import cv2
import numpy as np
from pathlib import Path
import os
import subprocess
from django.conf import settings

class VideoDetector:
    """동영상 및 이미지 객체 감지 처리 (YOLO 기반)"""
    
    def __init__(self, model):
        self.model = model
        self.model_type = model.model_type
        self.yolo_model = None
        
        # YOLO 모델 로드
        if self.model_type == 'yolo':
            self.load_yolo_model()
    
    def load_yolo_model(self):
        """YOLO 모델 로드 로직 (기존 유지)"""
        try:
            from ultralytics import YOLO
            model_path = self.model.get_model_path()
            if not model_path:
                raise ValueError("모델 파일이 지정되지 않았습니다")
            
            print(f"🔄 YOLO 모델 로딩 중: {model_path}")
            self.yolo_model = YOLO(model_path)
            print(f"✅ YOLO 모델 로드 완료")
        except Exception as e:
            print(f"❌ YOLO 모델 로드 실패: {e}")
            raise

    def detect_frame(self, frame):
        """단일 프레임 감지 분기"""
        if self.model_type == 'yolo':
            return self.detect_yolo(frame)
        return []

    def detect_yolo(self, frame):
        """YOLO 객체 감지 로직 (채널 오류 수정 포함)"""
        if not self.yolo_model:
            return []
        
        try:
            # ⭐ [수정] 4채널(RGBA) 이미지가 들어올 경우 3채널(BGR)로 변환
            if len(frame.shape) == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            results = self.yolo_model(frame, verbose=False)
            detections = []
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    label = self.yolo_model.names[class_id]
                    
                    conf_threshold = self.model.config.get('conf_threshold', 0.25)
                    if confidence >= conf_threshold:
                        detections.append({
                            'label': label,
                            'confidence': confidence,
                            'bbox': [int(x1), int(y1), int(x2-x1), int(y2-y1)],
                        })
            return detections
        except Exception as e:
            print(f"⚠️  YOLO 감지 오류: {e}")
            return []

    def process_video(self, input_path, output_path, progress_callback=None):
        """동영상/이미지에 감지 모델 적용 및 결과 저장"""
        print(f"\n{'='*60}\n🔍 감지 처리 시작\n{'='*60}")
        
        # 1. 미디어 타입 판별
        is_image = input_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"파일을 열 수 없습니다: {input_path}")
        
        # 2. 미디어 정보 추출 (중요: VideoWriter 생성보다 먼저 실행)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if is_image:
            fps = 1
            total_frames = 1
        else:
            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"🖼️  해상도: {width}x{height} | FPS: {fps} | 총 프레임: {total_frames}")

        # 3. 출력 설정 분기
        out = None
        temp_output = output_path
        annotated_frame = None 

        if not is_image:
            # 동영상일 때만 임시 파일(temp_) 및 VideoWriter 생성
            temp_output = str(Path(output_path).parent / f'temp_{Path(output_path).name}')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
            if not out.isOpened():
                cap.release()
                raise ValueError("출력 VideoWriter 생성 실패")

        all_detections = []
        detection_summary = {}
        total_detections_count = 0
        frame_count = 0

        try:
            print(f"🔄 처리 중...")
            while True:
                ret, frame = cap.read()
                if not ret: break
                
                # 감지 수행 및 그리기
                detections = self.detect_frame(frame)
                annotated_frame = self.draw_detections(frame, detections)
                
                if not is_image and out:
                    out.write(annotated_frame)
                
                if detections:
                    all_detections.append({'frame': frame_count, 'detections': detections})
                    total_detections_count += len(detections)
                    for det in detections:
                        label = det['label']
                        detection_summary[label] = detection_summary.get(label, 0) + 1
                
                frame_count += 1
                if progress_callback and frame_count % 10 == 0:
                    progress = int((frame_count / total_frames) * 80)
                    progress_callback(frame_count, total_frames, progress)

        finally:
            cap.release()
            if out: out.release()

        # 4. 최종 저장 및 인코딩
        if is_image:
            if annotated_frame is not None:
                cv2.imwrite(output_path, annotated_frame)
                print(f"✅ 이미지 결과 저장 완료: {output_path}")
            ffmpeg_success = True
        else:
            print(f"\n🎬 동영상 재인코딩 시작...")
            if progress_callback: progress_callback(frame_count, total_frames, 85)
            ffmpeg_success = self.reencode_with_ffmpeg(temp_output, output_path)
            
            if ffmpeg_success and os.path.exists(temp_output):
                os.remove(temp_output)
            elif not ffmpeg_success:
                print(f"⚠️  ffmpeg 실패 - 원본 파일 이동 시도")
                if os.path.exists(output_path): os.remove(output_path)
                os.rename(temp_output, output_path)

        if progress_callback: progress_callback(frame_count, total_frames, 100)

        return {
            'detections': all_detections,
            'total_detections': total_detections_count,
            'summary': detection_summary,
        }

    def draw_detections(self, frame, detections):
        """감지 결과를 프레임에 그리기"""
        result = frame.copy()
        for det in detections:
            x, y, w, h = det['bbox']
            label = det['label']
            conf = det['confidence']
            color = self.get_color_for_label(label)
            cv2.rectangle(result, (x, y), (x+w, y+h), color, 2)
            text = f"{label} {conf:.2f}"
            cv2.putText(result, text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return result

    def get_color_for_label(self, label):
        """라벨별 색상 지정"""
        hash_val = hash(label)
        return (hash_val & 0xFF, (hash_val >> 8) & 0xFF, (hash_val >> 16) & 0xFF)

    def reencode_with_ffmpeg(self, input_path, output_path):
        """ffmpeg 인코딩 로직 (기존 유지)"""
        import shutil
        ffmpeg_path = shutil.which('ffmpeg') or r'C:\ffmpeg\bin\ffmpeg.exe'
        if not os.path.exists(ffmpeg_path): return False
        
        try:
            cmd = [ffmpeg_path, '-i', str(input_path), '-c:v', 'libx264', '-preset', 'fast', '-y', str(output_path)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            return os.path.exists(output_path)
        except:
            return False