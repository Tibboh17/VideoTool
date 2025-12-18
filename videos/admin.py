from django.contrib import admin
from .models import Video, Image

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'file_size', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['title', 'description']

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'file_size', 'width', 'height', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['title', 'description']
    readonly_fields = ['file_size', 'width', 'height']