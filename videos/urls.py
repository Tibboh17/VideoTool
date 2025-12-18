from django.urls import path
from . import views

urlpatterns = [
    path('', views.VideoListView.as_view(), name='video_list'),
    path('upload/', views.VideoCreateView.as_view(), name='video_upload'),
    path('<int:pk>/', views.VideoDetailView.as_view(), name='video_detail'),
    path('<int:pk>/delete/', views.VideoDeleteView.as_view(), name='video_delete'),
    path('<int:pk>/stream/', views.VideoStreamView.as_view(), name='serve_video'), 
]
