from django.urls import path
from . import views

urlpatterns = [
    # 분석 시작 (전처리 선택)
    path('start/<int:video_id>/', views.StartAnalysisView.as_view(), name='start_analysis'),

    # 전처리 파이프라인 추가/제거 (AJAX)
    path('<int:analysis_id>/add-step/', views.AddPreprocessingStepView.as_view(), name='add_preprocessing_step'),
    path('<int:analysis_id>/remove-step/', views.RemovePreprocessingStepView.as_view(), name='remove_preprocessing_step'),

    # 분석 실행
    path('<int:analysis_id>/execute/', views.ExecuteAnalysisView.as_view(), name='execute_analysis'),

    # 진행 상황
    path('<int:analysis_id>/progress/', views.AnalysisProgressView.as_view(), name='analysis_progress'),
    path('<int:analysis_id>/status/', views.AnalysisStatusView.as_view(), name='analysis_status'),

    # 결과
    path('<int:analysis_id>/result/', views.AnalysisResultView.as_view(), name='analysis_result'),

    # 결과 스트리밍
    path('<int:analysis_id>/stream/', views.ServeAnalysisVideoView.as_view(), name='serve_analysis_video'),

    # 결과 이미지 제공
    path('analysis/<int:analysis_id>/image/', views.ServeAnalysisImageView.as_view(), name='serve_analysis_image'),

    # 분석 삭제
    path('<int:analysis_id>/delete/', views.AnalysisDeleteView.as_view(), name='analysis_delete'),
]
