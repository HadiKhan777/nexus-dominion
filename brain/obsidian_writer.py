"""
NEXUS Obsidian Writer — agents write findings into ~/claude-wiki.

Write permissions are locked to ALLOWED_WRITE_ROOTS only.
Any path outside that allowlist is silently refused.
"""

import threading, re
from datetime import datetime
from pathlib import Path

WIKI       = Path.home() / 'claude-wiki' / 'wiki'
AGENTS_DIR = WIKI / 'agents'

# Hard allowlist — agents can only write inside these directories
ALLOWED_ROOTS = [WIKI.resolve()]

def _safe(p: Path) -> bool:
    try:
        return any(p.resolve().is_relative_to(r) for r in ALLOWED_ROOTS)
    except Exception:
        return False


class ObsidianWriter:
    def __init__(self):
        self._lock = threading.Lock()
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    def log_finding(self, agent_name, provider_name, task, result):
        slug = re.sub(r'[^a-z0-9]+', '-', agent_name.lower())
        path = AGENTS_DIR / f'{slug}.md'
        if not _safe(path):
            return

        ts    = datetime.now().strftime('%Y-%m-%d %H:%M')
        entry = (f'\n## {ts} — {provider_name}\n'
                 f'**Task:** {task[:120]}\n\n'
                 f'{result[:500]}\n')

        with self._lock:
            if path.exists():
                with open(path, 'a') as f:
                    f.write(entry)
            else:
                header = (f'---\ntype: agent-log\nagent: {agent_name}\n'
                          f'provider: {provider_name}\ncreated: {ts}\n---\n\n'
                          f'# {agent_name} Agent Log\n\n'
                          f'Related: [[nexus-project]] · [[hadi-khan]]\n')
                path.write_text(header + entry)

    def write_insight(self, title, content, tags=None):
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:50]
        path = WIKI / 'concepts' / f'ai-insight-{slug}.md'
        if not _safe(path):
            return
        tags = tags or []
        ts   = datetime.now().strftime('%Y-%m-%d')

        with self._lock:
            if path.exists():
                with open(path, 'a') as f:
                    f.write(f'\n## Updated {ts}\n{content[:800]}\n')
            else:
                node = (f'---\ntype: concept\ntags: [{", ".join(tags)}]\n'
                        f'created: {ts}\nsource: nexus-agent\n---\n\n'
                        f'# {title}\n\n{content[:800]}\n\n'
                        f'## Related\n[[nexus-project]] · [[hadi-khan]]\n')
                path.write_text(node)

    def recent_agent_context(self, agent_name, n=3):
        slug = re.sub(r'[^a-z0-9]+', '-', agent_name.lower())
        path = AGENTS_DIR / f'{slug}.md'
        if not path.exists():
            return ''
        text     = path.read_text()
        sections = re.split(r'\n## ', text)
        recent   = sections[-n:] if len(sections) > n else sections[1:]
        if not recent:
            return ''
        return f'[{agent_name} recent findings]\n' + '\n---\n'.join(recent)
