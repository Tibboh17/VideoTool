from django.urls import path
from . import views

urlpatterns = [
    # 통합 미디어 목록
    path('', views.MediaListView.as_view(), name='video_list'),  # 호환성
    path('', views.MediaListView.as_view(), name='media_list'),
    
    # 통합 업로드
    path('upload/', views.MediaUploadView.as_view(), name='video_upload'),  # 호환성
    path('upload/', views.MediaUploadView.as_view(), name='upload_media'),
    
    # 동영상 관련
    path('video/<int:pk>/', views.VideoDetailView.as_view(), name='video_detail'),
    path('video/<int:pk>/delete/', views.VideoDeleteView.as_view(), name='video_delete'),
    path('video/<int:pk>/stream/', views.VideoStreamView.as_view(), name='serve_video'),
    
    # 이미지 관련
    path('image/<int:pk>/', views.ImageDetailView.as_view(), name='image_detail'),
    path('image/<int:pk>/delete/', views.ImageDeleteView.as_view(), name='image_delete'),
]