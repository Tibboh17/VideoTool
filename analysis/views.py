from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from videos.models import Video
from .models import Analysis
from .preprocessing import VideoPreprocessor
from .tasks import process_video_analysis
import json
import os, re
import mimetypes
from wsgiref.util import FileWrapper
from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponse, Http404

def start_analysis(request, video_id):
    """분석 시작 - 전처리 선택 페이지"""
    video = get_object_or_404(Video, pk=video_id)
    
    # 새 분석 생성 또는 기존 분석 가져오기
    analysis = Analysis.objects.filter(video=video, status='ready').first()
    if not analysis:
        analysis = Analysis.objects.create(video=video, status='ready')
    
    # 사용 가능한 전처리 방법들
    preprocessing_methods = VideoPreprocessor.PREPROCESSING_METHODS
    
    context = {
        'video': video,
        'analysis': analysis,
        'preprocessing_methods': preprocessing_methods,
        'current_pipeline': analysis.get_pipeline_display(),
    }
    return render(request, 'analysis/preprocessing.html', context)


def add_preprocessing_step(request, analysis_id):
    """전처리 단계 추가 (AJAX)"""
    if request.method == 'POST':
        analysis = get_object_or_404(Analysis, id=analysis_id)
        
        data = json.loads(request.body)
        step_type = data.get('type')
        params = data.get('params', {})
        
        # 전처리 단계 추가
        analysis.add_preprocessing_step(step_type, params)
        
        return JsonResponse({
            'success': True,
            'pipeline': analysis.get_pipeline_display(),
            'pipeline_full': analysis.preprocessing_pipeline
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


def remove_preprocessing_step(request, analysis_id):
    """마지막 전처리 단계 제거 (AJAX)"""
    if request.method == 'POST':
        analysis = get_object_or_404(Analysis, id=analysis_id)
        analysis.remove_last_step()
        
        return JsonResponse({
            'success': True,
            'pipeline': analysis.get_pipeline_display(),
            'pipeline_full': analysis.preprocessing_pipeline
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


def execute_analysis(request, analysis_id):
    """분석 실행"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    if analysis.status == 'processing':
        messages.warning(request, '이미 처리 중입니다.')
        return redirect('analysis_progress', analysis_id=analysis.id)
    
    # 분석 실행 (백그라운드)
    import threading
    thread = threading.Thread(target=process_video_analysis, args=(analysis.id,))
    thread.start()
    
    return redirect('analysis_progress', analysis_id=analysis.id)


def analysis_progress(request, analysis_id):
    """분석 진행 상황 페이지"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    context = {
        'analysis': analysis,
        'video': analysis.video,
    }
    return render(request, 'analysis/progress.html', context)


def analysis_status(request, analysis_id):
    """분석 상태 확인 (AJAX)"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    return JsonResponse({
        'status': analysis.status,
        'progress': analysis.progress,
        'current_step': analysis.current_step,
        'processed_frames': analysis.processed_frames,
        'total_frames': analysis.total_frames,
        'error_message': analysis.error_message,
    })


def analysis_result(request, analysis_id):
    """분석 결과 페이지"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    if analysis.status != 'completed':
        return redirect('analysis_progress', analysis_id=analysis.id)
    
    context = {
        'analysis': analysis,
        'video': analysis.video,
    }
    return render(request, 'analysis/result.html', context)

def analysis_delete(request, analysis_id):
    """분석 삭제"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    video_id = analysis.video.id
    
    if request.method == 'POST':
        try:
            for detection in analysis.detections.all():
                try:
                    detection.delete_files()
                except Exception as e:
                    print(f"감지 파일 삭제 중 오류: {e}")
                detection.delete()
            
            # 분석 파일 삭제
            analysis.delete_files()
        except Exception as e:
            print(f"파일 삭제 중 오류: {e}")
        
        analysis.delete()
        messages.success(request, '분석이 삭제되었습니다.')
        
        redirect_to = request.POST.get('redirect', 'analysis_list')
        
        if redirect_to == 'video_detail':
            return redirect('video_detail', pk=video_id)
        else:
            return redirect('video_list') 
    
    messages.warning(request, '잘못된 접근입니다.')
    return redirect('video_detail', pk=video_id)


def serve_analysis_video(request, analysis_id):
    """
    분석 결과 동영상 스트리밍
    """
    from django.conf import settings
    
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    if not analysis.output_video_path:
        raise Http404("처리된 동영상이 없습니다.")
    
    # 파일 경로
    video_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)
    
    if not os.path.exists(video_path):
        raise Http404("동영상 파일을 찾을 수 없습니다.")
    
    # 파일 크기 및 타입
    file_size = os.path.getsize(video_path)
    content_type, _ = mimetypes.guess_type(video_path)
    content_type = content_type or 'video/mp4'
    
    # Range 헤더 파싱
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', range_header, re.I)
    
    if range_match:
        # Range Request
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else file_size - 1
        
        if last_byte >= file_size:
            last_byte = file_size - 1
        
        length = last_byte - first_byte + 1
        
        with open(video_path, 'rb') as f:
            f.seek(first_byte)
            data = f.read(length)
        
        response = HttpResponse(data, status=206, content_type=content_type)
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        
        return response
    
    else:
        # 일반 요청
        response = StreamingHttpResponse(
            FileWrapper(open(video_path, 'rb'), 8192),
            content_type=content_type
        )
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        
        return response
    
