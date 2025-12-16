from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import StreamingHttpResponse, HttpResponse, Http404
from .models import Video 
from .forms import VideoUploadForm
import os
import re
import mimetypes


def video_list(request):
    """동영상 목록"""
    videos = Video.objects.all()
    
    # 페이지네이션
    paginator = Paginator(videos, 12)  # 페이지당 12개
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'videos': page_obj,
    }
    return render(request, 'videos/video_list.html', context)


def video_upload(request):
    """동영상 업로드"""
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            
            # 파일 크기 저장
            if video.file:
                video.file_size = video.file.size
            
            video.save()
            messages.success(request, '동영상이 성공적으로 업로드되었습니다!')
            return redirect('video_detail', pk=video.pk)
        else:
            messages.error(request, '업로드 중 오류가 발생했습니다. 다시 시도해주세요.')
    else:
        form = VideoUploadForm()
    
    context = {
        'form': form,
    }
    return render(request, 'videos/video_upload.html', context)


def video_detail(request, pk):
    """동영상 상세보기"""
    video = get_object_or_404(Video, pk=pk)
    context = {
        'video': video,
    }
    return render(request, 'videos/video_detail.html', context)


def video_delete(request, pk):
    """동영상 삭제"""
    video = get_object_or_404(Video, pk=pk)
    
    if request.method == 'POST':
        # 파일 삭제
        if video.file:
            if os.path.isfile(video.file.path):
                os.remove(video.file.path)
        if video.thumbnail:
            if os.path.isfile(video.thumbnail.path):
                os.remove(video.thumbnail.path)
        
        video.delete()
        messages.success(request, '동영상이 삭제되었습니다.')
        return redirect('video_list')
    
    context = {
        'video': video,
    }
    return render(request, 'videos/video_delete.html', context)


def serve_video(request, pk):
    """동영상 스트리밍 (Range Request 지원)"""
    video = get_object_or_404(Video, pk=pk)
    
    # 파일 경로
    video_path = video.file.path
    
    if not os.path.exists(video_path):
        raise Http404("동영상 파일을 찾을 수 없습니다.")
    
    # 파일 크기
    file_size = os.path.getsize(video_path)
    
    # Range 헤더 확인
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)
    range_match = range_re.match(range_header)
    
    # Range Request 처리
    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else file_size - 1
        
        if last_byte >= file_size:
            last_byte = file_size - 1
        
        length = last_byte - first_byte + 1
        
        # 파일의 일부분만 읽기
        with open(video_path, 'rb') as f:
            f.seek(first_byte)
            data = f.read(length)
        
        response = HttpResponse(
            data, 
            status=206,  # Partial Content
            content_type='video/mp4'
        )
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        
        return response
    
    # 일반 요청 (Range 없음)
    else:
        response = StreamingHttpResponse(
            FileWrapper(open(video_path, 'rb'), 8192),
            content_type='video/mp4'
        )
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        
        return response