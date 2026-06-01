"""
NEXUS Self-Modification Engine — NEXUS can read, analyze, and propose
improvements to its own source code, then apply them with confirmation.
"""

import os, subprocess
from pathlib import Path


NEXUS_ROOT = Path(__file__).parent.parent


class SelfModifyEngine:
    def __init__(self, brain):
        self.brain     = brain
        self.proposals = []   # pending modifications
        self.applied   = []   # applied modifications

    def analyze_self(self, on_token):
        """Read own source, ask LLM to find improvements."""
        # Gather key source files
        files = [
            NEXUS_ROOT / 'brain' / 'core.py',
            NEXUS_ROOT / 'brain' / 'swarm.py',
            NEXUS_ROOT / 'ui'    / 'terminal_v2.py',
        ]
        sources = []
        for f in files:
            if f.exists():
                code = f.read_text()[:2000]
                sources.append(f'# {f.name}\n{code}')

        prompt = (
            'You are analyzing NEXUS, a personal AI system. '
            'Review this source code and identify ONE specific, concrete improvement. '
            'Describe exactly what file to change, what line to find, and what the new code should be. '
            'Be precise — give actual code, not suggestions.\n\n'
            + '\n\n'.join(sources[:2])
        )
        self.brain.ollama.stream(prompt, on_token=on_token)

    def read_file(self, filename):
        """Read a NEXUS source file."""
        p = NEXUS_ROOT / filename
        if p.exists() and p.suffix in ('.py', '.js', '.html', '.md'):
            return p.read_text()
        return None

    def apply(self, filename, old_code, new_code):
        """Apply a modification — only allowed inside ~/nexus/."""
        p = (NEXUS_ROOT / filename).resolve()
        if not str(p).startswith(str(NEXUS_ROOT.resolve())):
            return False, 'Refused: path escapes nexus root'
        if not p.exists():
            return False, 'File not found'
        content = p.read_text()
        if old_code not in content:
            return False, 'Old code not found in file'
        new_content = content.replace(old_code, new_code, 1)
        # Backup
        backup = p.with_suffix(p.suffix + '.bak')
        backup.write_text(content)
        p.write_text(new_content)
        self.applied.append({'file': filename, 'old': old_code[:80], 'new': new_code[:80]})
        return True, f'Applied to {filename} (backup: {backup.name})'

    def git_diff(self):
        """Show what NEXUS has changed in its own repo."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--stat'],
                capture_output=True, text=True,
                cwd=str(NEXUS_ROOT), timeout=5
            )
            return result.stdout or 'No changes'
        except:
            return 'git not available'
