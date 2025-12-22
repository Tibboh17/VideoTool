# 목표
- 뷰를 CBV로 전환해 로직 재사용성과 확장성을 확보한다
- 기존 URL name/패턴, 템플릿 컨텍스트, 동작(모델 관리, 감지 실행, 스트리밍, 삭제)을 유지한다

# 변경 범위
- URL 라우팅: `detection/urls.py`
- View 구현: `detection/views.py`
- 템플릿: 기능상 변경 없음(컨텍스트 키는 유지)
- 모델 참고: `detection/models.py`

# 변경 요약

## 1. URL 라우팅 변경
기존 FBV 핸들러를 CBV `as_view()`로 교체했다. URL name/패턴은 동일하다
- `/detection/models/` → `DetectionModelListView`
- `/detection/models/add/` → `DetectionModelAddView`
- `/detection/models/<model_id>/` → `DetectionModelDetailView`
- `/detection/models/<model_id>/delete/` → `DetectionModelDeleteView`
- `/detection/start/<analysis_id>/` → `StartDetectionView`
- `/detection/<detection_id>/execute/` → `ExecuteDetectionView`
- `/detection/<detection_id>/progress/` → `DetectionProgressView`
- `/detection/<detection_id>/status/` → `DetectionStatusView`
- `/detection/<detection_id>/result/` → `DetectionResultView`
- `/detection/dashboard/` → `DetectionDashboardView`
- `/detection/<detection_id>/stream/` → `ServeDetectionVideoView`
- `/detection/<detection_id>/delete/` → `DetectionDeleteView`

## 2. FBV 제거

기존에 존재하던 다음 FBV들은 라우팅에서 더 이상 사용되지 않으므로 제거했다

- `model_list`
- `model_add`
- `model_detail`
- `model_delete`
- `start_detection`
- `execute_detection`
- `detection_progress`
- `detection_status`
- `detection_result`
- `detection_dashboard`
- `serve_detection_video`
- `detection_delete`

## 3. CBV 구현 목록 및 책임

### `DetectionModelListView`(ListView)
- 활성 모델 목록 + 통계(`total_models`, `yolo_models`, `custom_models`)

### `DetectionModelAddView`(View)
- 모델 추가
- 파일 저장 경로(`get_default_model_path`/`get_custom_model_path`) 처리, YOLO 기본 버전 옵션 제공, `conf_threshold`를 config에 저장

### `DetectionModelDetailView`(DetailView)
- 모델 정보 + 최근 감지 10개 + 통계(`total_detections`, `completed_detections`)

### `DetectionModelDeleteView`(DeleteView)
- 사용 중인 감지 작업 있으면 경고 후 중단하고 없으면 파일 삭제 후 모델 삭제

### `StartDetectionView`(View)
- 분석 완료 여부 확인 후 감지 작업 생성(모델 선택)

### `ExecuteDetectionView`(View)
- 감지 실행 트리거(스레드로 `process_detection` 시작) 후 진행 화면으로 이동

### `DetectionProgressView`(View)
- 진행 상황 페이지 렌더

### `DetectionStatusView`(View)
- 상태/프로그레스 JSON 반환

### `DetectionResultView`(View)
- 감지 결과 페이지 렌더(`detection.get_results()` 활용)

### `DetectionDashboardView`(TemplateView)
- 전체/상태별 통계, 최근 감지 10개, 모델별 통계 제공

### `ServeDetectionVideoView`(View)
- 감지 결과 비디오 스트리밍. Range 요청 206 처리, 없으면 전체 스트리밍
- MIME 기본 `video/mp4`

### `DetectionDeleteView`(DeleteView)
- 산출물 `delete_files()` 실행 후 감지 삭제
- `redirect` 값에 따라 `video_detail`/`image_detail`/`analysis_result`/`model_detail`/`detection_dashboard` 분기

## 4. 헬퍼/기타
- 모델 파일 삭제: `DetectionModel.delete_files()` 사용
- 감지 산출물 삭제: `Detection.delete_files()` 사용
- 감지 실행은 스레드 기반(`process_detection`)으로 기존 동작을 유지

# 템플릿/컨텍스트 호환
- 주요 컨텍스트 키를 유지  
  - 모델 목록/상세: `models`, `total_models`, `yolo_models`, `custom_models`, `model`, `detections`, `total_detections`, `completed_detections`  
  - 감지 실행/진행/결과: `analysis`, `models`, `detection`, `results`, `video`  
  - 대시보드: `total_detections`, `completed_detections`, `processing_detections`, `failed_detections`, `recent_detections`, `model_stats`
- 템플릿 경로는 기존 유지(`detection/templates/detection/*.html`)

# 관계 이름 참고
- `Analysis` <-> `Detection`: `Detection.analysis`의 `related_name='detections'`를 사용하므로 역참조는 `analysis.detections`
- 모델 파일 경로는 `model_path`(CharField)로 관리하며, `get_default_model_path`/`get_custom_model_path`를 통해 저장 경로를 계산

# 추후 개선
- 감지 실행을 Celery 등 비동기 큐로 전환하여 스레드 사용 최소화
- Range 없는 응답도 chunked 스트리밍으로 개선해 대용량 메모리 사용을 줄이기
- 모델 추가 로직을 `ModelForm`/서비스 계층으로 리팩터링하여 검증/저장을 분리
