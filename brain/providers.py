"""
NEXUS Multi-Provider LLM Client.

Unified interface for: Ollama · OpenAI · Gemini · DeepSeek · Kimi · Anthropic
Each provider falls back to Ollama if no API key is configured.

Config: ~/.nexus/providers.json
"""

import json, os, time, requests, threading
from pathlib import Path

CONFIG_FILE = Path.home() / '.nexus' / 'providers.json'
DEFAULT_CONFIG = {
    "ollama":    {"base": "http://localhost:11434", "model": "llama3.2:1b"},
    "openai":    {"api_key": "", "model": "gpt-4o-mini"},
    "gemini":    {"api_key": "", "model": "gemini-1.5-flash"},
    "deepseek":  {"api_key": "", "model": "deepseek-chat"},
    "kimi":      {"api_key": "", "model": "moonshot-v1-8k"},
    "anthropic":    {"api_key": "", "model": "claude-haiku-4-5-20251001"},
    "groq":        {"api_key": "", "model": "llama-3.1-70b-versatile"},
    "openrouter":  {"api_key": "", "model": "meta-llama/llama-3.1-8b-instruct:free"},
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            merged = dict(DEFAULT_CONFIG)
            merged.update(saved)
            return merged
        except Exception:
            pass
    # Write defaults on first run
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    return dict(DEFAULT_CONFIG)


class BaseProvider:
    name = 'base'

    def available(self):
        return False

    def stream(self, prompt, system='', on_token=None):
        raise NotImplementedError

    def _emit(self, text, on_token):
        if not on_token:
            return
        for word in text.split():
            on_token(word + ' ')
            time.sleep(0.015)


class OllamaProvider(BaseProvider):
    name = 'Ollama'

    def __init__(self, cfg):
        self.base  = cfg.get('base', 'http://localhost:11434')
        self.model = cfg.get('model', 'llama3.2:1b')

    def available(self):
        try:
            r = requests.get(f'{self.base}/api/tags', timeout=2)
            models = [m['name'] for m in r.json().get('models', [])]
            return any(self.model.split(':')[0] in m for m in models)
        except Exception:
            return False

    def stream(self, prompt, system='', on_token=None):
        payload = {'model': self.model, 'prompt': prompt,
                   'system': system, 'stream': True}
        try:
            with requests.post(f'{self.base}/api/generate',
                               json=payload, stream=True, timeout=120) as r:
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        tok = data.get('response', '')
                        if tok and on_token:
                            on_token(tok)
                        if data.get('done'):
                            break
        except Exception as e:
            if on_token:
                on_token(f'\n[Ollama error: {e}]')


class OpenAIProvider(BaseProvider):
    name = 'OpenAI'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'gpt-4o-mini')
        self.base    = 'https://api.openai.com/v1'

    def available(self):
        return bool(self.api_key and self.api_key.startswith('sk-'))

    def stream(self, prompt, system='', on_token=None):
        headers = {'Authorization': f'Bearer {self.api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'model': self.model, 'stream': True,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': prompt},
            ]
        }
        try:
            with requests.post(f'{self.base}/chat/completions',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line or line == b'data: [DONE]':
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        delta = json.loads(raw)['choices'][0]['delta']
                        tok = delta.get('content', '')
                        if tok and on_token:
                            on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[OpenAI error: {e}]')


class GeminiProvider(BaseProvider):
    name = 'Gemini'

    def __init__(self, cfg):
        self.api_key  = cfg.get('api_key', '')
        self.model    = cfg.get('model', 'gemini-1.5-flash')
        self._avail   = None   # cached result

    def available(self):
        if not self.api_key or len(self.api_key) < 10:
            return False
        if self._avail is not None:
            return self._avail
        try:
            import requests as _r
            url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                   f'{self.model}:generateContent?key={self.api_key}')
            r = _r.post(url,
                json={'contents':[{'parts':[{'text':'hi'}]}],
                      'generationConfig':{'maxOutputTokens':4}},
                timeout=5)
            self._avail = r.status_code == 200
        except Exception:
            self._avail = False
        return self._avail

    def stream(self, prompt, system='', on_token=None):
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{self.model}:streamGenerateContent?key={self.api_key}')
        payload = {
            'contents': [{'parts': [{'text': (system + '\n\n' + prompt).strip()}]}],
            'generationConfig': {'maxOutputTokens': 1024}
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=60) as r:
                buffer = ''
                for chunk in r.iter_content(chunk_size=None):
                    buffer += chunk.decode('utf-8', errors='ignore')
                    while '"text":' in buffer:
                        try:
                            start = buffer.index('"text":') + 8
                            end   = buffer.index('"', start)
                            tok   = buffer[start:end].encode().decode('unicode_escape')
                            if on_token and tok:
                                on_token(tok)
                            buffer = buffer[end+1:]
                        except (ValueError, UnicodeDecodeError):
                            break
        except Exception as e:
            if on_token:
                on_token(f'\n[Gemini error: {e}]')


class DeepSeekProvider(BaseProvider):
    """DeepSeek uses OpenAI-compatible API."""
    name = 'DeepSeek'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'deepseek-chat')
        self.base    = 'https://api.deepseek.com/v1'

    def available(self):
        return bool(self.api_key and self.api_key.startswith('sk-'))

    def stream(self, prompt, system='', on_token=None):
        headers = {'Authorization': f'Bearer {self.api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'model': self.model, 'stream': True,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': prompt},
            ]
        }
        try:
            with requests.post(f'{self.base}/chat/completions',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line or b'[DONE]' in line:
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        delta = json.loads(raw)['choices'][0]['delta']
                        tok = delta.get('content', '')
                        if tok and on_token:
                            on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[DeepSeek error: {e}]')


class KimiProvider(BaseProvider):
    """Kimi (Moonshot AI) — OpenAI-compatible API."""
    name = 'Kimi'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'moonshot-v1-8k')
        self.base    = 'https://api.moonshot.cn/v1'

    def available(self):
        return bool(self.api_key and self.api_key.startswith('sk-'))

    def stream(self, prompt, system='', on_token=None):
        headers = {'Authorization': f'Bearer {self.api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'model': self.model, 'stream': True,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': prompt},
            ]
        }
        try:
            with requests.post(f'{self.base}/chat/completions',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line or b'[DONE]' in line:
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        delta = json.loads(raw)['choices'][0]['delta']
                        tok = delta.get('content', '')
                        if tok and on_token:
                            on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[Kimi error: {e}]')


class AnthropicProvider(BaseProvider):
    name = 'Anthropic'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'claude-haiku-4-5-20251001')

    def available(self):
        return bool(self.api_key and self.api_key.startswith('sk-ant'))

    def stream(self, prompt, system='', on_token=None):
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
        payload = {
            'model': self.model, 'max_tokens': 1024, 'stream': True,
            'system': system,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        try:
            with requests.post('https://api.anthropic.com/v1/messages',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line:
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        data = json.loads(raw)
                        if data.get('type') == 'content_block_delta':
                            tok = data['delta'].get('text', '')
                            if tok and on_token:
                                on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[Anthropic error: {e}]')



class GroqProvider(BaseProvider):
    """Groq — free, extremely fast inference. OpenAI-compatible."""
    name = 'Groq'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'llama-3.1-70b-versatile')
        self.base    = 'https://api.groq.com/openai/v1'

    def available(self):
        return bool(self.api_key and self.api_key.startswith('gsk_'))

    def stream(self, prompt, system='', on_token=None):
        headers = {'Authorization': f'Bearer {self.api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'model': self.model, 'stream': True,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': prompt},
            ]
        }
        try:
            with requests.post(f'{self.base}/chat/completions',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line or b'[DONE]' in line:
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        delta = json.loads(raw)['choices'][0]['delta']
                        tok = delta.get('content', '')
                        if tok and on_token:
                            on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[Groq error: {e}]')


class OpenRouterProvider(BaseProvider):
    """OpenRouter — free models (llama, gemma, mistral). OpenAI-compatible."""
    name = 'OpenRouter'

    def __init__(self, cfg):
        self.api_key = cfg.get('api_key', '')
        self.model   = cfg.get('model', 'meta-llama/llama-3.1-8b-instruct:free')
        self.base    = 'https://openrouter.ai/api/v1'

    def available(self):
        return bool(self.api_key and self.api_key.startswith('sk-or-'))

    def stream(self, prompt, system='', on_token=None):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/HadiKhan777/nexus',
        }
        payload = {
            'model': self.model, 'stream': True,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': prompt},
            ]
        }
        try:
            with requests.post(f'{self.base}/chat/completions',
                               headers=headers, json=payload,
                               stream=True, timeout=60) as r:
                for line in r.iter_lines():
                    if not line or b'[DONE]' in line:
                        continue
                    raw = line.decode().removeprefix('data: ')
                    try:
                        delta = json.loads(raw)['choices'][0]['delta']
                        tok = delta.get('content', '')
                        if tok and on_token:
                            on_token(tok)
                    except Exception:
                        pass
        except Exception as e:
            if on_token:
                on_token(f'\n[OpenRouter error: {e}]')




class GroqVariantProvider(GroqProvider):
    """Groq with a specific model — reuses GroqProvider implementation."""
    def __init__(self, cfg):
        super().__init__(cfg)
        self.name = f"Groq/{cfg.get('model','?').split('/')[-1][:20]}"


class OpenRouterVariantProvider(OpenRouterProvider):
    """OpenRouter with a specific model — reuses OpenRouterProvider."""
    def __init__(self, cfg):
        super().__init__(cfg)
        self.name = f"OR/{cfg.get('model','?').split('/')[-1][:20]}"

def build_providers():
    """Load config and instantiate all providers. Returns dict name→provider."""
    cfg = load_config()
    ollama = OllamaProvider(cfg.get('ollama', {}))
    return {
        'ollama':          ollama,
        'openai':          OpenAIProvider(cfg.get('openai', {})),
        'gemini':          GeminiProvider(cfg.get('gemini', {})),
        'deepseek':        DeepSeekProvider(cfg.get('deepseek', {})),
        'kimi':            KimiProvider(cfg.get('kimi', {})),
        'anthropic':       AnthropicProvider(cfg.get('anthropic', {})),
        'groq':            GroqProvider(cfg.get('groq', {})),
        'openrouter':      OpenRouterProvider(cfg.get('openrouter', {})),
        # Specialized variants — best model per task
        'groq_120b':       GroqVariantProvider(cfg.get('groq_120b', {})),
        'groq_qwen3':      GroqVariantProvider(cfg.get('groq_qwen3', {})),
        'groq_llama4':     GroqVariantProvider(cfg.get('groq_llama4', {})),
        'or_coder':        OpenRouterVariantProvider(cfg.get('or_coder', {})),
        'or_hermes405b':   OpenRouterVariantProvider(cfg.get('or_hermes405b', {})),
        'or_nemotron120b': OpenRouterVariantProvider(cfg.get('or_nemotron120b', {})),
        'or_kimi':         OpenRouterVariantProvider(cfg.get('or_kimi', {})),
    }


def best_available(providers, preferred_order):
    """Return first available provider from preference list, else Ollama."""
    for name in preferred_order:
        p = providers.get(name)
        if p and p.available():
            return p
    return providers['ollama']
