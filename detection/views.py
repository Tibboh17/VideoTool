import os
import re
import threading
from wsgiref.util import FileWrapper

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, TemplateView

from analysis.models import Analysis
from .models import Detection, DetectionModel, get_custom_model_path, get_default_model_path


class DetectionModelListView(ListView):
    model = DetectionModel
    template_name = 'detection/model_list.html'
    context_object_name = 'models'

    def get_queryset(self):
        return DetectionModel.objects.filter(is_active=True).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        models = context['models']
        context['total_models'] = models.count()
        context['yolo_models'] = models.filter(model_type='yolo').count()
        context['custom_models'] = models.filter(model_type='custom').count()
        return context

class DetectionModelAddView(View):
    template_name = 'detection/model_add.html'

    YOLO_VERSIONS = [
        ('yolov8n.pt', 'YOLOv8 Nano (빠름, 보통 정확도)'),
        ('yolov8s.pt', 'YOLOv8 Small (균형)'),
        ('yolov8m.pt', 'YOLOv8 Medium (정확도 우선)'),
        ('yolov8l.pt', 'YOLOv8 Large (정확도 매우 우선)'),
        ('yolov8x.pt', 'YOLOv8 XLarge (최고 정확도 모델)'),
    ]

    def get(self, request):
        return render(request, self.template_name, {'yolo_versions': self.YOLO_VERSIONS})

    def post(self, request):
        name = request.POST.get('name')
        model_type = request.POST.get('model_type')
        description = request.POST.get('description', '')
        yolo_version = request.POST.get('yolo_version', '')
        model_file = request.FILES.get('model_file')

        conf_threshold = request.POST.get('conf_threshold', '0.25')
        try:
            conf_threshold = float(conf_threshold)
        except Exception:
            conf_threshold = 0.25
        config = {'conf_threshold': conf_threshold}

        # 유효성 검사
        if model_type == 'yolo':
            if not model_file and not yolo_version:
                messages.error(request, 'YOLO 모델은 파일 업로드나 버전 지정이 필요합니다.')
                return redirect('detection_model_add')
        elif model_type == 'custom':
            if not model_file:
                messages.error(request, '커스텀 모델은 파일 업로드가 필요합니다.')
                return redirect('detection_model_add')

        # 모델 파일 저장
        model_path = ''
        if model_file:
            if model_type == 'yolo':
                save_path = get_default_model_path(model_file.name)
            else:
                save_path = get_custom_model_path(model_file.name)

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb+') as destination:
                for chunk in model_file.chunks():
                    destination.write(chunk)

            model_path = os.path.relpath(save_path, settings.MODELS_ROOT)

        model = DetectionModel.objects.create(
            name=name,
            model_type=model_type,
            description=description,
            model_path=model_path,
            yolo_version=yolo_version if model_type == 'yolo' and not model_file else '',
            config=config,
        )

        messages.success(request, f'모델 "{model.name}"이(가) 추가되었습니다.')
        return redirect('detection_model_list')

class DetectionModelDetailView(DetailView):
    model = DetectionModel
    template_name = 'detection/model_detail.html'
    pk_url_kwarg = 'model_id'
    context_object_name = 'model'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.object
        detections = Detection.objects.filter(model=model).select_related(
            'analysis__video'
        ).order_by('-created_at')[:10]

        context.update({
            'detections': detections,
            'total_detections': Detection.objects.filter(model=model).count(),
            'completed_detections': Detection.objects.filter(model=model, status='completed').count(),
        })
        return context

class DetectionModelDeleteView(DeleteView):
    model = DetectionModel
    pk_url_kwarg = 'model_id'
    success_url = reverse_lazy('detection_model_list')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        detection_count = Detection.objects.filter(model=self.object).count()
        if detection_count > 0:
            messages.warning(
                request,
                f'해당 모델을 사용하는 감지 작업이 {detection_count}개 있습니다. 다른 모델로 변경 후 삭제하세요.',
            )
            return redirect('detection_model_detail', model_id=self.object.id)

        try:
            self.object.delete_files()
        except Exception as exc:
            print(f"모델 파일 삭제 오류: {exc}")

        model_name = self.object.name
        response = super().post(request, *args, **kwargs)
        messages.success(request, f'모델 "{model_name}"이(가) 삭제되었습니다.')
        return response

class StartDetectionView(View):
    template_name = 'detection/start_detection.html'

    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)

        if analysis.status != 'completed':
            messages.error(request, '분석이 완료되지 않았습니다.')
            return redirect('analysis_result', analysis_id=analysis_id)

        models = DetectionModel.objects.filter(is_active=True)
        context = {'analysis': analysis, 'models': models}
        return render(request, self.template_name, context)

    def post(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)

        if analysis.status != 'completed':
            messages.error(request, '분석이 완료되지 않았습니다.')
            return redirect('analysis_result', analysis_id=analysis_id)

        model_id = request.POST.get('model_id')
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        model = get_object_or_404(DetectionModel, id=model_id)

        detection = Detection.objects.create(
            analysis=analysis,
            model=model,
            title=title or f"{model.name} 감지",
            description=description,
            status='ready',
        )

        messages.success(request, '감지 작업이 생성되었습니다.')
        return redirect('execute_detection', detection_id=detection.id)

class ExecuteDetectionView(View):
    template_name = 'detection/execute_detection.html'

    def get(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)
        return render(request, self.template_name, {'detection': detection})

    def post(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)
        from .tasks import process_detection

        thread = threading.Thread(target=process_detection, args=(detection_id,))
        thread.start()

        messages.info(request, '감지 작업이 시작되었습니다.')
        return redirect('detection_progress', detection_id=detection_id)

class DetectionProgressView(View):
    template_name = 'detection/detection_progress.html'

    def get(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)
        return render(request, self.template_name, {'detection': detection})

class DetectionStatusView(View):
    def get(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)
        return JsonResponse({
            'status': detection.status,
            'progress': detection.progress,
            'processed_frames': detection.processed_frames,
            'total_frames': detection.total_frames,
            'error_message': detection.error_message,
        })

class DetectionResultView(View):
    template_name = 'detection/detection_result.html'

    def get(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)
        results = detection.get_results()

        context = {
            'detection': detection,
            'analysis': detection.analysis,
            'video': detection.analysis.video,
            'results': results,
        }
        return render(request, self.template_name, context)

class DetectionDashboardView(TemplateView):
    template_name = 'detection/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['total_detections'] = Detection.objects.count()
        context['completed_detections'] = Detection.objects.filter(status='completed').count()
        context['processing_detections'] = Detection.objects.filter(status='processing').count()
        context['failed_detections'] = Detection.objects.filter(status='failed').count()

        context['recent_detections'] = Detection.objects.select_related(
            'analysis__video', 'model'
        ).order_by('-created_at')[:10]

        context['model_stats'] = DetectionModel.objects.annotate(
            total=Count('detection'),
            completed=Count('detection', filter=Q(detection__status='completed')),
        ).filter(is_active=True)

        return context

class ServeDetectionVideoView(View):
    def get(self, request, detection_id):
        detection = get_object_or_404(Detection, id=detection_id)

        if not detection.output_video_path:
            raise Http404("처리된 동영상 파일이 없습니다.")

        video_path = os.path.join(settings.BASE_DIR, 'media', detection.output_video_path)

        if not os.path.exists(video_path):
            raise Http404("동영상 파일을 찾을 수 없습니다.")

        file_size = os.path.getsize(video_path)
        content_type = 'video/mp4'

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

            with open(video_path, 'rb') as file:
                file.seek(first_byte)
                data = file.read(length)

            response = HttpResponse(data, status=206, content_type=content_type)
            response['Content-Length'] = str(length)
            response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
            response['Accept-Ranges'] = 'bytes'
            return response

        response = StreamingHttpResponse(
            FileWrapper(open(video_path, 'rb'), 8192),
            content_type=content_type,
        )
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        return response

class DetectionDeleteView(DeleteView):
    model = Detection
    pk_url_kwarg = 'detection_id'
    template_name = 'detection/detection_delete.html'
    context_object_name = 'detection'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        analysis = self.object.analysis
        media = analysis.get_media()
        media_type = analysis.get_media_type()
        model_id = self.object.model.id

        self.object.delete_files()
        self.object.delete()

        messages.success(request, '감지 작업이 삭제되었습니다.')

        redirect_to = request.POST.get('redirect', 'detection_dashboard')

        if redirect_to == 'video_detail' and media_type == 'video' and media:
            return redirect('video_detail', pk=media.id)
        if redirect_to == 'image_detail' and media_type == 'image' and media:
            return redirect('image_detail', pk=media.id)
        if redirect_to == 'analysis_result':
            return redirect('analysis_result', analysis_id=analysis.id)
        if redirect_to == 'model_detail':
            return redirect('detection_model_detail', model_id=model_id)

        return redirect('detection_dashboard')