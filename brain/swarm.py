"""
NEXUS Agent Swarm — 5 specialized AI agents running in parallel.
Each agent has its own context, goal, and communication channel.
They share a message bus and can delegate to each other.
"""

import threading, queue, time, json, requests
from brain.obsidian_writer import ObsidianWriter
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentMessage:
    sender:  str
    target:  str     # agent name or 'broadcast'
    content: str
    mtype:   str = 'info'   # info | task | result | alert


class MessageBus:
    def __init__(self):
        self._queues = {}
        self._log    = []
        self._lock   = threading.Lock()

    def register(self, name):
        self._queues[name] = queue.Queue()

    def send(self, msg: AgentMessage):
        with self._lock:
            self._log.insert(0, msg)
            self._log = self._log[:50]
        if msg.target == 'broadcast':
            for q in self._queues.values():
                q.put_nowait(msg)
        elif msg.target in self._queues:
            self._queues[msg.target].put_nowait(msg)

    def recv(self, name, timeout=0.1):
        try:
            return self._queues[name].get(timeout=timeout)
        except queue.Empty:
            return None

    def recent(self, n=10):
        with self._lock:
            return list(self._log[:n])


AGENT_DEFS = {
    'CODER': {
        'icon': '⌨',
        'color': (0, 255, 150),
        'system': 'You are the CODER agent in NEXUS. You write Python code for any requested task. Always produce complete, working code. Be concise — code first, explanation after if needed.',
        'idle_task': 'Analyze your code quality. Identify one improvement.',
    },
    'TRAINER': {
        'icon': '⬡',
        'color': (170, 50, 255),
        'system': 'You are the TRAINER agent. You monitor and optimize machine learning training runs. Track loss, accuracy, learning rate. Suggest hyperparameter adjustments.',
        'idle_task': 'Analyze current neural training metrics and suggest next steps.',
    },
    'GUARDIAN': {
        'icon': '⚔',
        'color': (255, 60, 60),
        'system': 'You are the GUARDIAN agent. You monitor network security, track devices, identify anomalies. Be alert but not paranoid.',
        'idle_task': 'Review network topology and identify potential vulnerabilities.',
    },
    'ORACLE': {
        'icon': '◎',
        'color': (0, 200, 255),
        'system': 'You are the ORACLE agent. You synthesize knowledge from documents, code, and context. Answer questions with deep insight drawing from the knowledge base.',
        'idle_task': 'Surface one non-obvious insight from the indexed documents.',
    },
    'ARCHITECT': {
        'icon': '⬟',
        'color': (255, 180, 0),
        'system': 'You are the ARCHITECT agent. You design systems, plan projects, review architecture decisions. Think in systems and tradeoffs.',
        'idle_task': 'Evaluate the current NEXUS architecture and suggest one improvement.',
    },
}


class Agent:
    def __init__(self, name, config, bus, rag, ollama, provider=None, obs_writer=None):
        self.name       = name
        self.config     = config
        self.bus        = bus
        self.rag        = rag
        self.ollama     = ollama
        self.provider   = provider or ollama
        self.obs_writer = obs_writer

        self.status  = 'idle'
        self.thought = 'Initializing...'
        self.task    = ''
        self.history = []
        self._thread = None
        self._stop   = threading.Event()
        self._active = threading.Event()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name=f'agent-{self.name}', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def assign(self, task):
        self.task = task
        self._active.set()

    def _loop(self):
        self.bus.register(self.name)
        time.sleep(1 + list(AGENT_DEFS.keys()).index(self.name) * 0.5)
        self.status  = 'ready'
        self.thought = 'Standing by.'

        while not self._stop.is_set():
            # Check for incoming messages
            msg = self.bus.recv(self.name, timeout=0.2)
            if msg and msg.mtype == 'task':
                self._handle_task(msg.content)
                continue

            # Periodic autonomous thinking
            if not self._active.is_set():
                time.sleep(8 + list(AGENT_DEFS.keys()).index(self.name) * 3)
                if not self._stop.is_set():
                    self._idle_think()
            else:
                self._active.clear()
                if self.task:
                    self._handle_task(self.task)

    def _handle_task(self, task):
        self.status  = 'thinking'
        self.thought = task[:60] + '...'

        ctx   = self.rag.build_context(task) if self.rag.docs else ''
        hist  = '\n'.join(f'{r}: {m[:200]}' for r, m in self.history[-4:])
        prompt = f'{ctx}Previous:\n{hist}\nTask: {task}\nResponse:'

        result = []
        def tok(t):
            result.append(t)
            self.thought = ''.join(result)[-80:]

        pname = getattr(self.provider, 'name', 'Ollama')
        self.provider.stream(prompt, system=self.config['system'], on_token=tok)

        full = ''.join(result)
        # Strip <think>...</think> reasoning blocks (Qwen3 thinking model)
        import re as _re
        full = _re.sub(r'<think>.*?</think>', '', full, flags=_re.DOTALL).strip()
        self.history.append(('task', task))
        self.history.append(('result', full[:300]))
        self.status  = 'done'
        self.thought = full[:100] + ('...' if len(full) > 100 else '')

        if self.obs_writer and full.strip():
            self.obs_writer.log_finding(self.name, pname, self.task, full)

        self.bus.send(AgentMessage(
            sender=self.name, target='broadcast',
            content=f'[{self.name}/{pname}] {full[:200]}', mtype='result'
        ))
        time.sleep(2)
        self.status = 'idle'

    def _idle_think(self):
        self._handle_task(self.config['idle_task'])


# Provider assignment per agent — best available provider for each specialty
AGENT_PROVIDERS = {
    # GPU-accelerated preferred when available (NVIDIA NIM, Cerebras, Together, SambaNova)
    # Falls back to Groq (fast), then OpenRouter (free models), then Ollama (local)
    'CODER':     ['cerebras',    'nvidia',   'groq_qwen3',  'groq_llama4', 'groq',     'or_gpt20b',  'ollama'],
    'TRAINER':   ['ollama',      'groq',     'cerebras'],
    'GUARDIAN':  ['nvidia',      'cerebras', 'groq_120b',   'groq',        'or_gemma31b', 'ollama'],
    'ORACLE':    ['nvidia',      'together', 'sambanova',   'groq_120b',   'groq',     'or_gemma31b','ollama'],
    'ARCHITECT': ['nvidia',      'cerebras', 'groq_llama4', 'groq_120b',   'groq',     'ollama'],
}


class AgentSwarm:
    def __init__(self, rag, ollama, providers=None, obs_writer=None):
        self.bus        = MessageBus()
        self.providers  = providers or {}
        self.obs_writer = obs_writer or ObsidianWriter()

        from brain.providers import best_available
        self.agents = {}
        for name, cfg in AGENT_DEFS.items():
            preferred = AGENT_PROVIDERS.get(name, ['ollama'])
            provider  = best_available(self.providers, preferred) if self.providers else ollama
            self.agents[name] = Agent(
                name, cfg, self.bus, rag, ollama,
                provider=provider, obs_writer=self.obs_writer
            )

    def start(self):
        for agent in self.agents.values():
            agent.start()

    def stop(self):
        for agent in self.agents.values():
            agent.stop()

    def dispatch(self, task, target=None):
        """Send a task to a specific agent or let the swarm route it."""
        if target and target in self.agents:
            self.agents[target].assign(task)
        else:
            # Route intelligently based on keywords
            kw = task.lower()
            if any(w in kw for w in ['code','write','function','script','build']):
                self.agents['CODER'].assign(task)
            elif any(w in kw for w in ['train','loss','model','neural','epoch']):
                self.agents['TRAINER'].assign(task)
            elif any(w in kw for w in ['security','network','scan','threat','camera']):
                self.agents['GUARDIAN'].assign(task)
            elif any(w in kw for w in ['design','architecture','system','plan','structure']):
                self.agents['ARCHITECT'].assign(task)
            else:
                self.agents['ORACLE'].assign(task)

    def broadcast(self, task):
        """Send a task to ALL agents simultaneously."""
        self.bus.send(AgentMessage('user', 'broadcast', task, 'task'))

    def consensus(self, question, on_token=None, ollama=None):
        """
        Run all 5 agents on the SAME question in parallel, then synthesize
        their answers into a single consensus response.

        Each agent answers through the lens of its specialty, then a
        synthesis pass merges the distinct perspectives. This is the swarm's
        most powerful mode — five viewpoints collapsed into one answer.
        """
        import concurrent.futures

        ollama = ollama or next(iter(self.agents.values())).ollama
        results = {}

        def ask(agent):
            parts = []
            agent.status  = 'thinking'
            agent.thought = f'consensus: {question[:40]}...'
            ctx = agent.rag.build_context(question) if agent.rag.docs else ''
            prompt = f'{ctx}Question: {question}\nAnswer from your specialty in 2-3 sentences:'
            agent.ollama.stream(prompt, system=agent.config['system'],
                                on_token=lambda t: parts.append(t))
            agent.status  = 'done'
            text = ''.join(parts).strip()
            agent.thought = text[:80]
            return agent.name, text

        # Fan out to all agents at once
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(ask, a) for a in self.agents.values()]
            for fut in concurrent.futures.as_completed(futures):
                name, text = fut.result()
                results[name] = text

        # Synthesis pass — merge the 5 perspectives
        viewpoints = '\n'.join(
            f'[{name}]: {results.get(name, "(no answer)")}'
            for name in self.agents
        )
        synth_prompt = (
            f'Five specialist agents answered the question: "{question}"\n\n'
            f'{viewpoints}\n\n'
            f'Synthesize these into one clear, authoritative answer. '
            f'Resolve any disagreements. Be concise.'
        )
        synth_system = ('You are the NEXUS SYNTHESIZER. You merge multiple expert '
                        'opinions into a single coherent answer.')
        final = []
        def collect(t):
            final.append(t)
            if on_token:
                on_token(t)
        ollama.stream(synth_prompt, system=synth_system, on_token=collect)

        # Reset agents to idle
        for a in self.agents.values():
            a.status = 'idle'

        return {'perspectives': results, 'consensus': ''.join(final)}

    def status_snapshot(self):
        return [
            {
                'name':   name,
                'icon':   AGENT_DEFS[name]['icon'],
                'color':  AGENT_DEFS[name]['color'],
                'status': agent.status,
                'thought': agent.thought,
            }
            for name, agent in self.agents.items()
        ]
