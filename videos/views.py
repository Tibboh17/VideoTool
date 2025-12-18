import os
import re
import mimetypes
from io import BytesIO

import ffmpeg
from PIL import Image

from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView

from .forms import VideoUploadForm
from .models import Video

class VideoListView(ListView):
    model = Video
    template_name = 'videos/video_list.html'
    context_object_name = 'videos'
    paginate_by = 9

    def get_queryset(self):
        queryset = Video.objects.all().order_by('-uploaded_at')
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')

        page_obj = context.get('page_obj')
        if page_obj is not None:
            context['videos'] = page_obj

        return context

class VideoCreateView(CreateView):
    model = Video
    form_class = VideoUploadForm
    template_name = 'videos/video_upload.html'

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if self.object.file:
            self.object.file_size = self.object.file.size

        self.object.save()

        if self.object.file:
            thumbnail_content = generate_thumbnail(self.object.file.path)
            if thumbnail_content:
                original_name = os.path.splitext(os.path.basename(self.object.file.name))[0]
                thumbnail_name = f"{original_name}_thumb.jpg"
                self.object.thumbnail.save(thumbnail_name, thumbnail_content, save=False)

        self.object.save()

        messages.success(self.request, '동영상이 성공적으로 업로드되었습니다!')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, '업로드 중 오류가 발생했습니다. 다시 시도해주세요.')
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('video_detail', kwargs={'pk': self.object.pk})

class VideoDetailView(DetailView):
    model = Video
    template_name = 'videos/video_detail.html'
    context_object_name = 'video'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            'analyses',
            'analyses__detections',
            'analyses__detections__model',
        )

class VideoDeleteView(DeleteView):
    model = Video
    template_name = 'videos/video_delete.html'
    context_object_name = 'video'
    success_url = reverse_lazy('video_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.file and os.path.isfile(self.object.file.path):
            os.remove(self.object.file.path)

        if self.object.thumbnail and os.path.isfile(self.object.thumbnail.path):
            os.remove(self.object.thumbnail.path)

        messages.success(request, '동영상이 삭제되었습니다.')
        return super().delete(request, *args, **kwargs)

class VideoStreamView(View):
    def get(self, request, pk):
        video = get_object_or_404(Video, pk=pk)
        video_path = video.file.path

        if not os.path.exists(video_path):
            raise Http404('동영상 파일을 찾을 수 없습니다.')

        file_size = os.path.getsize(video_path)
        content_type, _ = mimetypes.guess_type(video_path)
        if not content_type:
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

        response = FileResponse(open(video_path, 'rb'), content_type=content_type)
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        return response

def generate_thumbnail(video_path):
    try:
        out, _ = (
            ffmpeg.input(video_path, ss=0)
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True)
        )

        image = Image.open(BytesIO(out))
        image.thumbnail((640, 360), Image.Resampling.LANCZOS)

        thumb_io = BytesIO()
        image.save(thumb_io, format='JPEG', quality=85)
        thumb_io.seek(0)

        return ContentFile(thumb_io.read())
    except Exception as exc:
        print(f"썸네일 생성 오류: {exc}")
        return None
