from django.utils import timezone
from .models import Analysis
import os
from pathlib import Path
import traceback

def process_video_analysis(analysis_id):
    """동영상 분석 실행"""
    analysis = None
    try:
        print(f"\n{'='*50}")
        print(f"🎬 분석 시작: ID={analysis_id}")
        
        analysis = Analysis.objects.get(id=analysis_id)
        video = analysis.video
        
        # 상태 업데이트
        analysis.status = 'processing'
        analysis.started_at = timezone.now()
        analysis.current_step = '전처리 시작'
        analysis.save()
        
        # 입력 동영상 경로
        video_path = video.file.path
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"동영상 파일을 찾을 수 없습니다")
        
        # 출력 경로 설정
        output_dir = Path('media/analysis_results') / str(analysis.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 이름 정리 (특수문자 제거)
        original_name = video.file.name.split("/")[-1]
        clean_name = "".join(c for c in original_name if c.isalnum() or c in '.-_')
        output_filename = f'processed_{clean_name}'
        
        # 확장자를 .mp4로 강제
        output_filename = Path(output_filename).stem + '.mp4'
        output_video_path = output_dir / output_filename
        
        print(f"📤 출력 경로: {output_video_path}")
        
        # 전처리기 생성
        from .preprocessing import VideoPreprocessor
        preprocessor = VideoPreprocessor()
        
        # 진행률 콜백
        def progress_callback(current, total, progress):
            analysis.processed_frames = current
            analysis.total_frames = total
            analysis.progress = progress
            
            if progress < 85:
                analysis.current_step = f'프레임 처리 중: {current}/{total}'
            elif progress < 95:
                analysis.current_step = 'ffmpeg 재인코딩 중...'
            else:
                analysis.current_step = '완료 중...'
            
            analysis.save()
            
            if current % 30 == 0:
                print(f"⏳ 진행률: {progress}%")
        
        # 파이프라인 실행
        pipeline = analysis.preprocessing_pipeline or []
        
        if not pipeline:
            # 파이프라인이 비어있으면 원본 복사
            import shutil
            shutil.copy(video_path, output_video_path)
            analysis.total_frames = 1
            analysis.processed_frames = 1
        else:
            # 전처리 실행
            frame_count = preprocessor.process_video(
                video_path,
                pipeline,
                str(output_video_path),
                progress_callback
            )
        
        # 출력 파일 확인
        if not output_video_path.exists():
            raise FileNotFoundError(f"출력 파일이 생성되지 않았습니다")
        
        file_size = output_video_path.stat().st_size
        print(f"✅ 출력 파일: {file_size:,} bytes")
        
        # 경로를 forward slash로 변환
        relative_path = output_video_path.relative_to('media')
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
        import traceback
        traceback.print_exc()
        
        if analysis:
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.save()
        
        return False
