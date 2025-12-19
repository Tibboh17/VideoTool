from django.urls import path
from . import views

urlpatterns = [
    # 모델 관리
    path('models/', views.DetectionModelListView.as_view(), name='detection_model_list'),
    path('models/add/', views.DetectionModelAddView.as_view(), name='detection_model_add'),
    path('models/<int:model_id>/', views.DetectionModelDetailView.as_view(), name='detection_model_detail'),
    path('models/<int:model_id>/delete/', views.DetectionModelDeleteView.as_view(), name='detection_model_delete'),

    # 감지 실행
    path('start/<int:analysis_id>/', views.StartDetectionView.as_view(), name='start_detection'),
    path('<int:detection_id>/execute/', views.ExecuteDetectionView.as_view(), name='execute_detection'),
    path('<int:detection_id>/progress/', views.DetectionProgressView.as_view(), name='detection_progress'),
    path('<int:detection_id>/status/', views.DetectionStatusView.as_view(), name='detection_status'),
    path('<int:detection_id>/result/', views.DetectionResultView.as_view(), name='detection_result'),

    # 대시보드
    path('dashboard/', views.DetectionDashboardView.as_view(), name='detection_dashboard'),

    # 결과 스트리밍
    path('<int:detection_id>/stream/', views.ServeDetectionVideoView.as_view(), name='serve_detection_video'),

    # 삭제
    path('<int:detection_id>/delete/', views.DetectionDeleteView.as_view(), name='detection_delete'),
]
