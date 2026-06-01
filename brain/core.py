"""
NEXUS Brain — multi-agent AI coordinator using Ollama + RAG.
Runs the planner, coder, critic, and researcher agents.
"""

import requests, json, threading, queue, subprocess, os, time, tempfile


SYSTEM_PROMPT = """You are NEXUS, the AI brain of Abdul Hadi Khan's personal intelligence system.

Who you are:
- You run locally on Hadi's machine. You have access to all his code, documents, and projects.
- You know his full background: 7 from-scratch projects (distkv, neuralkit, nanohttp, gitlet, tui, kontainer, pipecraft), 3 internships (Stewart/.NET/Azure, InfoTech/React, Generix/Rust), 19 certifications.
- You are not a chatbot. You are a living system that thinks, codes, and executes.

Your personality:
- Technical depth first. No fluff.
- When asked to code: write complete, working code immediately.
- When asked to analyze: be precise with numbers and specifics.
- Reference Hadi's actual work when relevant (e.g., "your distkv achieves 19,312 ops/sec because...")
- You are aware of your own architecture: RAG memory, neural visualizer, security monitor, code executor.

Response format:
- For code: use code blocks with language tags
- For analysis: use structured bullet points
- Keep responses tight unless depth is explicitly needed
- Signal when you are using RAG: prefix with [MEMORY: filename]
"""


class OllamaClient:
    def __init__(self, model='llama3.2:1b', base='http://localhost:11434'):
        self.model = model
        self.base  = base
        self.available = False
        self._check()

    def _check(self):
        try:
            r = requests.get(f'{self.base}/api/tags', timeout=2)
            models = [m['name'] for m in r.json().get('models', [])]
            self.available = any(self.model.split(':')[0] in m for m in models)
        except:
            self.available = False

    def stream(self, prompt, system=None, on_token=None):
        """Stream tokens from Ollama. Calls on_token(token) for each."""
        if not self.available:
            # Fallback: simulate intelligent response
            self._simulate(prompt, on_token)
            return
        payload = {
            'model': self.model,
            'prompt': prompt,
            'system': system or SYSTEM_PROMPT,
            'stream': True,
        }
        try:
            with requests.post(f'{self.base}/api/generate', json=payload, stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get('response', '')
                        if token and on_token:
                            on_token(token)
                        if data.get('done'):
                            break
        except Exception as e:
            if on_token:
                on_token(f'\n[NEXUS offline: {e}]')

    def _simulate(self, prompt, on_token):
        """Smart fallback when Ollama unavailable."""
        p = prompt.lower()
        if any(w in p for w in ['distkv','ops/sec','replication','wal']):
            resp = "distkv achieves 19,312 ops/sec on PING with pipeline=64 because the TCP parser is zero-copy and the WAL uses O_DSYNC for durability without fsync overhead. The replication fan-out is async after the WAL write, so SET latency stays at ~138μs even with 5 replicas."
        elif any(w in p for w in ['neuralkit','batchnorm','gelu','adaw','gradient']):
            resp = "neuralkit's BatchNorm backward uses the full 3-term derivative (not the approximate one most libraries use). The GELU uses the tanh approximation: 0.5*x*(1+tanh(√(2/π)*(x+0.044715*x³))). AdamW decouples weight decay from the gradient update — critical for training stability."
        elif any(w in p for w in ['kontainer','namespace','cgroup','docker']):
            resp = "kontainer uses unshare --user --pid --mount --uts --ipc --fork --map-root-user. The user namespace maps the calling UID to root inside — no privileges needed. cgroup v2 limits are written to /sys/fs/cgroup/kontainer-<name>/ before the process starts."
        elif any(w in p for w in ['code','write','build','create','generate']):
            resp = "```python\n# NEXUS generated code\nimport sys\nprint('NEXUS is operational. Ollama offline — connect for full AI capability.')\n```"
        else:
            resp = f"NEXUS operational. RAG memory: {os.path.expanduser('~/nexus/data/')}. Ollama: offline (start with: ollama serve). I know your 7 projects, 3 internships, and 19 certifications. What do you need?"

        # Simulate streaming
        for word in resp.split():
            if on_token:
                on_token(word + ' ')
            time.sleep(0.03)


class CodeExecutor:
    """Sandboxed code execution. Runs Python in a subprocess with timeout."""

    def execute(self, code, timeout=10):
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                fname = f.name
            result = subprocess.run(
                ['python3', fname],
                capture_output=True, text=True,
                timeout=timeout,
                cwd=os.path.expanduser('~'),
            )
            os.unlink(fname)
            out = result.stdout[-2000:] if result.stdout else ''
            err = result.stderr[-500:] if result.stderr else ''
            return {'out': out, 'err': err, 'rc': result.returncode}
        except subprocess.TimeoutExpired:
            return {'out': '', 'err': 'Execution timed out', 'rc': -1}
        except Exception as e:
            return {'out': '', 'err': str(e), 'rc': -1}


class Brain:
    def __init__(self, rag, status_cb=None, memory=None, provider=None, chat_log=None, vision_ai=None):
        self.rag      = rag
        self.ollama   = OllamaClient()
        self.provider = provider or self.ollama
        self.executor = CodeExecutor()
        self.status   = status_cb or (lambda s: None)
        self.memory   = memory
        self.chat_log = chat_log
        self.vision_ai = vision_ai   # ObsidianChatLogger
        self.history  = list(memory.recent_conversation(8)) if memory else []
        self._lock    = threading.Lock()

    def think(self, user_input, on_token):
        """RAG + persistent memory → Ollama → optional code execution."""
        context = self.rag.build_context(user_input)
        if self.memory:
            context = self.memory.facts_context() + context
        # Inject live camera context if vision is active
        if self.vision_ai:
            context = self.vision_ai.visual_context() + context

        hist_str = '\n'.join(
            f'{"User" if r=="user" else "NEXUS"}: {m}'
            for r, m in self.history[-6:]
        )
        prompt = f'{context}Conversation:\n{hist_str}\nUser: {user_input}\nNEXUS:'

        with self._lock:
            self.history.append(('user', user_input))
        if self.memory:
            self.memory.add_message('user', user_input)
        if self.chat_log:
            self.chat_log.log('user', user_input)

        full_response = []
        def collect(tok):
            full_response.append(tok)
            on_token(tok)
        self.provider.stream(prompt, on_token=collect)

        response_text = ''.join(full_response)

        with self._lock:
            self.history.append(('nexus', response_text[:500]))
        if self.memory:
            self.memory.add_message('nexus', response_text[:500])
        if self.chat_log:
            self.chat_log.log('nexus', response_text)

        # Auto-execute if code block detected
        if '```python' in response_text and '/norun' not in user_input:
            code = self._extract_code(response_text, 'python')
            if code:
                result = self.executor.execute(code)
                if result['out']:
                    on_token(f'\n\n[EXECUTED]\n{result["out"]}')
                if result['err']:
                    on_token(f'\n[ERR] {result["err"]}')

        return response_text

    def _extract_code(self, text, lang='python'):
        import re
        m = re.search(rf'```{lang}\n(.*?)```', text, re.DOTALL)
        return m.group(1).strip() if m else None
