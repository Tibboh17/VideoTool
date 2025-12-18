from django.db import models
from django.utils import timezone
from videos.models import Video
import json

class Analysis(models.Model):
    STATUS_CHOICES = [
        ('ready', '준비'),
        ('processing', '처리 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]
    
    # video 또는 image 중 하나만 필수
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE, 
        related_name='analyses',
        null=True,
        blank=True,
        verbose_name='동영상'
    )
    
    image = models.ForeignKey(
        'videos.Image',
        on_delete=models.CASCADE,
        related_name='analyses',
        null=True,
        blank=True,
        verbose_name='이미지'
    )
    
    preprocessing_pipeline = models.JSONField(
        default=list, 
        blank=True,
        verbose_name='전처리 파이프라인'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ready',
        verbose_name='상태'
    )
    
    progress = models.IntegerField(default=0, verbose_name='진행률 (%)')
    
    # 현재 단계 필드 추가
    current_step = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='현재 단계'
    )
    
    # 처리 정보
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='시작 시간')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='완료 시간')
    processed_frames = models.IntegerField(default=0, verbose_name='처리된 프레임')
    total_frames = models.IntegerField(default=0, verbose_name='총 프레임')
    
    # 결과 저장
    output_video_path = models.CharField(
        max_length=500, 
        blank=True,
        verbose_name='출력 파일 경로'
    )
    
    # 에러
    error_message = models.TextField(blank=True, verbose_name='에러 메시지')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    class Meta:
        verbose_name = '분석'
        verbose_name_plural = '분석들'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.video:
            return f"Analysis #{self.id} - {self.video.title}"
        elif self.image:
            return f"Analysis #{self.id} - {self.image.title}"
        return f"Analysis #{self.id}"
    
    def clean(self):
        """video와 image 중 하나만 있어야 함"""
        from django.core.exceptions import ValidationError
        if not self.video and not self.image:
            raise ValidationError('동영상 또는 이미지 중 하나는 필수입니다.')
        if self.video and self.image:
            raise ValidationError('동영상과 이미지를 동시에 지정할 수 없습니다.')
    
    def get_media(self):
        """미디어 객체 반환 (video 또는 image)"""
        if self.video:
            return self.video
        elif self.image:
            return self.image
        else:
            return None
    
    def get_media_type(self):
        """미디어 타입 반환"""
        return 'video' if self.video else 'image'
    
    # ⭐ 전처리 파이프라인 관리 메서드들
    def add_preprocessing_step(self, step_type, params=None):
        """전처리 단계 추가"""
        if not isinstance(self.preprocessing_pipeline, list):
            self.preprocessing_pipeline = []
        
        step = {
            'type': step_type,
            'params': params or {}
        }
        self.preprocessing_pipeline.append(step)
        self.save()
    
    def remove_last_preprocessing_step(self):
        """마지막 전처리 단계 제거"""
        if isinstance(self.preprocessing_pipeline, list) and len(self.preprocessing_pipeline) > 0:
            self.preprocessing_pipeline.pop()
            self.save()
    
    def clear_preprocessing_pipeline(self):
        """전처리 파이프라인 초기화"""
        self.preprocessing_pipeline = []
        self.save()
    
    def get_pipeline_display(self):
        """파이프라인을 읽기 쉬운 형식으로 반환"""
        if not self.preprocessing_pipeline:
            return []
        
        display_names = {
            'harris_corner': 'Harris Corner Detection',
            'gaussian_blur': 'Gaussian Blur',
            'canny_edge': 'Canny Edge Detection',
            'median_blur': 'Median Blur',
            'gray_scale': 'Grayscale',
            'sobel_edge': 'Sobel Edge Detection',
            'threshold': 'Binary Threshold',
            'adaptive_threshold': 'Adaptive Threshold',
            'morphology_open': 'Morphological Opening',
            'morphology_close': 'Morphological Closing',
        }
        
        result = []
        for step in self.preprocessing_pipeline:
            step_type = step.get('type', '')
            display_name = display_names.get(step_type, step_type)
            
            params = step.get('params', {})
            if params:
                param_str = ', '.join([f"{k}={v}" for k, v in params.items()])
                display_name = f"{display_name} ({param_str})"
            
            result.append(display_name)
        
        return result
    
    def get_status_display_badge(self):
        """상태 배지 색상 반환"""
        status_colors = {
            'ready': 'secondary',
            'processing': 'primary',
            'completed': 'success',
            'failed': 'danger',
        }
        return status_colors.get(self.status, 'secondary')
    
    def delete_files(self):
        """분석 결과 파일 삭제"""
        import os
        import shutil
        from django.conf import settings
        
        deleted_files = []
        
        # 출력 파일 삭제
        if self.output_video_path:
            try:
                # 전처리 생략한 경우 원본 파일 경로일 수 있으므로 체크
                media = self.get_media()
                if media and self.output_video_path != media.file.name:
                    path = os.path.join(settings.BASE_DIR, 'media', self.output_video_path)
                    if os.path.exists(path):
                        os.remove(path)
                        deleted_files.append(path)
            except Exception as e:
                print(f"파일 삭제 실패: {e}")
        
        # 분석 결과 폴더 삭제
        result_dir = os.path.join(
            settings.BASE_DIR, 
            'media', 
            'analysis_results', 
            str(self.id)
        )
        if os.path.exists(result_dir):
            try:
                shutil.rmtree(result_dir)
                deleted_files.append(result_dir)
            except Exception as e:
                print(f"폴더 삭제 실패: {e}")
        
        return deleted_files