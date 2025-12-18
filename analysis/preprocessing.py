import cv2
import numpy as np
from pathlib import Path
import subprocess
import os

class VideoPreprocessor:
    """동영상 전처리 클래스"""
    
    PREPROCESSING_METHODS = {
        'harris_corner': 'Harris Corner Detection',
        'gaussian_blur': 'Gaussian Blur',
        'canny_edge': 'Canny Edge Detection',
        'median_blur': 'Median Blur',
        'gray_scale': 'Grayscale',
        'sobel_edge': 'Sobel Edge Detection',
        'threshold': 'Binary Threshold',
        'adaptive_threshold': 'Adaptive Threshold',
        'morphology_open': 'Morphological Opening',
        'morphology_close': 'Morphological Closing',
    }
    
    @staticmethod
    def harris_corner(frame, params=None):
        """Harris Corner Detection"""
        params = params or {}
        block_size = params.get('block_size', 2)
        ksize = params.get('ksize', 3)
        k = params.get('k', 0.04)
        threshold = params.get('threshold', 0.01)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = np.float32(gray)
        
        dst = cv2.cornerHarris(gray, block_size, ksize, k)
        dst = cv2.dilate(dst, None)
        
        result = frame.copy()
        result[dst > threshold * dst.max()] = [0, 0, 255]
        
        return result
    
    @staticmethod
    def gaussian_blur(frame, params=None):
        """Gaussian Blur"""
        params = params or {}
        kernel_size = params.get('kernel_size', 5)
        sigma = params.get('sigma', 0)
        
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), sigma)
    
    @staticmethod
    def canny_edge(frame, params=None):
        """Canny Edge Detection"""
        params = params or {}
        threshold1 = params.get('threshold1', 100)
        threshold2 = params.get('threshold2', 200)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, threshold1, threshold2)
        
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def median_blur(frame, params=None):
        """Median Blur"""
        params = params or {}
        kernel_size = params.get('kernel_size', 5)
        
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        return cv2.medianBlur(frame, kernel_size)
    
    @staticmethod
    def gray_scale(frame, params=None):
        """Grayscale"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def sobel_edge(frame, params=None):
        """Sobel Edge Detection"""
        params = params or {}
        ksize = params.get('ksize', 3)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)
        
        sobel = np.sqrt(sobelx**2 + sobely**2)
        sobel = np.uint8(sobel / sobel.max() * 255)
        
        return cv2.cvtColor(sobel, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def threshold(frame, params=None):
        """Binary Threshold"""
        params = params or {}
        threshold_value = params.get('threshold', 127)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
        
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def adaptive_threshold(frame, params=None):
        """Adaptive Threshold"""
        params = params or {}
        block_size = params.get('block_size', 11)
        c = params.get('c', 2)
        
        if block_size % 2 == 0:
            block_size += 1
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, block_size, c
        )
        
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def morphology_open(frame, params=None):
        """Morphological Opening"""
        params = params or {}
        kernel_size = params.get('kernel_size', 5)
        
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        return cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)
    
    @staticmethod
    def morphology_close(frame, params=None):
        """Morphological Closing"""
        params = params or {}
        kernel_size = params.get('kernel_size', 5)
        
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        return cv2.morphologyEx(frame, cv2.MORPH_CLOSE, kernel)
    
    def apply_preprocessing(self, frame, preprocessing_type, params=None):
        """전처리 적용"""
        method = getattr(self, preprocessing_type, None)
        if method:
            return method(frame, params)
        else:
            raise ValueError(f"Unknown preprocessing type: {preprocessing_type}")
    
    def reencode_with_ffmpeg(self, input_path, output_path):
        """
        ffmpeg로 웹 브라우저 재생 가능하도록 재인코딩
        """
        import shutil
        
        # ffmpeg 경로 확인
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
            print(f"   PATH 확인 또는 C:\\ffmpeg\\bin\\ffmpeg.exe 존재 여부 확인")
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
                '-c:v', 'libx264',           # H.264 코덱
                '-preset', 'fast',           # 인코딩 속도 (ultrafast, fast, medium, slow)
                '-crf', '23',                # 품질 (18-28, 낮을수록 고품질)
                '-movflags', '+faststart',   # 웹 스트리밍 최적화
                '-pix_fmt', 'yuv420p',       # 브라우저 호환성
                '-y',                        # 덮어쓰기
                str(output_path)
            ]
            
            print(f"\n🎬 ffmpeg 재인코딩 시작...")
            print(f"   명령어: {' '.join(cmd[:3])} ... {cmd[-1]}")
            
            # ffmpeg 실행
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=1800  # 30분 타임아웃
            )
            
            print(f"\n📋 ffmpeg 결과:")
            print(f"   Return code: {result.returncode}")
            
            # stderr에 진행 상황 및 에러가 출력됨
            if result.stderr:
                # stderr의 마지막 부분만 출력 (너무 길면)
                stderr_lines = result.stderr.split('\n')
                if len(stderr_lines) > 20:
                    print(f"\n--- stderr (마지막 20줄) ---")
                    print('\n'.join(stderr_lines[-20:]))
                else:
                    print(f"\n--- stderr ---")
                    print(result.stderr)
                print(f"--- stderr 끝 ---\n")
            
            # 성공 확인
            if result.returncode == 0:
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    print(f"✅ ffmpeg 재인코딩 성공!")
                    print(f"📤 출력 파일: {output_size:,} bytes ({output_size/1024/1024:.2f} MB)")
                    
                    if output_size < 1000:
                        print(f"⚠️  경고: 출력 파일이 너무 작습니다!")
                        return False
                    
                    return True
                else:
                    print(f"❌ ffmpeg는 성공했으나 출력 파일이 없습니다: {output_path}")
                    return False
            else:
                print(f"❌ ffmpeg 실패 (return code: {result.returncode})")
                
                # 일반적인 에러 메시지 확인
                if 'Unrecognized option' in result.stderr:
                    print(f"⚠️  옵션 인식 실패 - ffmpeg GPL 버전인지 확인하세요")
                elif 'libx264' in result.stderr and 'not found' in result.stderr:
                    print(f"⚠️  libx264 코덱을 찾을 수 없습니다 - GPL 버전 필요")
                elif 'moov atom not found' in result.stderr:
                    print(f"⚠️  입력 파일이 손상되었거나 완전히 생성되지 않았습니다")
                
                return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ ffmpeg 타임아웃 (30분 초과)")
            return False
            
        except FileNotFoundError as e:
            print(f"❌ ffmpeg 실행 실패: {e}")
            return False
            
        except Exception as e:
            print(f"❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def process_video(self, video_path, pipeline, output_path, progress_callback=None):
        """동영상에 전처리 파이프라인 적용"""
        
        print(f"\n{'='*60}")
        print(f"📹 동영상 처리 시작")
        print(f"{'='*60}")
        print(f"입력: {video_path}")
        print(f"출력: {output_path}")
        print(f"파이프라인: {len(pipeline)}단계")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"동영상을 열 수 없습니다: {video_path}")
        
        # 동영상 정보
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"해상도: {width}x{height}")
        print(f"FPS: {fps}")
        print(f"총 프레임: {total_frames}")
        
        # 임시 파일로 먼저 저장 (OpenCV 출력)
        temp_output = str(Path(output_path).parent / f'temp_{Path(output_path).name}')
        print(f"임시 출력: {temp_output}")
        
        # 출력 동영상 설정
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        if not out.isOpened():
            cap.release()
            raise ValueError(f"출력 VideoWriter를 생성할 수 없습니다")
        
        print(f"✅ VideoWriter 생성 완료 (코덱: mp4v)")
        
        frame_count = 0
        
        try:
            print(f"\n🔄 프레임 처리 중...")
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 파이프라인 적용
                processed_frame = frame.copy()
                for step in pipeline:
                    step_type = step['type']
                    params = step.get('params', {})
                    processed_frame = self.apply_preprocessing(processed_frame, step_type, params)
                
                # 프레임 저장
                out.write(processed_frame)
                frame_count += 1
                
                # 진행률 콜백 (0-80%)
                if progress_callback and frame_count % 10 == 0:
                    progress = int((frame_count / total_frames) * 80) if total_frames > 0 else 0
                    progress_callback(frame_count, total_frames, progress)
                    
                # 진행상황 출력
                if frame_count % 100 == 0:
                    percent = (frame_count / total_frames * 100) if total_frames > 0 else 0
                    print(f"   진행: {frame_count}/{total_frames} ({percent:.1f}%)")
        
        finally:
            print(f"\n🔒 리소스 해제 중...")
            cap.release()
            out.release()
            
            # 파일이 완전히 닫힐 때까지 대기
            import time
            time.sleep(1)
            
            print(f"✅ OpenCV 처리 완료: {frame_count} 프레임")
        
        # 임시 파일 확인
        if not os.path.exists(temp_output):
            raise ValueError(f"임시 파일이 생성되지 않았습니다: {temp_output}")
        
        temp_size = os.path.getsize(temp_output)
        print(f"📦 임시 파일 크기: {temp_size:,} bytes ({temp_size/1024/1024:.2f} MB)")
        
        if temp_size < 1000:
            raise ValueError(f"임시 파일이 너무 작습니다: {temp_size} bytes")
        
        # ffmpeg 재인코딩 (80-100%)
        if progress_callback:
            progress_callback(frame_count, total_frames, 85)
        
        print(f"\n🎬 ffmpeg 재인코딩 시도...")
        success = self.reencode_with_ffmpeg(temp_output, output_path)
        
        if success:
            # 임시 파일 삭제
            try:
                os.remove(temp_output)
                print(f"🗑️  임시 파일 삭제 완료")
            except Exception as e:
                print(f"⚠️  임시 파일 삭제 실패: {e}")
        else:
            # ffmpeg 실패 시 임시 파일을 최종 파일로 사용
            print(f"\n⚠️  ffmpeg 재인코딩 실패 - OpenCV 출력 사용")
            print(f"   브라우저에서 재생이 안 될 수 있습니다")
            
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_output, output_path)
        
        # 최종 파일 확인
        if not os.path.exists(output_path):
            raise ValueError(f"최종 출력 파일이 없습니다: {output_path}")
        
        final_size = os.path.getsize(output_path)
        print(f"\n📦 최종 파일 크기: {final_size:,} bytes ({final_size/1024/1024:.2f} MB)")
        
        if final_size < 1000:
            raise ValueError(f"최종 파일이 너무 작습니다: {final_size} bytes")
        
        if progress_callback:
            progress_callback(frame_count, total_frames, 100)
        
        print(f"\n{'='*60}")
        print(f"✨ 처리 완료!")
        print(f"{'='*60}\n")
        
        return frame_count

    def process_image(self, image_path, pipeline, output_path, progress_callback=None):
        """이미지에 전처리 파이프라인 적용"""
        
        print(f"\n{'='*60}")
        print(f"🖼️  이미지 처리 시작")
        print(f"{'='*60}")
        print(f"입력: {image_path}")
        print(f"출력: {output_path}")
        print(f"파이프라인: {len(pipeline)}단계")
        
        # 이미지 읽기
        frame = cv2.imread(image_path)
        
        if frame is None:
            raise ValueError(f"이미지를 열 수 없습니다: {image_path}")
        
        # 이미지 정보
        height, width = frame.shape[:2]
        channels = frame.shape[2] if len(frame.shape) > 2 else 1
        
        print(f"해상도: {width}x{height}")
        print(f"채널: {channels}")
        
        total_steps = len(pipeline)
        
        try:
            print(f"\n🔄 전처리 적용 중...")
            
            # 파이프라인 적용
            processed_frame = frame.copy()
            for idx, step in enumerate(pipeline):
                step_type = step['type']
                params = step.get('params', {})
                
                print(f"   단계 {idx+1}/{total_steps}: {step_type}")
                processed_frame = self.apply_preprocessing(processed_frame, step_type, params)
                
                # 진행률 콜백 (0-90%)
                if progress_callback:
                    progress = int((idx + 1) / total_steps * 90)
                    progress_callback(idx + 1, total_steps, progress)
            
            # 이미지 저장
            print(f"\n💾 이미지 저장 중: {output_path}")
            
            # 출력 디렉토리 생성
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 이미지 저장
            success = cv2.imwrite(str(output_path), processed_frame)
            
            if not success:
                raise ValueError(f"이미지 저장 실패: {output_path}")
            
            # 파일 확인
            if not os.path.exists(output_path):
                raise ValueError(f"출력 파일이 생성되지 않았습니다: {output_path}")
            
            file_size = os.path.getsize(output_path)
            print(f"✅ 이미지 저장 완료")
            print(f"📦 파일 크기: {file_size:,} bytes ({file_size/1024:.2f} KB)")
            
            if file_size < 100:
                raise ValueError(f"출력 파일이 너무 작습니다: {file_size} bytes")
            
            if progress_callback:
                progress_callback(total_steps, total_steps, 100)
            
            print(f"\n{'='*60}")
            print(f"✨ 처리 완료!")
            print(f"{'='*60}\n")
            
            return output_path
            
        except Exception as e:
            print(f"\n❌ 이미지 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            raise