from django.db import models
from videos.models import Video
import json, os

class Analysis(models.Model):
    STATUS_CHOICES = [
        ('ready', '준비'),
        ('processing', '처리 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]
    
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE, 
        related_name='analyses',
        verbose_name='동영상'
        )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
    
    # 전처리 파이프라인 (JSON으로 저장)
    preprocessing_pipeline = models.JSONField(default=list, blank=True)
    # 예: [{"type": "harris_corner", "params": {...}}, {"type": "gaussian_blur", "params": {...}}]
    
    # 진행률
    progress = models.IntegerField(default=0)  # 0-100
    current_step = models.CharField(max_length=100, blank=True)
    
    # 결과
    output_video_path = models.CharField(max_length=500, blank=True)  # 처리된 영상 경로
    result_frames_dir = models.CharField(max_length=500, blank=True)  # 프레임 저장 폴더
    
    # 통계
    total_frames = models.IntegerField(default=0)
    processed_frames = models.IntegerField(default=0)
    
    # 시간
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Analysis for {self.video.title} - {self.get_status_display()}"
    
    def add_preprocessing_step(self, step_type, params=None):
        """전처리 단계 추가"""
        step = {
            'type': step_type,
            'params': params or {}
        }
        pipeline = self.preprocessing_pipeline or []
        pipeline.append(step)
        self.preprocessing_pipeline = pipeline
        self.save()
    
    def remove_last_step(self):
        """마지막 전처리 단계 제거"""
        if self.preprocessing_pipeline:
            self.preprocessing_pipeline.pop()
            self.save()
    
    def get_pipeline_display(self):
        """파이프라인을 읽기 쉽게 표시"""
        pipeline = self.preprocessing_pipeline or []
        return [step['type'] for step in pipeline]
    
    def delete_files(self):
        """관련 파일 삭제"""
        
        from django.conf import settings
        import shutil
        
        deleted_files = []
        
        # 출력 동영상 삭제
        if self.output_video_path:
            try:
                path = os.path.join(settings.BASE_DIR, 'media', self.output_video_path)
                if os.path.exists(path):
                    os.remove(path)
                    deleted_files.append(path)
                    print(f"✅ 파일 삭제: {path}")
            except Exception as e:
                print(f"⚠️  파일 삭제 실패: {e}")
        
        # 결과 폴더 전체 삭제
        result_dir = os.path.join(settings.BASE_DIR, 'media', 'analysis_results', str(self.id))
        if os.path.exists(result_dir):
            try:
                shutil.rmtree(result_dir)
                deleted_files.append(result_dir)
                print(f"✅ 폴더 삭제: {result_dir}")
            except Exception as e:
                print(f"⚠️  폴더 삭제 실패: {e}")
        
        return deleted_files