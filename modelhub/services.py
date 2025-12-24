import os
import shutil
from django.conf import settings
from django.core.files.storage import default_storage
from pathlib import Path
from .models import DetectionModel
from .validators import ModelFileValidator

class ModelService:
    """모델 관리 서비스"""
    
    @staticmethod
    def upload_model(file, model_type, name):
        """모델 파일 업로드"""
        validator = ModelFileValidator()
        validator.validate(file)
        
        # 저장 경로 결정
        if model_type == 'yolo':
            save_dir = Path(settings.MODELS_ROOT) / 'default'
        else:
            save_dir = Path(settings.MODELS_ROOT) / 'custom'
        
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 저장
        filename = f"{name}_{file.name}"
        filepath = save_dir / filename
        
        with open(filepath, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        return str(filepath.relative_to(settings.MODELS_ROOT))
    
    @staticmethod
    def download_yolo_model(version):
        """YOLO 기본 모델 다운로드"""
        from ultralytics import YOLO
        
        # YOLO 모델 다운로드 (자동으로 캐시됨)
        model = YOLO(version)
        
        return f"Downloaded {version}"
    
    @staticmethod
    def validate_model(model_id):
        """모델 검증"""
        try:
            model = DetectionModel.objects.get(id=model_id)
            model_path = model.get_model_path()
            
            if not os.path.exists(model_path):
                return False, "모델 파일을 찾을 수 없습니다"
            
            # 추가 검증 로직...
            return True, "검증 성공"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def export_model(model_id, format='onnx'):
        """모델 포맷 변환"""
        # 필요시 구현 예정
        pass