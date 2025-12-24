from django.core.exceptions import ValidationError
import os

class ModelFileValidator:
    """모델 파일 검증"""
    
    ALLOWED_EXTENSIONS = ['.pt', '.pth', '.onnx', '.h5', '.pb']
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    
    def validate(self, file):
        """파일 검증"""
        self.validate_extension(file.name)
        self.validate_size(file.size)
    
    def validate_extension(self, filename):
        """확장자 검증"""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f'허용되지 않는 파일 형식입니다. '
                f'허용 형식: {", ".join(self.ALLOWED_EXTENSIONS)}'
            )
    
    def validate_size(self, size):
        """파일 크기 검증"""
        if size > self.MAX_FILE_SIZE:
            raise ValidationError(
                f'파일 크기는 {self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB를 '
                f'초과할 수 없습니다. (현재: {size / 1024 / 1024:.2f}MB)'
            )