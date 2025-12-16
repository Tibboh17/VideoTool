from django.urls import path
from . import views

urlpatterns = [
    # 분석 시작 (전처리 선택)
    path('start/<int:video_id>/', views.start_analysis, name='start_analysis'),
    
    # 전처리 단계 추가/제거 (AJAX)
    path('<int:analysis_id>/add-step/', views.add_preprocessing_step, name='add_preprocessing_step'),
    path('<int:analysis_id>/remove-step/', views.remove_preprocessing_step, name='remove_preprocessing_step'),
    
    # 분석 실행
    path('<int:analysis_id>/execute/', views.execute_analysis, name='execute_analysis'),
    
    # 진행 상황
    path('<int:analysis_id>/progress/', views.analysis_progress, name='analysis_progress'),
    path('<int:analysis_id>/status/', views.analysis_status, name='analysis_status'),
    
    # 결과
    path('<int:analysis_id>/result/', views.analysis_result, name='analysis_result'),

    # 결과 동영상 스트리밍
    path('<int:analysis_id>/stream/', views.serve_analysis_video, name='serve_analysis_video'),
]