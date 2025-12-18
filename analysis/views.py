from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.utils import timezone
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
    # ⭐ type 파라미터로 video/image 구분
    media_type = request.GET.get('type', 'video')
    
    if media_type == 'image':
        from videos.models import Image
        media = get_object_or_404(Image, pk=video_id)
    else:
        media = get_object_or_404(Video, pk=video_id)
    
    # POST 요청 처리 (전처리 생략)
    if request.method == 'POST':
        skip_preprocessing = request.POST.get('skip_preprocessing') == 'true'
        
        if skip_preprocessing:
            # 전처리 생략
            if media_type == 'image':
                analysis = Analysis.objects.create(
                    image=media,
                    preprocessing_pipeline=[],
                    status='completed'
                )
                analysis.output_video_path = media.file.name
            else:
                analysis = Analysis.objects.create(
                    video=media,
                    preprocessing_pipeline=[],
                    status='completed'
                )
                analysis.output_video_path = media.file.name
            
            analysis.total_frames = 0
            analysis.processed_frames = 0
            analysis.completed_at = timezone.now()
            analysis.save()
            
            messages.success(request, '전처리를 생략했습니다. 이제 모델을 적용할 수 있습니다.')
            
            if media_type == 'image':
                return redirect('image_detail', pk=media.pk)
            else:
                return redirect('analysis_result', analysis_id=analysis.id)
    
    # GET 요청 - 기존 로직
    if media_type == 'image':
        analysis = Analysis.objects.filter(image=media, status='ready').first()
    else:
        analysis = Analysis.objects.filter(video=media, status='ready').first()
    
    if not analysis:
        if media_type == 'image':
            analysis = Analysis.objects.create(image=media, status='ready')
        else:
            analysis = Analysis.objects.create(video=media, status='ready')
    
    preprocessing_methods = VideoPreprocessor.PREPROCESSING_METHODS
    
    context = {
        'video': media,  # 템플릿 호환성
        'media': media,
        'media_type': media_type,
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
    
    # 미디어 정보
    media = analysis.get_media()
    media_type = analysis.get_media_type()
    
    if not media:
        messages.error(request, '미디어를 찾을 수 없습니다.')
        return redirect('media_list')
    
    if analysis.status == 'processing':
        messages.warning(request, '이미 처리 중입니다.')
        return redirect('analysis_progress', analysis_id=analysis_id)
    
    # 백그라운드 작업 시작
    from .tasks import start_analysis_task
    start_analysis_task(analysis_id)
    
    messages.success(request, '분석이 시작되었습니다.')
    return redirect('analysis_progress', analysis_id=analysis_id)


def analysis_progress(request, analysis_id):
    """분석 진행 상황"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    # 미디어 정보 가져오기
    media = analysis.get_media()
    media_type = analysis.get_media_type()
    
    # 미디어가 없으면 에러
    if not media:
        messages.error(request, '미디어를 찾을 수 없습니다.')
        return redirect('media_list')
    
    context = {
        'analysis': analysis,
        'media': media,
        'media_type': media_type,
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
    
    # 미디어 정보 가져오기
    media = analysis.get_media()
    media_type = analysis.get_media_type()
    
    # 미디어가 없으면 에러
    if not media:
        messages.error(request, '미디어를 찾을 수 없습니다.')
        return redirect('media_list')
    
    context = {
        'analysis': analysis,
        'media': media,
        'media_type': media_type,
    }
    return render(request, 'analysis/result.html', context)



def analysis_delete(request, analysis_id):
    """분석 삭제"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    # video 또는 image 확인
    media = analysis.get_media()
    media_type = analysis.get_media_type()
    
    if request.method == 'POST':
        # 파일 삭제
        analysis.delete_files()
        
        # 분석 삭제
        analysis.delete()
        
        messages.success(request, '분석이 삭제되었습니다.')
        
        # 리다이렉트 처리
        redirect_to = request.POST.get('redirect', 'analysis_result')
        
        if redirect_to == 'video_detail':
            return redirect('video_detail', pk=media.id)
        elif redirect_to == 'image_detail':
            return redirect('image_detail', pk=media.id)
        else:
            # 기본: 미디어 목록으로
            return redirect('media_list')
    
    context = {
        'analysis': analysis,
        'media': media,
        'media_type': media_type,
    }
    return render(request, 'analysis/analysis_delete.html', context)


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
    

def serve_analysis_image(request, analysis_id):
    """
    분석 결과 이미지 제공 (동영상 스트리밍 로직의 이미지 버전)
    """
    from django.conf import settings
    
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    if not analysis.output_video_path:
        raise Http404("처리된 결과 파일이 없습니다.")
    
    image_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)
    
    if not os.path.exists(image_path):
        raise Http404("이미지 파일을 찾을 수 없습니다.")
    
    content_type, _ = mimetypes.guess_type(image_path)
    content_type = content_type or 'image/jpeg'
    
    response = FileResponse(open(image_path, 'rb'), content_type=content_type)
    
    return response