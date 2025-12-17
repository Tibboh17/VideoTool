from django.db import models
from django.utils import timezone
import os
import re

def sanitize_filename(filename):
    """파일명을 안전하게 정리 (특수문자, 공백 제거)"""
    # 확장자 분리
    name, ext = os.path.splitext(filename)
    
    # 공백을 언더스코어로 변경
    name = name.replace(' ', '_')
    
    # 특수문자 제거 (알파벳, 숫자, 언더스코어, 하이픈만 허용)
    name = re.sub(r'[^\w\-]', '', name)
    
    # 연속된 언더스코어 제거
    name = re.sub(r'_+', '_', name)
    
    # 앞뒤 언더스코어 제거
    name = name.strip('_')
    
    # 파일명이 비어있으면 기본값 사용
    if not name:
        name = 'video'
    
    return name, ext.lower()

def video_upload_path(instance, filename):
    """동영상 업로드 경로: videos/YYYY/원본파일명_MMDDhhmmss.확장자"""
    now = timezone.now()
    
    # 파일명 안전하게 정리
    name, ext = sanitize_filename(filename)
    
    # 새 파일명: 원본파일명_MMDDhhmmss.확장자
    new_filename = f"{name}_{now.strftime('%m%d%H%M%S')}{ext}"
    
    # 경로: videos/YYYY/파일명
    return os.path.join(
        'videos',
        str(now.year),
        new_filename
    )

def thumbnail_upload_path(instance, filename):
    """썸네일 업로드 경로: thumbnails/YYYY/원본파일명_thumb_MMDDhhmmss.jpg"""
    now = timezone.now()
    
    # 파일명 안전하게 정리
    name, ext = sanitize_filename(filename)
    
    # 새 파일명
    new_filename = f"{name}.jpg"
    
    return os.path.join(
        'thumbnails',
        str(now.year),
        new_filename
    )

class Video(models.Model):
    title = models.CharField(max_length=200, verbose_name='제목')
    description = models.TextField(blank=True, verbose_name='설명')
    file = models.FileField(
        upload_to=video_upload_path, 
        verbose_name='동영상 파일'
    )
    thumbnail = models.ImageField(
        upload_to=thumbnail_upload_path, 
        blank=True, 
        null=True, 
        verbose_name='썸네일'
    )
    file_size = models.BigIntegerField(default=0, verbose_name='파일 크기')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='업로드 시간')
    
    class Meta:
        verbose_name = '동영상'
        verbose_name_plural = '동영상들'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.title
    
    def get_file_size_display(self):
        """파일 크기를 읽기 쉬운 형식으로 반환"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"