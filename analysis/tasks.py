from django.utils import timezone
from .models import Analysis
import os
from pathlib import Path
import traceback

def process_video_analysis(analysis_id):
    """동영상/이미지 분석 실행"""
    analysis = None
    try:
        print(f"\n{'='*50}")
        print(f"🎬 분석 시작: ID={analysis_id}")
        
        analysis = Analysis.objects.get(id=analysis_id)
        
        # ⭐ 미디어 가져오기 (video 또는 image)
        media = analysis.get_media()
        media_type = analysis.get_media_type()
        
        if not media:
            raise ValueError("미디어를 찾을 수 없습니다")
        
        print(f"📦 미디어 타입: {media_type}")
        print(f"📄 파일명: {media.title}")
        
        # 상태 업데이트
        analysis.status = 'processing'
        analysis.started_at = timezone.now()
        analysis.current_step = '전처리 시작'
        analysis.save()
        
        # 입력 파일 경로
        input_path = media.file.path
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {input_path}")
        
        # 출력 경로 설정
        output_dir = Path('media/analysis_results') / str(analysis.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 이름 정리 (특수문자 제거)
        original_name = media.file.name.split("/")[-1]
        clean_name = "".join(c for c in original_name if c.isalnum() or c in '.-_')
        
        # ⭐ 미디어 타입에 따라 확장자 결정
        if media_type == 'image':
            output_filename = Path(clean_name).stem + '_processed.jpg'
        else:
            output_filename = Path(clean_name).stem + '_processed.mp4'
        
        output_path = output_dir / output_filename
        
        print(f"📤 출력 경로: {output_path}")
        
        # 전처리기 생성
        from .preprocessing import VideoPreprocessor
        preprocessor = VideoPreprocessor()
        
        # 진행률 콜백
        def progress_callback(current, total, progress):
            analysis.processed_frames = current
            analysis.total_frames = total
            analysis.progress = progress
            
            if media_type == 'image':
                if progress < 90:
                    analysis.current_step = f'이미지 처리 중: {current}/{total}'
                else:
                    analysis.current_step = '완료 중...'
            else:
                if progress < 85:
                    analysis.current_step = f'프레임 처리 중: {current}/{total}'
                elif progress < 95:
                    analysis.current_step = 'ffmpeg 재인코딩 중...'
                else:
                    analysis.current_step = '완료 중...'
            
            analysis.save()
            
            if current % 30 == 0 or media_type == 'image':
                print(f"⏳ 진행률: {progress}%")
        
        # 파이프라인 실행
        pipeline = analysis.preprocessing_pipeline or []
        
        if not pipeline:
            # 파이프라인이 비어있으면 원본 복사
            import shutil
            shutil.copy(input_path, output_path)
            analysis.total_frames = 1
            analysis.processed_frames = 1
        else:
            # ⭐ 미디어 타입에 따라 다른 처리
            if media_type == 'image':
                # 이미지 전처리
                preprocessor.process_image(
                    input_path,
                    pipeline,
                    str(output_path),
                    progress_callback
                )
            else:
                # 동영상 전처리
                preprocessor.process_video(
                    input_path,
                    pipeline,
                    str(output_path),
                    progress_callback
                )
        
        # 출력 파일 확인
        if not output_path.exists():
            raise FileNotFoundError(f"출력 파일이 생성되지 않았습니다: {output_path}")
        
        file_size = output_path.stat().st_size
        print(f"✅ 출력 파일: {file_size:,} bytes")
        
        # 경로를 forward slash로 변환
        relative_path = output_path.relative_to('media')
        relative_path_str = str(relative_path).replace('\\', '/')
        
        print(f"💾 저장 경로: {relative_path_str}")
        
        # 완료 처리
        analysis.status = 'completed'
        analysis.completed_at = timezone.now()
        analysis.progress = 100
        analysis.output_video_path = relative_path_str
        analysis.current_step = '완료'
        analysis.save()
        
        print(f"✨ 분석 완료!")
        
        return True
        
    except Exception as e:
        print(f"❌ 에러: {e}")
        traceback.print_exc()
        
        if analysis:
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.current_step = '실패'
            analysis.save()
        
        return False


def start_analysis_task(analysis_id):
    """분석 작업을 백그라운드에서 시작"""
    import threading
    thread = threading.Thread(target=process_video_analysis, args=(analysis_id,))
    thread.daemon = True
    thread.start()