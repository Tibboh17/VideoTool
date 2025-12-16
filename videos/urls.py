from django.urls import path
from . import views

urlpatterns = [
    path('', views.video_list, name='video_list'),
    path('upload/', views.video_upload, name='video_upload'),
    path('<int:pk>/', views.video_detail, name='video_detail'),
    path('<int:pk>/delete/', views.video_delete, name='video_delete'),
    path('<int:pk>/stream/', views.serve_video, name='serve_video'), 
]