from django.db import models
from django.utils import timezone
from analysis.models import Analysis
import json


class Detection(models.Model):
    """객체 탐지 작업"""
    
    STATUS_CHOICES = [
        ('ready', '대기'),
        ('processing', '처리 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]
    
    # 연결
    analysis = models.ForeignKey(
        Analysis,
        on_delete=models.CASCADE,
        related_name='detections',
        verbose_name='분석'
    )
    
    # 모델 선택 (modelhub의 BaseModel 또는 CustomModel)
    base_model = models.ForeignKey(
        'modelhub.BaseModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='기본 모델'
    )
    custom_model = models.ForeignKey(
        'modelhub.CustomModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='커스텀 모델'
    )
    
    # 기본 정보
    title = models.CharField(max_length=200, verbose_name='제목')
    description = models.TextField(blank=True, verbose_name='설명')
    
    # 실행 상태
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ready',
        verbose_name='상태'
    )
    
    # 진행률
    total_frames = models.IntegerField(default=0, verbose_name='총 프레임')
    processed_frames = models.IntegerField(default=0, verbose_name='처리된 프레임')
    progress = models.IntegerField(default=0, verbose_name='진행률 (%)')
    
    # 결과
    output_video_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='결과 동영상 경로'
    )
    detection_data = models.JSONField(
        default=list,
        blank=True,
        verbose_name='탐지 데이터'
    )
    total_detections = models.IntegerField(default=0, verbose_name='총 탐지 수')
    detection_summary = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='탐지 요약'
    )
    
    # 에러
    error_message = models.TextField(blank=True, verbose_name='에러 메시지')
    
    # 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='시작 시간')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='완료 시간')
    
    class Meta:
        verbose_name = '객체 탐지'
        verbose_name_plural = '객체 탐지들'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def get_model(self):
        """사용된 모델 반환"""
        if self.base_model:
            return self.base_model
        return self.custom_model
    
    def get_model_name(self):
        """모델 이름 반환"""
        model = self.get_model()
        if model:
            if hasattr(model, 'display_name'):
                return model.display_name
            return model.name
        return "모델 없음"
    
    def save_results(self, detections):
        """탐지 결과 저장"""
        self.detection_data = detections
        self.save()
    
    def get_duration(self):
        """실행 시간 계산"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return 0
    
    def get_duration_display(self):
        """실행 시간 표시"""
        duration = self.get_duration()
        if duration == 0:
            return "-"
        
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        if minutes > 0:
            return f"{minutes}분 {seconds}초"
        return f"{seconds}초"
