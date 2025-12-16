from django import forms
from .models import Video

class VideoUploadForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['title', 'description', 'file', 'thumbnail']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '동영상 제목을 입력하세요'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '동영상 설명을 입력하세요 (선택사항)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # 파일 크기 체크 (1GB 제한)
            if file.size > 1024 * 1024 * 1024:
                raise forms.ValidationError('파일 크기는 1GB를 초과할 수 없습니다.')
        return file