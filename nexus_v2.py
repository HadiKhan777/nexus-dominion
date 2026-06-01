#!/usr/bin/env python3
"""
NEXUS DOMINION — Personal Intelligence System v2
8 live systems running in parallel from a single terminal.
"""

import sys, os, time, threading
sys.path.insert(0, os.path.dirname(__file__))

BOOT_ART = r"""
  ██████╗  ██████╗ ███╗   ███╗██╗███╗   ██╗██╗ ██████╗ ███╗   ██╗
  ██╔══██╗██╔═══██╗████╗ ████║██║████╗  ██║██║██╔═══██╗████╗  ██║
  ██║  ██║██║   ██║██╔████╔██║██║██╔██╗ ██║██║██║   ██║██╔██╗ ██║
  ██║  ██║██║   ██║██║╚██╔╝██║██║██║╚██╗██║██║██║   ██║██║╚██╗██║
  ██████╔╝╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██║╚██████╔╝██║ ╚████║
  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
"""

def boot(ui):
    time.sleep(0.4)
    steps = [
        (0, lambda: None,                          'Ollama'),
        (1, lambda: ui.rag.index_all(),            'Indexing 9800+ documents'),
        (2, lambda: ui.neural.start('spiral'),     'Neural trainer'),
        (3, lambda: ui.swarm.start(),              'Agent swarm (5 AIs)'),
        (4, lambda: None,                           'Camera vision (type /camera to enable)'),
        (5, lambda: ui.github.start(),             'GitHub feed'),
        (6, lambda: None,                          'All systems online'),
    ]
    for idx, fn, name in steps:
        ui.update_task(idx, 30)
        try:
            if idx == 1:
                t = threading.Thread(target=fn, daemon=True); t.start()
                for p in range(30, 100, 5):
                    ui.update_task(idx, p); time.sleep(0.15)
                t.join(timeout=20)
            else:
                fn()
        except Exception as e:
            ui.add_message('nexus', f'[{name}] warning: {e}')
        ui.update_task(idx, 100, done=True)
        time.sleep(0.2)

    olm = 'online' if ui.brain.ollama.available else 'offline (run: ollama serve)'
    ui.add_message('nexus',
        f'NEXUS DOMINION fully operational.\n'
        f'Ollama {olm} · {len(ui.rag.docs)} docs indexed · 5 agents live · camera {ui.vision.status}\n'
        f'8 systems running in parallel. What do you need?'
    )
    if ui.voice.enabled:
        ui.voice.speak('NEXUS Dominion online. All systems operational.')


def main():
    print('\x1b[2J\x1b[H\x1b[38;2;200;255;0m' + BOOT_ART + '\x1b[0m')
    print('\x1b[2m  8 parallel systems · RAG · Swarm · Vision · Voice · Security · GitHub · Neural · 3D\x1b[0m')
    print('\x1b[2m  Initializing...\x1b[0m')
    time.sleep(1.8)

    from brain.rag          import RAGEngine
    from brain.core         import Brain
    from brain.swarm        import AgentSwarm
    from brain.voice        import VoiceEngine
    from brain.vision       import VisionWorker
    from brain.github_feed  import GitHubFeed
    from brain.self_modify  import SelfModifyEngine
    from workers.neural_worker   import NeuralWorker
    from workers.security_worker import SecurityWorker
    from workers.file_watcher    import FileWatcher
    from ui.terminal_v2     import NexusTerminalV2
    from web.server         import NexusWSServer, start_http

    rag      = RAGEngine()
    neural   = NeuralWorker()
    security = SecurityWorker()
    security.start()

    from brain.memory import Memory
    memory      = Memory()
    from brain.providers      import build_providers
    from brain.obsidian_writer import ObsidianWriter
    providers   = build_providers()
    obs_writer  = ObsidianWriter()
    from brain.providers import best_available as _best
    chat_provider = _best(providers, ['groq', 'openrouter', 'ollama'])
    from brain.obsidian_chat_log import ObsidianChatLogger
    from brain.vision_ai        import VisionAI
    chat_log  = ObsidianChatLogger()
    vision_ai = VisionAI(providers=providers, memory=memory, obs_writer=obs_writer)
    brain     = Brain(rag, memory=memory, provider=chat_provider,
                      chat_log=chat_log, vision_ai=vision_ai)
    swarm       = AgentSwarm(rag, brain.ollama,
                             providers=providers, obs_writer=obs_writer)
    voice       = VoiceEngine()
    vision      = VisionWorker(device=0, width=36, height=12)
    # Camera is OFF by default — user enables with /camera
    github      = GitHubFeed('HadiKhan777')
    file_watch  = FileWatcher()
    file_watch.start()

    self_mod = SelfModifyEngine(brain)
    ui = NexusTerminalV2(brain, rag, neural, security, swarm, vision, github, voice,
                         file_watch=file_watch, self_modify=self_mod, memory=memory)

    # WebSocket bridge for 3D viz
    ws = NexusWSServer(neural, security, brain)
    ws.start()
    vis_url = start_http(8766)
    threading.Timer(4.0, lambda: __import__('subprocess').Popen(
        ['xdg-open', vis_url],
        stdout=__import__('subprocess').DEVNULL,
        stderr=__import__('subprocess').DEVNULL
    )).start()

    threading.Thread(target=boot, args=(ui,), daemon=True).start()
    ui.run()


if __name__ == '__main__':
    main()
