from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse, Http404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from analysis.models import Analysis
from .models import Detection, DetectionModel
import os
import re
from django.conf import settings
from wsgiref.util import FileWrapper

def model_list(request):
    """모델 목록"""
    models = DetectionModel.objects.filter(is_active=True).order_by('-created_at')
    
    # 통계
    total_models = models.count()
    yolo_models = models.filter(model_type='yolo').count()
    custom_models = models.filter(model_type='custom').count()
    
    context = {
        'models': models,
        'total_models': total_models,
        'yolo_models': yolo_models,
        'custom_models': custom_models,
    }
    return render(request, 'detection/model_list.html', context)


def model_add(request):
    """모델 추가"""
    if request.method == 'POST':
        name = request.POST.get('name')
        model_type = request.POST.get('model_type')
        description = request.POST.get('description', '')
        yolo_version = request.POST.get('yolo_version', '')
        model_file = request.FILES.get('model_file')
        
        # 설정
        conf_threshold = request.POST.get('conf_threshold', '0.25')
        
        try:
            conf_threshold = float(conf_threshold)
        except:
            conf_threshold = 0.25
        
        config = {
            'conf_threshold': conf_threshold,
        }
        
        # 모델 생성
        model = DetectionModel.objects.create(
            name=name,
            model_type=model_type,
            description=description,
            yolo_version=yolo_version if model_type == 'yolo' and not model_file else '',
            model_file=model_file,
            config=config,
        )
        
        messages.success(request, f'모델 "{name}"이(가) 추가되었습니다.')
        return redirect('detection_model_list')
    
    # YOLO 기본 모델 목록
    yolo_versions = [
        ('yolov8n.pt', 'YOLOv8 Nano (빠름, 정확도 낮음)'),
        ('yolov8s.pt', 'YOLOv8 Small (균형)'),
        ('yolov8m.pt', 'YOLOv8 Medium (정확도 높음)'),
        ('yolov8l.pt', 'YOLOv8 Large (정확도 매우 높음)'),
        ('yolov8x.pt', 'YOLOv8 XLarge (최고 정확도, 느림)'),
    ]
    
    context = {
        'yolo_versions': yolo_versions,
    }
    return render(request, 'detection/model_add.html', context)


def model_detail(request, model_id):
    """모델 상세"""
    model = get_object_or_404(DetectionModel, id=model_id)
    
    # 이 모델을 사용한 감지 작업들
    detections = Detection.objects.filter(model=model).select_related(
        'analysis__video'
    ).order_by('-created_at')[:10]
    
    # 통계
    total_detections = Detection.objects.filter(model=model).count()
    completed_detections = Detection.objects.filter(
        model=model, 
        status='completed'
    ).count()
    
    context = {
        'model': model,
        'detections': detections,
        'total_detections': total_detections,
        'completed_detections': completed_detections,
    }
    return render(request, 'detection/model_detail.html', context)


def model_delete(request, model_id):
    """모델 삭제"""
    model = get_object_or_404(DetectionModel, id=model_id)
    
    if request.method == 'POST':
        # 이 모델을 사용하는 감지 작업 확인
        detection_count = Detection.objects.filter(model=model).count()
        
        if detection_count > 0:
            messages.warning(
                request, 
                f'이 모델을 사용하는 감지 작업이 {detection_count}개 있습니다. '
                f'먼저 감지 작업을 삭제하거나 다른 모델로 변경해주세요.'
            )
            return redirect('detection_model_detail', model_id=model_id)
        
        # 파일 삭제
        try:
            model.delete_files()
        except Exception as e:
            print(f"파일 삭제 중 오류: {e}")
        
        model_name = model.name
        model.delete()
        
        messages.success(request, f'모델 "{model_name}"이(가) 삭제되었습니다.')
        return redirect('detection_model_list')
    
    return redirect('detection_model_detail', model_id=model_id)


def start_detection(request, analysis_id):
    """감지 작업 시작"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    if analysis.status != 'completed':
        messages.error(request, '분석이 완료되지 않았습니다.')
        return redirect('analysis_result', analysis_id=analysis_id)
    
    # 사용 가능한 모델 목록
    models = DetectionModel.objects.filter(is_active=True)
    
    if request.method == 'POST':
        model_id = request.POST.get('model_id')
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        
        model = get_object_or_404(DetectionModel, id=model_id)
        
        # Detection 객체 생성
        detection = Detection.objects.create(
            analysis=analysis,
            model=model,
            title=title or f"{model.name} 감지",
            description=description,
            status='ready',
        )
        
        messages.success(request, '감지 작업이 생성되었습니다.')
        return redirect('execute_detection', detection_id=detection.id)
    
    context = {
        'analysis': analysis,
        'models': models,
    }
    return render(request, 'detection/start_detection.html', context)


def execute_detection(request, detection_id):
    """감지 실행"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    if request.method == 'POST':
        # 백그라운드 작업 시작
        from .tasks import process_detection
        
        # 즉시 처리 (나중에 Celery로 변경 가능)
        import threading
        thread = threading.Thread(target=process_detection, args=(detection_id,))
        thread.start()
        
        messages.info(request, '감지 작업이 시작되었습니다.')
        return redirect('detection_progress', detection_id=detection_id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'detection/execute_detection.html', context)


def detection_progress(request, detection_id):
    """진행 상황 페이지"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'detection/detection_progress.html', context)


def detection_status(request, detection_id):
    """진행 상황 API (AJAX)"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    data = {
        'status': detection.status,
        'progress': detection.progress,
        'processed_frames': detection.processed_frames,
        'total_frames': detection.total_frames,
        'error_message': detection.error_message,
    }
    
    return JsonResponse(data)


def detection_result(request, detection_id):
    """감지 결과 페이지"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    # 결과 파싱
    results = detection.get_results()
    
    context = {
        'detection': detection,
        'analysis': detection.analysis,
        'video': detection.analysis.video,
        'results': results,
    }
    return render(request, 'detection/detection_result.html', context)


def detection_dashboard(request):
    """대시보드"""
    # 전체 통계
    total_detections = Detection.objects.count()
    completed_detections = Detection.objects.filter(status='completed').count()
    processing_detections = Detection.objects.filter(status='processing').count()
    failed_detections = Detection.objects.filter(status='failed').count()
    
    # 최근 감지 작업
    recent_detections = Detection.objects.select_related(
        'analysis__video', 'model'
    ).order_by('-created_at')[:10]
    
    # 모델별 통계
    model_stats = DetectionModel.objects.annotate(
        total=Count('detection'),
        completed=Count('detection', filter=Q(detection__status='completed'))
    ).filter(is_active=True)
    
    context = {
        'total_detections': total_detections,
        'completed_detections': completed_detections,
        'processing_detections': processing_detections,
        'failed_detections': failed_detections,
        'recent_detections': recent_detections,
        'model_stats': model_stats,
    }
    return render(request, 'detection/dashboard.html', context)


def serve_detection_video(request, detection_id):
    """감지 결과 동영상 스트리밍"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    if not detection.output_video_path:
        raise Http404("처리된 동영상이 없습니다.")
    
    video_path = os.path.join(settings.BASE_DIR, 'media', detection.output_video_path)
    
    if not os.path.exists(video_path):
        raise Http404("동영상 파일을 찾을 수 없습니다.")
    
    file_size = os.path.getsize(video_path)
    
    # Range Request 처리
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)
    range_match = range_re.match(range_header)
    
    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else file_size - 1
        
        if last_byte >= file_size:
            last_byte = file_size - 1
        
        length = last_byte - first_byte + 1
        
        with open(video_path, 'rb') as f:
            f.seek(first_byte)
            data = f.read(length)
        
        response = HttpResponse(data, status=206, content_type='video/mp4')
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        
        return response
    
    else:
        response = StreamingHttpResponse(
            FileWrapper(open(video_path, 'rb'), 8192),
            content_type='video/mp4'
        )
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        
        return response


def detection_delete(request, detection_id):
    """감지 작업 삭제"""
    detection = get_object_or_404(Detection, id=detection_id)
    analysis_id = detection.analysis.id
    video_id = detection.analysis.video.id
    model_id = detection.model.id  # ⭐ 추가
    
    if request.method == 'POST':
        try:
            detection.delete_files()
        except Exception as e:
            print(f"파일 삭제 중 오류: {e}")
        
        detection.delete()
        messages.success(request, '감지 작업이 삭제되었습니다.')
        
        redirect_to = request.POST.get('redirect', 'detection_dashboard')
        
        if redirect_to == 'analysis_result':
            return redirect('analysis_result', analysis_id=analysis_id)
        elif redirect_to == 'video_detail':
            return redirect('video_detail', pk=video_id)
        elif redirect_to == 'model_detail': 
            return redirect('detection_model_detail', model_id=model_id)
        else:
            return redirect('detection_dashboard')
    
    messages.warning(request, '잘못된 접근입니다.')
    return redirect('detection_dashboard')