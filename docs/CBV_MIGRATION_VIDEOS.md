# 목표

- 뷰 로직을 CBV로 전환하여 재사용성과 확장성을 높인다
- 기존 URL name/템플릿/화면 동작(업로드→썸네일 생성, 삭제 시 파일 삭제, 스트리밍 Range 처리)을 최대한 유지한다

# 변경 범위

- URL 라우팅: `videos/urls.py`
- View 구현: `videos/views.py`
- 템플릿 일부 수정
  - `videos/templates/videos/video_list.html`
  - `videos/templates/videos/video_detail.html`

# 변경 요약

## 1. URL 라우팅 변경

기존 FBV 핸들러를 CBV `as_view()`로 교체했다. URL name은 변경하지 않았다

- `/videos/` → `VideoListView` (`video_list`)
- `/videos/upload/` → `VideoCreateView` (`video_upload`)
- `/videos/<pk>/` → `VideoDetailView` (`video_detail`)
- `/videos/<pk>/delete/` → `VideoDeleteView` (`video_delete`)
- `/videos/<pk>/stream/` → `VideoStreamView` (`serve_video`)

## 2. FBV 제거

기존에 존재하던 다음 FBV들은 라우팅에서 더 이상 사용되지 않으므로 제거했다

- `video_list`
- `video_upload`
- `video_detail`
- `video_delete`
- `serve_video`

## 3. CBV 구현 목록 및 책임

### `VideoListView (ListView)`

- 목록 조회 + 검색 처리
- `GET ?search=...`가 있으면 `title__icontains`로 필터링
- 페이지네이션 적용(`paginate_by = 9`)
- 템플릿 호환을 위해 컨텍스트의 `videos`에 `page_obj`를 재할당(템플릿이 Page 객체 메서드를 사용)
- 컨텍스트에 `search` 값을 제공

### `VideoCreateView (CreateView)`

- 업로드 폼 처리(`VideoUploadForm`)
- 저장 플로우(기존 동작 유지)
  1) `file_size` 저장
  2) 1차 `save()`로 파일 경로 확보
  3) `generate_thumbnail(video.file.path)`로 썸네일 생성
  4) 썸네일 저장 후 최종 `save()`
- 성공 시 `video_detail(pk)`로 redirect
- 성공/실패 메시지(`messages`) 표시

### `VideoDetailView (DetailView)`

- 비디오 상세 페이지 렌더링
- 템플릿에서 분석/감지 정보를 사용하므로, 조회 최적화를 위해 `prefetch_related` 적용
  - `analyses`
  - `analyses__detections`
  - `analyses__detections__model`

> 관계 이름은 `Analysis.video`의 `related_name='analyses'`에 의해 결정된다

### `VideoDeleteView (DeleteView)`

- 삭제 확인 페이지 + 삭제 처리
- 삭제 시 실제 파일 삭제(비디오/썸네일) 후 DB 삭제 수행
- 삭제 성공 메시지 표시 후 목록으로 이동

### `VideoStreamView (View)`

- HTML `<video>` 태그에서 사용하는 스트리밍 엔드포인트
- Range Request(Seek) 지원:
  - `HTTP_RANGE`를 파싱하여 206 Partial Content로 응답
  - `Content-Range`, `Accept-Ranges`, `Content-Length` 헤더 설정
- Range가 없을 때는 `FileResponse`로 스트리밍
- MIME 타입은 `mimetypes.guess_type()`으로 추정, 없으면 `video/mp4`를 사용

## 4. 썸네일 생성 헬퍼 유지

- `generate_thumbnail(video_path)`는 기존처럼 `ffmpeg`로 프레임 1장을 추출하여 PIL로 리사이즈 후 JPEG `ContentFile`을 반환한다

# 템플릿 변경 사항

## `video_list.html`

- 페이지네이션 링크에서 검색어가 유지되도록 `search` 쿼리스트링을 추가했다
  - 예: `?page=2&search=...`

# 추후 개선(옵션)

- 메시지 문자열/템플릿 한글 인코딩 정리(깨진 문자열이 있다면 UTF-8로 통일)
- 공통 로직(파일 삭제/썸네일 생성)을 mixin 또는 서비스 함수로 분리