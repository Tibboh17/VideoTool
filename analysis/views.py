import json
import mimetypes
import os
import re

from django.conf import settings
from django.contrib import messages
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DeleteView
from wsgiref.util import FileWrapper

from videos.models import Image, Video
from .models import Analysis
from .preprocessing import VideoPreprocessor


class StartAnalysisView(View):
    template_name = 'analysis/preprocessing.html'

    def _get_media(self, media_type, media_id):
        if media_type == 'image':
            return get_object_or_404(Image, pk=media_id)
        return get_object_or_404(Video, pk=media_id)

    def _get_ready_analysis(self, media, media_type):
        if media_type == 'image':
            analysis = Analysis.objects.filter(image=media, status='ready').first()
            if not analysis:
                analysis = Analysis.objects.create(image=media, status='ready')
            return analysis

        analysis = Analysis.objects.filter(video=media, status='ready').first()
        if not analysis:
            analysis = Analysis.objects.create(video=media, status='ready')
        return analysis

    def _skip_preprocessing(self, request, media, media_type):
        if media_type == 'image':
            analysis = Analysis.objects.create(
                image=media,
                preprocessing_pipeline=[],
                status='completed',
            )
            analysis.output_video_path = media.file.name
        else:
            analysis = Analysis.objects.create(
                video=media,
                preprocessing_pipeline=[],
                status='completed',
            )
            analysis.output_video_path = media.file.name

        analysis.total_frames = 0
        analysis.processed_frames = 0
        analysis.completed_at = timezone.now()
        analysis.save()

        messages.success(
            request,
            '전처리를 건너뛰었습니다. 이후 모델을 적용할 수 있습니다.',
        )

        if media_type == 'image':
            return redirect('image_detail', pk=media.pk)
        return redirect('analysis_result', analysis_id=analysis.id)

    def get(self, request, video_id):
        media_type = request.GET.get('type', 'video')
        media = self._get_media(media_type, video_id)
        analysis = self._get_ready_analysis(media, media_type)

        context = {
            'video': media,
            'media': media,
            'media_type': media_type,
            'analysis': analysis,
            'preprocessing_methods': VideoPreprocessor.PREPROCESSING_METHODS,
            'current_pipeline': analysis.get_pipeline_display(),
        }
        return render(request, self.template_name, context)

    def post(self, request, video_id):
        media_type = request.GET.get('type', 'video')
        media = self._get_media(media_type, video_id)
        skip_preprocessing = request.POST.get('skip_preprocessing') == 'true'

        if skip_preprocessing:
            return self._skip_preprocessing(request, media, media_type)

        # 전처리를 건너뛰지 않는 경우 기존 화면 그대로 렌더
        return self.get(request, video_id)


class AddPreprocessingStepView(View):
    def post(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        data = json.loads(request.body or '{}')
        step_type = data.get('type')
        params = data.get('params', {})

        analysis.add_preprocessing_step(step_type, params)

        return JsonResponse({
            'success': True,
            'pipeline': analysis.get_pipeline_display(),
            'pipeline_full': analysis.preprocessing_pipeline,
        })

    def get(self, request, analysis_id):
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=405)


class RemovePreprocessingStepView(View):
    def post(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        analysis.remove_last_preprocessing_step()

        return JsonResponse({
            'success': True,
            'pipeline': analysis.get_pipeline_display(),
            'pipeline_full': analysis.preprocessing_pipeline,
        })

    def get(self, request, analysis_id):
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=405)


class ExecuteAnalysisView(View):
    def post(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        media = analysis.get_media()

        if not media:
            messages.error(request, '미디어를 찾을 수 없습니다.')
            return redirect('media_list')

        if analysis.status == 'processing':
            messages.warning(request, '이미 처리 중입니다.')
            return redirect('analysis_progress', analysis_id=analysis_id)

        from .tasks import start_analysis_task

        start_analysis_task(analysis_id)
        messages.success(request, '분석을 시작했습니다.')
        return redirect('analysis_progress', analysis_id=analysis_id)

    def get(self, request, analysis_id):
        return redirect('analysis_progress', analysis_id=analysis_id)


class AnalysisProgressView(View):
    template_name = 'analysis/progress.html'

    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        media = analysis.get_media()

        if not media:
            messages.error(request, '미디어를 찾을 수 없습니다.')
            return redirect('media_list')

        context = {
            'analysis': analysis,
            'media': media,
            'media_type': analysis.get_media_type(),
        }
        return render(request, self.template_name, context)


class AnalysisStatusView(View):
    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        return JsonResponse({
            'status': analysis.status,
            'progress': analysis.progress,
            'current_step': analysis.current_step,
            'processed_frames': analysis.processed_frames,
            'total_frames': analysis.total_frames,
            'error_message': analysis.error_message,
        })


class AnalysisResultView(View):
    template_name = 'analysis/result.html'

    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)
        media = analysis.get_media()
        media_type = analysis.get_media_type()

        if not media:
            messages.error(request, '미디어를 찾을 수 없습니다.')
            return redirect('media_list')

        context = {
            'analysis': analysis,
            'media': media,
            'media_type': media_type,
        }
        return render(request, self.template_name, context)


class AnalysisDeleteView(DeleteView):
    model = Analysis
    template_name = 'analysis/analysis_delete.html'
    context_object_name = 'analysis'
    pk_url_kwarg = 'analysis_id'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        media = self.object.get_media()
        media_type = self.object.get_media_type()

        self.object.delete_files()
        self.object.delete()

        messages.success(request, '분석이 삭제되었습니다.')

        redirect_to = request.POST.get('redirect', 'analysis_result')
        if redirect_to == 'video_detail' and media_type == 'video' and media:
            return redirect('video_detail', pk=media.id)
        if redirect_to == 'image_detail' and media_type == 'image' and media:
            return redirect('image_detail', pk=media.id)

        return redirect('media_list')


class ServeAnalysisVideoView(View):
    """
    분석 결과 비디오 스트리밍
    """

    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)

        if not analysis.output_video_path:
            raise Http404("처리된 동영상 파일이 없습니다.")

        video_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)

        if not os.path.exists(video_path):
            raise Http404("동영상 파일을 찾을 수 없습니다.")

        file_size = os.path.getsize(video_path)
        content_type, _ = mimetypes.guess_type(video_path)
        content_type = content_type or 'video/mp4'

        range_header = request.META.get('HTTP_RANGE', '').strip()
        range_match = re.match(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', range_header, re.I)

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


class ServeAnalysisImageView(View):
    """
    분석 결과 이미지 서빙
    """

    def get(self, request, analysis_id):
        analysis = get_object_or_404(Analysis, id=analysis_id)

        if not analysis.output_video_path:
            raise Http404("처리된 이미지 파일이 없습니다.")

        image_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)

        if not os.path.exists(image_path):
            raise Http404("이미지 파일을 찾을 수 없습니다.")

        content_type, _ = mimetypes.guess_type(image_path)
        content_type = content_type or 'image/jpeg'

        return FileResponse(open(image_path, 'rb'), content_type=content_type)
