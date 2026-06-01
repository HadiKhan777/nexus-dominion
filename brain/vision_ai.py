"""
NEXUS Vision AI — connects the camera feed to the AI brain.

Captures frames, sends to multimodal LLMs, stores observations
as memories and Obsidian nodes. NEXUS literally sees and learns.

Vision models (all free):
  Groq:        meta-llama/llama-4-scout-17b-16e-instruct  (Llama 4, multimodal)
  OpenRouter:  nvidia/nemotron-nano-12b-v2-vl:free         (VL = Vision Language)
  OpenRouter:  google/gemma-4-26b-a4b-it:free
"""

import base64, requests, json, time, threading
from datetime import datetime
from pathlib import Path

# Vision model preference order (model, provider_key, base_url)
VISION_MODELS = [
    ('meta-llama/llama-4-scout-17b-16e-instruct', 'groq',       'https://api.groq.com/openai/v1'),
    ('nvidia/nemotron-nano-12b-v2-vl:free',        'openrouter', 'https://openrouter.ai/api/v1'),
    ('google/gemma-4-26b-a4b-it:free',             'openrouter', 'https://openrouter.ai/api/v1'),
]


class VisionAI:
    def __init__(self, providers=None, memory=None, obs_writer=None, vision_worker=None):
        self.providers      = providers or {}
        self.memory         = memory
        self.obs_writer     = obs_writer
        self.vision_worker  = vision_worker  # VisionWorker already running

        self.last_frame  = None   # latest base64 JPEG
        self.last_desc   = ''     # latest text description
        self.last_ts     = None   # timestamp of last observation
        self.watching    = False  # continuous observation mode
        self.watch_interval = 30  # seconds between auto-observations
        self._thread     = None
        self._lock       = threading.Lock()

    # ── Frame capture ──────────────────────────────────────────────────────────

    def capture_frame(self, device=0, width=640, height=480, quality=75):
        """Get a frame — prefer VisionWorker buffer to avoid double-opening camera."""
        # Use already-running VisionWorker if available
        if self.vision_worker and self.vision_worker.running:
            return self.vision_worker.get_frame_b64(quality)
        # Otherwise open camera directly
        try:
            import cv2
            cap = cv2.VideoCapture(device)
            for _ in range(8): cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            frame = cv2.resize(frame, (width, height))
            _, buf = cv2.imencode('.jpg', frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, quality])
            return base64.b64encode(buf.tobytes()).decode('ascii')
        except Exception:
            return None

    # ── Vision LLM calls ───────────────────────────────────────────────────────

    def _ask(self, api_key, base_url, model, b64_image, question):
        """Send image + question to a multimodal LLM, return answer string."""
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
            'HTTP-Referer':  'https://github.com/HadiKhan777/nexus-dominion',
        }
        payload = {
            'model':      model,
            'max_tokens': 400,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'text',      'text': question},
                    {'type': 'image_url', 'image_url': {
                        'url': f'data:image/jpeg;base64,{b64_image}'
                    }},
                ]
            }]
        }
        try:
            r = requests.post(f'{base_url}/chat/completions',
                              headers=headers, json=payload, timeout=25)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content'].strip()
        except Exception:
            pass
        return None

    def _find_vision_model(self):
        """Return (api_key, base_url, model) for the first available vision model."""
        for model, pname, base_url in VISION_MODELS:
            p = self.providers.get(pname)
            if p and p.available():
                return p.api_key, base_url, model
        return None, None, None

    # ── Main describe API ──────────────────────────────────────────────────────

    def describe(self, question="What do you see? Describe the scene concisely.", device=0):
        """Capture frame, ask vision LLM, store result, return description."""
        b64 = self.capture_frame(device)
        if not b64:
            return "Camera unavailable or no frame captured."

        with self._lock:
            self.last_frame = b64

        api_key, base_url, model = self._find_vision_model()
        if not api_key:
            # Fallback: OpenCV face/object detection description
            return self._opencv_fallback(device)

        result = self._ask(api_key, base_url, model, b64, question)
        if not result:
            return "Vision model did not respond."

        ts = datetime.now().strftime('%H:%M')
        full = f'[{ts} via {model.split("/")[-1]}] {result}'

        with self._lock:
            self.last_desc = result
            self.last_ts   = ts

        # Store as persistent memory
        if self.memory:
            self.memory.remember(f'Camera observation at {ts}: {result[:300]}')

        # Write to Obsidian knowledge graph
        if self.obs_writer:
            date = datetime.now().strftime('%Y-%m-%d')
            self.obs_writer.log_finding(
                'VISION', model.split('/')[-1],
                f'Visual observation at {ts}',
                result
            )

        return full

    def _opencv_fallback(self, device=0):
        """Basic OpenCV-based scene description without LLM."""
        try:
            import cv2
            cap = cv2.VideoCapture(device)
            for _ in range(5): cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret: return "Camera offline."
            gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces   = cascade.detectMultiScale(gray, 1.1, 4, minSize=(40,40))
            n_faces = len(faces) if len(faces) else 0
            brightness = int(gray.mean())
            light = 'bright' if brightness > 100 else 'dim' if brightness > 40 else 'dark'
            return (f'OpenCV only (no vision LLM): {n_faces} face(s) detected, '
                    f'{light} scene (brightness={brightness}/255). '
                    f'Add Groq or OpenRouter key for full visual understanding.')
        except Exception as e:
            return f'Camera error: {e}'

    # ── Continuous observation (watch mode) ────────────────────────────────────

    def start_watching(self, interval=30, device=0,
                       question="Describe what you see briefly. Note any changes."):
        """Auto-observe every N seconds. Stores everything to memory + Obsidian."""
        self.watching = True
        self.watch_interval = interval

        def _loop():
            count = 0
            while self.watching:
                count += 1
                self.describe(
                    question if count > 1 else
                    "Describe the scene in detail. Who is present? What objects are visible? What's happening?",
                    device
                )
                for _ in range(interval * 10):
                    if not self.watching:
                        break
                    time.sleep(0.1)

        self._thread = threading.Thread(target=_loop, name='vision-watch', daemon=True)
        self._thread.start()

    def stop_watching(self):
        self.watching = False

    # ── Context injection ──────────────────────────────────────────────────────

    def visual_context(self):
        """Return latest visual observation for injection into AI prompts."""
        with self._lock:
            if self.last_desc and self.last_ts:
                return (f'[Visual context from camera at {self.last_ts}]\n'
                        f'{self.last_desc}\n\n')
        return ''

    def answer_about_scene(self, question, device=0):
        """Ask the vision LLM a specific question about the current camera view."""
        b64 = self.capture_frame(device)
        if not b64:
            return "Cannot access camera."
        api_key, base_url, model = self._find_vision_model()
        if not api_key:
            return "No vision model available. Add Groq or OpenRouter API key."
        result = self._ask(api_key, base_url, model, b64, question)
        return result or "Vision model did not respond."
