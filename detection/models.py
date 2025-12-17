from django.db import models
from analysis.models import Analysis
import json
import os
from pathlib import Path

class DetectionModel(models.Model):
    """감지/분류 모델 정의"""
    MODEL_TYPES = [
        ('yolo', 'YOLO (객체 감지)'),
        ('custom', 'Custom Model'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='모델 이름')
    model_type = models.CharField(max_length=50, choices=MODEL_TYPES, verbose_name='모델 타입')
    description = models.TextField(blank=True, verbose_name='설명')
    
    # ⭐ 모델 파일 업로드
    model_file = models.FileField(
        upload_to='detection_models/', 
        blank=True, 
        null=True, 
        verbose_name='모델 파일',
        help_text='YOLO: .pt 파일, Custom: .pt, .pth, .onnx 등'
    )
    
    # 모델 설정
    config = models.JSONField(default=dict, blank=True, verbose_name='모델 설정')
    
    # YOLO 기본 모델 (파일 업로드 없이 사용)
    yolo_version = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name='YOLO 버전',
        help_text='예: yolov8n.pt, yolov8s.pt, yolov8m.pt'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='활성화')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    class Meta:
        verbose_name = '감지 모델'
        verbose_name_plural = '감지 모델들'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"
    
    def get_model_path(self):
        """모델 파일 경로 반환"""
        if self.model_file:
            return self.model_file.path
        elif self.yolo_version:
            # YOLO 기본 모델은 ultralytics가 자동 다운로드
            return self.yolo_version
        return None
    
    def get_file_size(self):
        """모델 파일 크기"""
        if self.model_file and os.path.exists(self.model_file.path):
            return os.path.getsize(self.model_file.path)
        return 0
    
    def get_file_size_display(self):
        """모델 파일 크기 (읽기 쉬운 형식)"""
        size = self.get_file_size()
        if size == 0:
            return "기본 모델" if self.yolo_version else "-"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def delete_files(self):
        """모델 파일 삭제"""
        deleted_files = []
        
        if self.model_file:
            try:
                if os.path.exists(self.model_file.path):
                    os.remove(self.model_file.path)
                    deleted_files.append(self.model_file.path)
                    print(f"✅ 모델 파일 삭제: {self.model_file.path}")
            except Exception as e:
                print(f"⚠️  모델 파일 삭제 실패: {e}")
        
        return deleted_files


class Detection(models.Model):
    """감지 작업"""
    STATUS_CHOICES = [
        ('ready', '준비'),
        ('processing', '처리 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]
    
    analysis = models.ForeignKey(
        Analysis, 
        on_delete=models.CASCADE, 
        related_name='detections', 
        verbose_name='분석'
    )
    model = models.ForeignKey(
        DetectionModel, 
        on_delete=models.PROTECT, 
        verbose_name='사용 모델'
    )
    
    title = models.CharField(max_length=200, blank=True, verbose_name='제목')
    description = models.TextField(blank=True, verbose_name='설명')
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ready', 
        verbose_name='상태'
    )
    progress = models.IntegerField(default=0, verbose_name='진행률')
    
    # 처리 정보
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='시작 시간')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='완료 시간')
    processed_frames = models.IntegerField(default=0, verbose_name='처리된 프레임')
    total_frames = models.IntegerField(default=0, verbose_name='총 프레임')
    
    # 결과 저장
    results_json = models.TextField(blank=True, verbose_name='결과 JSON')
    output_video_path = models.CharField(
        max_length=500, 
        blank=True, 
        verbose_name='출력 동영상 경로'
    )
    
    # 통계
    total_detections = models.IntegerField(default=0, verbose_name='총 감지 수')
    detection_summary = models.JSONField(
        default=dict, 
        blank=True,
        verbose_name='감지 요약'
    )
    
    # 에러
    error_message = models.TextField(blank=True, verbose_name='에러 메시지')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    class Meta:
        verbose_name = '감지 작업'
        verbose_name_plural = '감지 작업들'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Detection #{self.id} - {self.analysis.video.title}"
    
    def get_results(self):
        """JSON 결과 파싱"""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except:
                return []
        return []
    
    def save_results(self, results):
        """결과를 JSON으로 저장"""
        self.results_json = json.dumps(results, ensure_ascii=False)
    
    def get_status_display_badge(self):
        """상태 배지 색상"""
        status_colors = {
            'ready': 'secondary',
            'processing': 'primary',
            'completed': 'success',
            'failed': 'danger',
        }
        return status_colors.get(self.status, 'secondary')
    
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
            except Exception as e:
                print(f"파일 삭제 실패: {e}")
        
        # 결과 폴더 삭제
        result_dir = os.path.join(
            settings.BASE_DIR, 
            'media', 
            'detection_results', 
            str(self.id)
        )
        if os.path.exists(result_dir):
            try:
                shutil.rmtree(result_dir)
                deleted_files.append(result_dir)
            except Exception as e:
                print(f"폴더 삭제 실패: {e}")
        
        return deleted_files