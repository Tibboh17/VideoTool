from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from analysis.models import Analysis
from modelhub.models import BaseModel, CustomModel
from .models import Detection
import threading


def select_model(request, analysis_id):
    """모델 선택 페이지"""
    analysis = get_object_or_404(Analysis, id=analysis_id)
    
    # 분석이 완료되지 않았으면 리다이렉트
    if analysis.status != 'completed':
        messages.error(request, '분석이 완료되지 않았습니다.')
        return redirect('analysis_result', analysis_id=analysis_id)
    
    # 활성화된 모델 목록
    base_models = BaseModel.objects.filter(is_active=True)
    custom_models = CustomModel.objects.filter(is_active=True)
    
    if request.method == 'POST':
        model_type = request.POST.get('model_type')  # 'base' or 'custom'
        model_id = request.POST.get('model_id')
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        
        # Detection 생성
        detection = Detection.objects.create(
            analysis=analysis,
            title=title or f"객체 탐지 - {timezone.now().strftime('%Y%m%d_%H%M%S')}",
            description=description,
            status='ready'
        )
        
        # 모델 할당
        if model_type == 'base':
            model = get_object_or_404(BaseModel, id=model_id)
            detection.base_model = model
        else:
            model = get_object_or_404(CustomModel, id=model_id)
            detection.custom_model = model
        
        detection.save()
        
        messages.success(request, '탐지 작업이 생성되었습니다.')
        return redirect('vision_engine:execute_detection', detection_id=detection.id)
    
    context = {
        'analysis': analysis,
        'base_models': base_models,
        'custom_models': custom_models,
    }
    return render(request, 'vision_engine/select_model.html', context)


def execute_detection(request, detection_id):
    """탐지 실행 페이지"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    if request.method == 'POST':
        # 백그라운드로 탐지 실행
        from .tasks import process_detection
        
        thread = threading.Thread(target=process_detection, args=(detection_id,))
        thread.start()
        
        messages.info(request, '탐지 작업이 시작되었습니다.')
        return redirect('vision_engine:detection_progress', detection_id=detection.id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'vision_engine/execute_detection.html', context)


def detection_progress(request, detection_id):
    """탐지 진행 상황 페이지"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'vision_engine/detection_progress.html', context)


def detection_status(request, detection_id):
    """탐지 상태 API (AJAX)"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    return JsonResponse({
        'status': detection.status,
        'progress': detection.progress,
        'processed_frames': detection.processed_frames,
        'total_frames': detection.total_frames,
        'error_message': detection.error_message,
    })


def detection_result(request, detection_id):
    """탐지 결과 페이지"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'vision_engine/detection_result.html', context)


def detection_list(request):
    """전체 탐지 목록"""
    detections = Detection.objects.all().order_by('-created_at')
    
    # 상태별 필터
    status = request.GET.get('status')
    if status:
        detections = detections.filter(status=status)
    
    context = {
        'detections': detections,
    }
    return render(request, 'vision_engine/detection_list.html', context)


def detection_delete(request, detection_id):
    """탐지 삭제"""
    detection = get_object_or_404(Detection, id=detection_id)
    
    if request.method == 'POST':
        analysis_id = detection.analysis.id
        detection.delete()
        
        messages.success(request, '탐지 작업이 삭제되었습니다.')
        return redirect('analysis_result', analysis_id=analysis_id)
    
    context = {
        'detection': detection,
    }
    return render(request, 'vision_engine/detection_delete.html', context)
