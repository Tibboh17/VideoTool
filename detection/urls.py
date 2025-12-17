from django.urls import path
from . import views

urlpatterns = [
    # 모델 관리
    path('models/', views.model_list, name='detection_model_list'),
    path('models/add/', views.model_add, name='detection_model_add'),
    path('models/<int:model_id>/', views.model_detail, name='detection_model_detail'),
    path('models/<int:model_id>/delete/', views.model_delete, name='detection_model_delete'),
    
    # 감지 작업
    path('start/<int:analysis_id>/', views.start_detection, name='start_detection'),
    path('<int:detection_id>/execute/', views.execute_detection, name='execute_detection'),
    path('<int:detection_id>/progress/', views.detection_progress, name='detection_progress'),
    path('<int:detection_id>/status/', views.detection_status, name='detection_status'),
    path('<int:detection_id>/result/', views.detection_result, name='detection_result'),
    
    # 대시보드
    path('dashboard/', views.detection_dashboard, name='detection_dashboard'),
    
    # 결과 동영상 스트리밍
    path('<int:detection_id>/stream/', views.serve_detection_video, name='serve_detection_video'),
    
    # 관리
    path('<int:detection_id>/delete/', views.detection_delete, name='detection_delete'),
]