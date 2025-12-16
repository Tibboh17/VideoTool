from django.db import models
from django.core.validators import FileExtensionValidator

class Video(models.Model):
    title = models.CharField(max_length=200, verbose_name='제목')
    description = models.TextField(blank=True, verbose_name='설명')
    file = models.FileField(
        upload_to='videos/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov', 'mkv', 'wmv'])],
        verbose_name='동영상 파일'
    )
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True, verbose_name='썸네일')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='업로드 일시')
    file_size = models.BigIntegerField(default=0, verbose_name='파일 크기(bytes)')
    duration = models.FloatField(default=0, verbose_name='재생 시간(초)')
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = '동영상'
        verbose_name_plural = '동영상 목록'
    
    def __str__(self):
        return self.title
    
    def get_file_size_display(self):
        """파일 크기를 읽기 쉽게 표시"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    