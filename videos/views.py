from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import StreamingHttpResponse, HttpResponse, Http404
from django.core.files.base import ContentFile
from .models import Video 
from .forms import VideoUploadForm
import os
import re
import mimetypes
import ffmpeg
from io import BytesIO
from PIL import Image

def generate_thumbnail(video_path):
    """영상의 첫 번째 프레임을 썸네일로 생성"""
    try:
        # ffmpeg로 첫 번째 프레임 추출
        out, _ = (
            ffmpeg
            .input(video_path, ss=0)  # 0초 위치에서
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # 이미지를 PIL로 열고 리사이즈
        image = Image.open(BytesIO(out))
        
        # 썸네일 크기 조정 (예: 640x360)
        image.thumbnail((640, 360), Image.Resampling.LANCZOS)
        
        # BytesIO에 저장
        thumb_io = BytesIO()
        image.save(thumb_io, format='JPEG', quality=85)
        thumb_io.seek(0)
        
        return ContentFile(thumb_io.read())
    
    except Exception as e:
        print(f"썸네일 생성 오류: {e}")
        return None


def video_upload(request):
    """동영상 업로드"""
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            
            # 파일 크기 저장
            if video.file:
                video.file_size = video.file.size
            
            # 임시 저장 (파일 경로를 얻기 위해)
            video.save()
            
            # 썸네일 자동 생성
            if video.file:
                thumbnail_content = generate_thumbnail(video.file.path)
                if thumbnail_content:
                    # 원본 파일명 기반으로 썸네일 파일명 생성
                    original_name = os.path.splitext(os.path.basename(video.file.name))[0]
                    thumbnail_name = f"{original_name}_thumb.jpg"
                    video.thumbnail.save(thumbnail_name, thumbnail_content, save=False)
            
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

def video_list(request):
    """동영상 목록"""
    videos = Video.objects.all().order_by('-uploaded_at')
    
    # 검색
    search = request.GET.get('search', '')
    if search:
        videos = videos.filter(title__icontains=search)
    
    context = {
        'videos': videos,
        'search': search,
    }
    return render(request, 'videos/video_list.html', context)

def video_detail(request, pk):
    """동영상 상세"""
    video = get_object_or_404(Video, pk=pk)
    
    from analysis.models import Analysis
    analyses_count = Analysis.objects.filter(video=video).count()
    print(f"\n{'='*60}")
    print(f"🎬 동영상 상세 페이지")
    print(f"{'='*60}")
    print(f"동영상 ID: {video.id}")
    print(f"동영상 제목: {video.title}")
    print(f"분석 개수 (직접 쿼리): {analyses_count}")
    print(f"분석 개수 (video.analyses): {video.analyses.count()}")
    
    # 분석 목록 출력
    for analysis in video.analyses.all():
        print(f"  - 분석 #{analysis.id}: {analysis.status}, 생성={analysis.created_at}")
    print(f"{'='*60}\n")
    
    analyses = video.analyses.prefetch_related(
        'detections', 
        'detections__model'
    ).order_by('-created_at')
    
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
        with open(video_path, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='video/mp4'
            )
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        
        return response