# NEXUS — Personal Intelligence System

A personal AI operating system that runs entirely on your local machine. No cloud required. No subscriptions. Everything from scratch.

```
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

## What it does

NEXUS is a full-screen terminal cockpit that runs 10 systems simultaneously:

- **Multi-provider AI brain** — routes queries to the best available model (Groq llama-3.3-70b, Groq gpt-oss-120b, Gemini, OpenRouter, or local Ollama). Falls back gracefully when providers are unavailable.
- **5-agent swarm** — CODER, TRAINER, GUARDIAN, ORACLE, ARCHITECT running in parallel threads. Each agent uses the model best suited to its specialty. `/consensus` fires all 5 at once and merges their answers.
- **RAG over 9,800+ local documents** — TF-IDF vector search over all your code, READMEs, notes, and past conversations. No external vector DB.
- **Persistent memory** — every conversation stored to disk, learned facts injected into every future prompt. Survives restarts.
- **Obsidian knowledge graph** — all conversations auto-logged as dated nodes in your knowledge base. Past chats become future context.
- **Live neural training** — runs a neural network in the background using NumPy only. Loss, accuracy, and per-layer activations visible in real time.
- **Network security monitor** — scans local subnet, tracks devices, identifies anomalies.
- **GitHub live feed** — real-time repo activity.
- **File watcher** — monitors your repos for changes as you code.
- **3D knowledge universe** — browser-based Three.js visualization showing your Obsidian graph as a live force-directed 3D network. Nodes colored by type, edges from wikilinks, updates every 30 seconds.

## Architecture

```
nexus/
├── nexus_v2.py              # Entry point — boots all 10 systems
├── brain/
│   ├── core.py              # AI brain: RAG + multi-provider + code executor
│   ├── providers.py         # Unified LLM client: Groq, Gemini, OpenRouter, DeepSeek, Kimi, Ollama
│   ├── swarm.py             # 5-agent swarm + consensus mode
│   ├── rag.py               # TF-IDF RAG engine — zero external dependencies
│   ├── memory.py            # Persistent memory (JSON, atomic writes)
│   ├── obsidian_writer.py   # Agents write findings to Obsidian knowledge graph
│   ├── obsidian_chat_log.py # Auto-log all conversations as Obsidian nodes
│   ├── github_feed.py       # Live GitHub activity feed
│   ├── self_modify.py       # NEXUS reads and improves its own source code
│   ├── voice.py             # TTS via espeak
│   ├── vision.py            # Camera feed with face detection (OpenCV)
│   └── websearch.py         # Web search via DuckDuckGo (no API key)
├── workers/
│   ├── neural_worker.py     # Live neural network training (NumPy only)
│   ├── security_worker.py   # Network scanner and device tracker
│   └── file_watcher.py      # Real-time file change monitor across repos
├── ui/
│   └── terminal_v2.py       # Full-screen ANSI cockpit at 20fps
└── web/
    ├── server.py             # WebSocket bridge + HTTP + /api/graph endpoint
    └── brain_3d.html         # Three.js knowledge universe (Obsidian graph in 3D)
```

## Setup

```bash
# Install dependencies
pip3 install numpy requests websockets evdev opencv-python

# Optional: install Ollama for local inference
# https://ollama.ai

# Run
cd nexus
python3 nexus_v2.py
```

## API Keys (all free)

Add your keys to `~/.nexus/providers.json`:

```json
{
  "groq":       {"api_key": "gsk_...",   "model": "llama-3.3-70b-versatile"},
  "gemini":     {"api_key": "AIza...",   "model": "gemini-1.5-flash"},
  "openrouter": {"api_key": "sk-or-...", "model": "meta-llama/llama-3.1-8b-instruct:free"}
}
```

- **Groq**: [console.groq.com](https://console.groq.com) — free, no credit card
- **Gemini**: [aistudio.google.com](https://aistudio.google.com) — free tier
- **OpenRouter**: [openrouter.ai](https://openrouter.ai) — 25+ free models

## Commands

| Command | Description |
|---------|-------------|
| `<anything>` | Ask the AI — uses RAG over your local files |
| `/consensus <question>` | All 5 agents answer in parallel, merged into one |
| `/swarm <task>` | Broadcast task to all agents simultaneously |
| `/agent CODER <task>` | Route to a specific agent |
| `/remember <fact>` | Commit to long-term memory |
| `/recall` | Show learned facts + session stats |
| `/search <query>` | Live web search |
| `/train moons` | Switch neural training dataset |
| `/evolve` | NEXUS reads its own code and suggests improvements |
| `/camera` | Toggle webcam (face detection, ASCII render) |
| `/3d` | Open knowledge universe in browser |
| `↑` / `↓` | Scroll chat history |

## Stack

Python · NumPy · Requests · WebSockets · OpenCV · Three.js · GLSL · WebGL · UnrealBloom

Zero cloud services. Everything runs on your machine.
