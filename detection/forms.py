import os

from django import forms
from django.core.exceptions import ValidationError

from .models import DetectionModel

class DetectionModelForm(forms.ModelForm):
    class Meta:
        model = DetectionModel
        fields = ['name', 'model_type', 'description', 'model_file', 'yolo_version', 'config']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'model_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'model_file': forms.FileInput(attrs={'class': 'form-control'}),
            'yolo_version': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_model_file(self):
        file = self.cleaned_data.get('model_file')
        
        if file:
            # 파일 크기 체크 (500MB)
            max_size = 500 * 1024 * 1024
            if file.size > max_size:
                raise ValidationError(
                    f'모델 파일 크기는 500MB를 초과할 수 없습니다. '
                    f'(현재: {file.size / 1024 / 1024:.2f}MB)'
                )
            
            # 파일 확장자 검증
            ext = os.path.splitext(file.name)[1].lower()
            allowed_extensions = ['.pt', '.pth', '.onnx', '.h5', '.pb']
            
            if ext not in allowed_extensions:
                raise ValidationError(
                    f'허용되지 않는 파일 형식입니다. '
                    f'허용 형식: {", ".join(allowed_extensions)}'
                )
        
        return file
    
    def clean(self):
        cleaned_data = super().clean()
        model_type = cleaned_data.get('model_type')
        model_file = cleaned_data.get('model_file')
        yolo_version = cleaned_data.get('yolo_version')
        
        # YOLO 타입이면 파일 또는 버전 중 하나는 있어야 함
        if model_type == 'yolo':
            if not model_file and not yolo_version:
                raise ValidationError(
                    'YOLO 모델은 파일을 업로드하거나 버전을 지정해야 합니다.'
                )
        
        # Custom 타입이면 파일이 필수
        if model_type == 'custom' and not model_file:
            raise ValidationError('커스텀 모델은 파일 업로드가 필수입니다.')
        
        return cleaned_data