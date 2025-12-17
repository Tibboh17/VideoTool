import cv2
import numpy as np
from pathlib import Path
import os
import subprocess
from django.conf import settings

class VideoDetector:
    """동영상 감지 처리 (YOLO 기본)"""
    
    def __init__(self, model):
        self.model = model
        self.model_type = model.model_type
        self.yolo_model = None
        
        # YOLO 모델 로드
        if self.model_type == 'yolo':
            self.load_yolo_model()
    
    def load_yolo_model(self):
        """YOLO 모델 로드"""
        try:
            from ultralytics import YOLO
            from ultralytics.utils import SETTINGS
            
            model_path = self.model.get_model_path()
            
            if not model_path:
                raise ValueError("모델 파일이 지정되지 않았습니다")
            
            print(f"🔄 YOLO 모델 로딩 중: {model_path}")
            
            # ⭐ YOLO 기본 모델의 경우
            if self.model.yolo_version and not self.model.model_path:
                # 기본 모델 디렉토리
                default_models_dir = getattr(
                    settings, 
                    'DEFAULT_MODELS_DIR', 
                    settings.MODELS_ROOT / 'default'
                )
                os.makedirs(default_models_dir, exist_ok=True)
                
                # 모델 파일 경로
                local_model_path = os.path.join(default_models_dir, self.model.yolo_version)
                
                # 이미 로컬에 있는지 확인
                if os.path.exists(local_model_path):
                    print(f"   ✅ 로컬 모델 사용: {local_model_path}")
                    self.yolo_model = YOLO(local_model_path)
                else:
                    print(f"   📥 모델 다운로드 중... → {default_models_dir}")
                    
                    # ⭐ ultralytics 다운로드 경로 변경
                    try:
                        # ultralytics 설정 업데이트
                        SETTINGS['weights_dir'] = str(default_models_dir)
                        SETTINGS.save()
                    except:
                        pass
                    
                    # 임시로 환경변수 설정
                    old_torch_home = os.environ.get('TORCH_HOME')
                    os.environ['TORCH_HOME'] = str(settings.MODELS_ROOT)
                    
                    try:
                        # 모델 다운로드 - ultralytics가 자동으로 처리
                        self.yolo_model = YOLO(self.model.yolo_version)
                        
                        # 다운로드된 파일 찾아서 이동
                        import shutil
                        from pathlib import Path
                        
                        # 가능한 캐시 위치들
                        possible_locations = [
                            # 현재 디렉토리
                            Path.cwd() / self.model.yolo_version,
                            settings.BASE_DIR / self.model.yolo_version,
                            # ultralytics 기본 캐시
                            Path.home() / '.cache' / 'torch' / 'hub' / 'ultralytics' / self.model.yolo_version,
                            # torch hub
                            Path.home() / '.cache' / 'torch' / 'hub' / self.model.yolo_version,
                        ]
                        
                        for possible_path in possible_locations:
                            if possible_path.exists() and possible_path.is_file():
                                if str(possible_path) != local_model_path:
                                    print(f"   📦 발견: {possible_path}")
                                    shutil.move(str(possible_path), local_model_path)
                                    print(f"   ✅ 이동 완료: {local_model_path}")
                                break
                        
                        # 이동된 모델로 재로드
                        if os.path.exists(local_model_path):
                            self.yolo_model = YOLO(local_model_path)
                        
                    finally:
                        # 환경변수 복원
                        if old_torch_home:
                            os.environ['TORCH_HOME'] = old_torch_home
                        elif 'TORCH_HOME' in os.environ:
                            del os.environ['TORCH_HOME']
            else:
                # 사용자가 업로드한 모델
                self.yolo_model = YOLO(model_path)
            
            print(f"✅ YOLO 모델 로드 완료")
            print(f"   클래스: {list(self.yolo_model.names.values())[:5]}... (총 {len(self.yolo_model.names)}개)")
            
        except ImportError:
            print(f"❌ ultralytics 패키지가 설치되어 있지 않습니다")
            print(f"   설치: pip install ultralytics --break-system-packages")
            raise
        except Exception as e:
            print(f"❌ YOLO 모델 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def detect_frame(self, frame, frame_idx):
        """단일 프레임 감지"""
        
        if self.model_type == 'yolo':
            return self.detect_yolo(frame)
        elif self.model_type == 'custom':
            return self.detect_custom(frame)
        else:
            return []

    def detect_yolo(self, frame):
        """YOLO 객체 감지"""
        if not self.yolo_model:
            return []
        
        try:
            # YOLO 추론
            results = self.yolo_model(frame, verbose=False)
            
            detections = []
            
            # 결과 파싱
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # 바운딩 박스 좌표
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # 신뢰도
                    confidence = float(box.conf[0])
                    
                    # 클래스
                    class_id = int(box.cls[0])
                    label = self.yolo_model.names[class_id]
                    
                    # 신뢰도 임계값
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
    
    def detect_custom(self, frame):
        """사용자 정의 모델"""
        # TODO: 다른 모델 타입 지원
        return []
    
    def process_video(self, input_path, output_path, progress_callback=None):
        """동영상에 감지 모델 적용"""
        
        print(f"\n{'='*60}")
        print(f"🔍 감지 처리 시작")
        print(f"{'='*60}")
        print(f"모델: {self.model.name}")
        print(f"타입: {self.model_type}")
        print(f"입력: {input_path}")
        print(f"출력: {output_path}")
        
        cap = cv2.VideoCapture(input_path)
        
        if not cap.isOpened():
            raise ValueError(f"동영상을 열 수 없습니다: {input_path}")
        
        # 동영상 정보
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"해상도: {width}x{height}")
        print(f"FPS: {fps}")
        print(f"총 프레임: {total_frames}")
        
        # 임시 파일로 먼저 저장
        temp_output = str(Path(output_path).parent / f'temp_{Path(output_path).name}')
        print(f"임시 출력: {temp_output}")
        
        # 출력 동영상 설정
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        if not out.isOpened():
            cap.release()
            raise ValueError(f"출력 VideoWriter를 생성할 수 없습니다")
        
        # 결과 저장
        all_detections = []
        detection_summary = {}
        total_detections = 0
        
        frame_count = 0
        
        try:
            print(f"\n🔄 프레임 처리 중...")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 감지 수행
                detections = self.detect_frame(frame, frame_count)
                
                # 결과 시각화
                annotated_frame = self.draw_detections(frame, detections)
                
                # 프레임 저장
                out.write(annotated_frame)
                
                # 결과 기록
                if detections:
                    all_detections.append({
                        'frame': frame_count,
                        'detections': detections
                    })
                    total_detections += len(detections)
                    
                    # 클래스별 통계
                    for det in detections:
                        label = det['label']
                        detection_summary[label] = detection_summary.get(label, 0) + 1
                
                frame_count += 1
                
                # 진행률 콜백 (0-80%)
                if progress_callback and frame_count % 10 == 0:
                    progress = int((frame_count / total_frames) * 80) if total_frames > 0 else 0
                    progress_callback(frame_count, total_frames, progress)
                
                # 진행상황 출력
                if frame_count % 100 == 0:
                    percent = (frame_count / total_frames * 100) if total_frames > 0 else 0
                    print(f"   진행: {frame_count}/{total_frames} ({percent:.1f}%) - 감지: {total_detections}")
        
        finally:
            cap.release()
            out.release()
            print(f"✅ OpenCV 처리 완료: {frame_count} 프레임")
            
            import time
            time.sleep(1)
        
        # ffmpeg 재인코딩
        if progress_callback:
            progress_callback(frame_count, total_frames, 85)
        
        print(f"\n🎬 ffmpeg 재인코딩 시작...")
        ffmpeg_success = self.reencode_with_ffmpeg(temp_output, output_path)
        
        if ffmpeg_success:
            try:
                os.remove(temp_output)
                print(f"🗑️  임시 파일 삭제 완료")
            except Exception as e:
                print(f"⚠️  임시 파일 삭제 실패: {e}")
        else:
            print(f"\n⚠️  ffmpeg 재인코딩 실패 - OpenCV 출력 사용")
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_output, output_path)
        
        if not os.path.exists(output_path):
            raise ValueError(f"최종 출력 파일이 없습니다: {output_path}")
        
        final_size = os.path.getsize(output_path)
        print(f"\n📦 최종 파일 크기: {final_size:,} bytes ({final_size/1024/1024:.2f} MB)")
        
        print(f"\n📊 감지 결과:")
        print(f"   총 감지 수: {total_detections}")
        print(f"   감지된 클래스: {len(detection_summary)}")
        for label, count in detection_summary.items():
            print(f"   - {label}: {count}")
        
        if progress_callback:
            progress_callback(frame_count, total_frames, 100)
        
        results = {
            'detections': all_detections,
            'total_detections': total_detections,
            'summary': detection_summary,
        }
        
        print(f"{'='*60}\n")
        
        return results
    
    def reencode_with_ffmpeg(self, input_path, output_path):
        """ffmpeg로 웹 브라우저 재생 가능하도록 재인코딩"""
        import shutil
        
        ffmpeg_path = shutil.which('ffmpeg')
        
        if not ffmpeg_path:
            # PATH에서 못 찾으면 일반적인 설치 위치 확인
            possible_paths = [
                r'C:\ffmpeg\bin\ffmpeg.exe',
                r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
        
        if not ffmpeg_path:
            print(f"❌ ffmpeg를 찾을 수 없습니다!")
            return False
        
        print(f"✅ ffmpeg 경로: {ffmpeg_path}")
        
        # 입력 파일 확인
        if not os.path.exists(input_path):
            print(f"❌ 입력 파일이 없습니다: {input_path}")
            return False
        
        input_size = os.path.getsize(input_path)
        print(f"📥 입력 파일: {input_size:,} bytes ({input_size/1024/1024:.2f} MB)")
        
        if input_size < 1000:
            print(f"❌ 입력 파일이 너무 작습니다!")
            return False
        
        try:
            cmd = [
                ffmpeg_path,
                '-i', str(input_path),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                '-y',
                str(output_path)
            ]
            
            print(f"   명령어: {' '.join(cmd[:3])} ... {cmd[-1]}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=1800
            )
            
            print(f"   Return code: {result.returncode}")
            
            if result.returncode == 0:
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    print(f"✅ ffmpeg 재인코딩 성공!")
                    print(f"📤 출력 파일: {output_size:,} bytes ({output_size/1024/1024:.2f} MB)")
                    
                    if output_size < 1000:
                        print(f"⚠️  출력 파일이 너무 작습니다!")
                        return False
                    
                    return True
                else:
                    print(f"❌ 출력 파일이 생성되지 않았습니다!")
                    return False
            else:
                print(f"❌ ffmpeg 실패 (return code: {result.returncode})")
                if result.stderr:
                    print(f"   stderr (마지막 500자): {result.stderr[-500:]}")
                return False
                
        except Exception as e:
            print(f"❌ 예외 발생: {e}")
            return False
    
    def detect_frame(self, frame, frame_idx):
        """단일 프레임 감지"""
        
        if self.model_type == 'yolo':
            return self.detect_yolo(frame)
        elif self.model_type == 'custom':
            return self.detect_custom(frame)
        else:
            return []
    
    def detect_yolo(self, frame):
        """YOLO 객체 감지"""
        if not self.yolo_model:
            return []
        
        try:
            # YOLO 추론 (verbose=False로 출력 최소화)
            results = self.yolo_model(frame, verbose=False)
            
            detections = []
            
            # 결과 파싱
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # 바운딩 박스 좌표
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # 신뢰도
                    confidence = float(box.conf[0])
                    
                    # 클래스
                    class_id = int(box.cls[0])
                    label = self.yolo_model.names[class_id]
                    
                    # 신뢰도 임계값
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
    
    def detect_custom(self, frame):
        """사용자 정의 모델"""
        return []
    
    def draw_detections(self, frame, detections):
        """감지 결과를 프레임에 그리기"""
        
        result = frame.copy()
        
        for det in detections:
            label = det['label']
            confidence = det.get('confidence', 0)
            bbox = det.get('bbox')
            
            if bbox:
                x, y, w, h = bbox
                
                # 색상
                color = self.get_color_for_label(label)
                
                # 바운딩 박스
                cv2.rectangle(result, (x, y), (x+w, y+h), color, 2)
                
                # 레이블 배경
                text = f"{label} {confidence:.2f}"
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(result, (x, y-text_size[1]-10), 
                            (x+text_size[0]+10, y), color, -1)
                
                # 레이블 텍스트
                cv2.putText(result, text, (x+5, y-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return result
    
    def get_color_for_label(self, label):
        """클래스별 고유 색상 생성"""
        hash_val = hash(label)
        r = (hash_val & 0xFF0000) >> 16
        g = (hash_val & 0x00FF00) >> 8
        b = hash_val & 0x0000FF
        return (b, g, r)