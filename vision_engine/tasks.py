from django.utils import timezone
from .models import Detection
from .detector import VideoDetector
import os
from pathlib import Path
from django.conf import settings


def process_detection(detection_id):
    """탐지 작업 실행 (백그라운드)"""
    detection = None
    
    try:
        print(f"\n{'='*60}")
        print(f"🔍 탐지 작업 시작: ID={detection_id}")
        print(f"{'='*60}\n")
        
        detection = Detection.objects.get(id=detection_id)
        analysis = detection.analysis
        model = detection.get_model()
        
        if not model:
            raise ValueError("모델이 선택되지 않았습니다")
        
        # 상태 업데이트
        detection.status = 'processing'
        detection.started_at = timezone.now()
        detection.save()
        
        print(f"📹 분석 ID: {analysis.id}")
        print(f"🤖 모델: {detection.get_model_name()}")
        
        # 입력 파일 경로
        if not analysis.output_video_path:
            raise ValueError("전처리된 파일이 없습니다")
        
        input_path = os.path.join(settings.BASE_DIR, 'media', analysis.output_video_path)
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {input_path}")
        
        print(f"📂 입력: {input_path}")
        
        # 출력 경로 설정
        output_dir = Path('media/detection_results') / str(detection.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 원본 파일명 가져오기
        media_obj = getattr(analysis, 'video', None) or getattr(analysis, 'image', None)
        if media_obj and hasattr(media_obj, 'file') and media_obj.file:
            original_filename = os.path.basename(media_obj.file.name)
        else:
            original_filename = "detected_result.mp4"
        
        output_filename = f'detected_{original_filename}'
        output_path = output_dir / output_filename
        
        print(f"📤 출력: {output_path}")
        
        # 탐지 실행
        detector = VideoDetector(model)
        
        # 진행률 콜백
        def progress_callback(current, total, progress):
            detection.processed_frames = current
            detection.total_frames = total
            detection.progress = progress
            detection.save()
            print(f"⏳ 진행: {current}/{total} ({progress}%)")
        
        # 실행
        results = detector.process_video(
            input_path,
            str(output_path),
            progress_callback
        )
        
        # 결과 저장
        detection.save_results(results['detections'])
        detection.total_detections = results['total_detections']
        detection.detection_summary = results['summary']
        
        # 출력 경로 저장
        relative_path = output_path.relative_to('media')
        detection.output_video_path = str(relative_path).replace('\\', '/')
        
        # 모델 사용 횟수 증가
        model.increment_usage()
        
        # 완료
        detection.status = 'completed'
        detection.completed_at = timezone.now()
        detection.progress = 100
        detection.save()
        
        print(f"\n{'='*60}")
        print(f"✨ 탐지 완료!")
        print(f"   총 탐지: {detection.total_detections}")
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
