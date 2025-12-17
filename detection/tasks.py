from django.utils import timezone
from .models import Detection
import os
from pathlib import Path

def process_detection(detection_id):
    """감지 작업 실행 (백그라운드)"""
    detection = None
    try:
        print(f"\n{'='*60}")
        print(f"🔍 감지 작업 시작: ID={detection_id}")
        print(f"{'='*60}\n")
        
        detection = Detection.objects.get(id=detection_id)
        analysis = detection.analysis
        model = detection.model
        
        # 상태 업데이트
        detection.status = 'processing'
        detection.started_at = timezone.now()
        detection.save()
        
        print(f"📹 분석 ID: {analysis.id}")
        print(f"🤖 모델: {model.name} ({model.model_type})")
        
        # 입력 동영상 경로 (전처리된 동영상)
        if not analysis.output_video_path:
            raise ValueError("전처리된 동영상이 없습니다")
        
        from django.conf import settings
        input_video_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)
        
        if not os.path.exists(input_video_path):
            raise FileNotFoundError(f"동영상 파일을 찾을 수 없습니다: {input_video_path}")
        
        print(f"📂 입력: {input_video_path}")
        
        # 출력 경로 설정
        output_dir = Path('media/detection_results') / str(detection.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = f'detected_{analysis.video.file.name.split("/")[-1]}'
        output_video_path = output_dir / output_filename
        
        print(f"📤 출력: {output_video_path}")
        
        # 모델 타입에 따라 처리
        from .detector import VideoDetector
        detector = VideoDetector(model)
        
        # 진행률 콜백
        def progress_callback(current, total, progress):
            detection.processed_frames = current
            detection.total_frames = total
            detection.progress = progress
            detection.save()
        
        # 감지 실행
        results = detector.process_video(
            input_video_path,
            str(output_video_path),
            progress_callback
        )
        
        # 결과 저장
        detection.save_results(results['detections'])
        detection.total_detections = results['total_detections']
        detection.detection_summary = results['summary']
        
        # 출력 경로 저장
        relative_path = output_video_path.relative_to('media')
        detection.output_video_path = str(relative_path).replace('\\', '/')
        
        # 완료 처리
        detection.status = 'completed'
        detection.completed_at = timezone.now()
        detection.progress = 100
        detection.save()
        
        print(f"\n{'='*60}")
        print(f"✨ 감지 완료!")
        print(f"   총 감지: {detection.total_detections}")
        print(f"   클래스: {len(detection.detection_summary)}")
        print(f"{'='*60}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()
        
        if detection:
            detection.status = 'failed'
            detection.error_message = str(e)
            detection.save()
        
        return False