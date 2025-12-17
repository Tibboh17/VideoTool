from django.contrib import admin
from .models import Video

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_at', 'file_size', 'get_file_size_display']
    list_filter = ['uploaded_at']
    search_fields = ['title', 'description']
    readonly_fields = ['uploaded_at', 'file_size']