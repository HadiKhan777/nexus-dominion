"""
NEXUS Vision — live camera feed with face detection.
Renders camera frames as ASCII/ANSI art for the terminal panel.
Runs OpenCV in a background thread.
"""

import threading, time
import numpy as np


ASCII_CHARS = ' .,:;ox%#@'


class VisionWorker:
    def __init__(self, device=0, width=32, height=16):
        self.device    = device
        self.w         = width
        self.h         = height
        self.frame_art = [''] * height
        self.faces     = 0
        self.fps       = 0
        self.running   = False
        self.status    = 'off'
        self._thread   = None
        self._stop     = threading.Event()
        self._lock     = threading.Lock()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.status = 'off'

    def _loop(self):
        try:
            import cv2
        except ImportError:
            self.status = 'no-opencv'
            return

        cap = cv2.VideoCapture(self.device)
        if not cap.isOpened():
            self.status = 'no-device'
            return

        self.status = 'live'
        self.running = True

        # Load face detector
        face_cascade = None
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        try:
            face_cascade = cv2.CascadeClassifier(cascade_path)
        except:
            pass

        frame_times = []

        while not self._stop.is_set():
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # Resize for ASCII
            small = cv2.resize(frame, (self.w, self.h))
            gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            # Face detection on small frame
            face_count = 0
            if face_cascade is not None:
                faces = face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(4,4))
                face_count = len(faces) if len(faces) > 0 else 0

            # Convert to colored ASCII art
            art_lines = []
            orig_small = cv2.resize(frame, (self.w*2, self.h))  # 2x wide for aspect ratio
            orig_gray  = cv2.cvtColor(orig_small, cv2.COLOR_BGR2GRAY)

            for row in range(self.h):
                line = []
                for col in range(self.w*2):
                    pixel = orig_gray[row, col]
                    b, g, r = orig_small[row, col]
                    char = ASCII_CHARS[int(pixel / 255 * (len(ASCII_CHARS)-1))]
                    # ANSI color
                    line.append(f'\x1b[38;2;{r};{g};{b}m{char}')
                art_lines.append(''.join(line) + '\x1b[0m')

            dt = time.time() - t0
            frame_times.append(dt)
            if len(frame_times) > 10:
                frame_times.pop(0)

            with self._lock:
                self.frame_art = art_lines
                self.faces     = face_count
                self.fps       = round(1.0 / (sum(frame_times)/len(frame_times)), 1)

            time.sleep(max(0, 0.1 - dt))  # ~10fps

        cap.release()
        self.running = False

    def get_frame(self):
        with self._lock:
            return list(self.frame_art), self.faces, self.fps

    def get_frame_b64(self, quality=75):
        """Return latest raw camera frame as base64 JPEG for vision LLM."""
        if not self.running:
            return None
        try:
            import cv2, base64
            cap = cv2.VideoCapture(self.device)
            # Brief re-open: grab one clean frame
            for _ in range(3): cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            frame = cv2.resize(frame, (640, 480))
            _, buf = cv2.imencode(".jpg", frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, quality])
            return base64.b64encode(buf.tobytes()).decode("ascii")
        except Exception:
            return None
