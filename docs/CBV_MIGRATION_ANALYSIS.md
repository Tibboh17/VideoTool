# 목표
- 뷰를 CBV로 전환해 로직 재사용성과 확장성을 확보한다.
- 기존 URL name/패턴, 템플릿 컨텍스트, 동작(비동기 실행, 파일/스트리밍 처리)을 유지한다.

# 변경 범위
- URL 라우팅: `analysis/urls.py`
- View 구현: `analysis/views.py`
- 템플릿: 기능상 변경 없음(컨텍스트 키는 유지)
- 모델 참고: `analysis/models.py` (`related_name='analyses'`)

# 변경 요약

## 1. URL 라우팅 변경

기존 FBV 핸들러를 CBV `as_view()`로 교체했다. URL name/패턴은 동일하다.
- `/analysis/start/<video_id>/` → `StartAnalysisView`
- `/analysis/<analysis_id>/add-step/` → `AddPreprocessingStepView`
- `/analysis/<analysis_id>/remove-step/` → `RemovePreprocessingStepView`
- `/analysis/<analysis_id>/execute/` → `ExecuteAnalysisView`
- `/analysis/<analysis_id>/progress/` → `AnalysisProgressView`
- `/analysis/<analysis_id>/status/` → `AnalysisStatusView`
- `/analysis/<analysis_id>/result/` → `AnalysisResultView`
- `/analysis/<analysis_id>/stream/` → `ServeAnalysisVideoView`
- `/analysis/analysis/<analysis_id>/image/` → `ServeAnalysisImageView`
- `/analysis/<analysis_id>/delete/` → `AnalysisDeleteView`

## 2. FBV 제거

기존에 존재하던 다음 FBV들은 라우팅에서 더 이상 사용되지 않으므로 제거했다.

- `start_analysis`
- `add_preprocessing_step`
- `remove_preprocessing_step`
- `execute_analysis`
- `analysis_progress`
- `analysis_status`
- `analysis_result`
- `serve_analysis_video`
- `serve_analysis_image`
- `analysis_delete`

## 3. CBV 구현 목록 및 책임

### `StartAnalysisView` (GET/POST)

- 전처리 선택 화면. 
- `skip_preprocessing=true` 시 Analysis를 `completed`로 만들고 결과/상세로 이동
- 준비 상태(`ready`)가 없으면 생성

### `AddPreprocessingStepView` / `RemovePreprocessingStepView`

- AJAX(JSON)로 전처리 스텝 추가/삭제 후 파이프라인을 JSON으로 반환

### `ExecuteAnalysisView`(POST)

- 비동기 분석 실행 트리거(`start_analysis_task`)
- 이미 `processing`이면 진행 화면으로 안내

### `AnalysisProgressView`(GET)

- 진행 상황 페이지. 미디어 없으면 `media_list`로 안내

### `AnalysisStatusView`(GET)

- 진행 상태 JSON(`status`, `progress`, `current_step`, `processed_frames`, `total_frames`, `error_message`)

### `AnalysisResultView`(GET)

- 결과 페이지
- 미디어 없으면 `media_list`로 안내

### `AnalysisDeleteView`(DeleteView)

- 산출물 `delete_files()` 실행 후 Analysis 삭제
- `redirect` 값에 따라 `video_detail`/`image_detail`/`media_list`로 분기

### `ServeAnalysisVideoView`(GET)

- 결과 비디오 스트리밍. Range 요청 206 처리, 없으면 전체 스트리밍
- MIME 기본 `video/mp4`

### `ServeAnalysisImageView`(GET)

- 결과 이미지 응답
- MIME 기본 `image/jpeg`

## 4. 헬퍼/기타
- 산출물 정리는 모델 메서드 `delete_files()`에 위임(비디오/결과 디렉터리 삭제)
- 전처리 파이프라인은 모델의 `add_preprocessing_step`, `remove_last_preprocessing_step` 사용

# 템플릿/컨텍스트 호환
- 컨텍스트 키: `analysis`, `media`, `media_type`, `preprocessing_methods`, `current_pipeline` 등 기존 키를 유지
- 템플릿 파일 경로는 변경 없음(`analysis/templates/analysis/*.html`)

# 관계 이름 참고
- `Analysis.video`/`Analysis.image`는 `related_name='analyses'`를 사용하므로 역참조는 `media.analyses`

# 추후 개선
- 공통 로직(파일 삭제/스트리밍)을 mixin 또는 서비스로 분리
- Range 없는 응답도 chunked 스트리밍으로 개선해 대용량 메모리 사용 최소화
- 메시지/문구 인코딩 정리(깨진 문자열이 있다면 UTF-8로 통일)