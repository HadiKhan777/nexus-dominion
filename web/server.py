"""
NEXUS WebSocket Bridge — streams live state to the 3D brain visualization.
Pushes neural training, security, and AI thinking data at 10fps.
"""

import asyncio, json, threading, time
import http.server, socketserver, os
from pathlib import Path


# Simple async WebSocket server using stdlib only
class NexusWSServer:
    def __init__(self, neural, security, brain, port=8765):
        self.neural   = neural
        self.security = security
        self.brain    = brain
        self.port     = port
        self.clients  = set()
        self._thread  = None
        self._loop    = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            import websockets
            asyncio.run(self._serve())
        except ImportError:
            pass  # websockets not available, 3D vis won't get live data

    async def _serve(self):
        import websockets
        async def handler(ws, path=None):  # noqa
            self.clients.add(ws)
            try:
                async for msg in ws:
                    pass  # we only push, not receive
            except:
                pass
            finally:
                self.clients.discard(ws)

        async def broadcaster():
            while True:
                if self.clients:
                    state = self._get_state()
                    msg   = json.dumps(state)
                    dead  = set()
                    for ws in self.clients:
                        try:
                            await ws.send(msg)
                        except:
                            dead.add(ws)
                    self.clients -= dead
                await asyncio.sleep(0.1)  # 10fps

        async with websockets.serve(handler, 'localhost', self.port, reuse_port=True):
            await broadcaster()

    def _get_state(self):
        n = self.neural
        sec = self.security.get_status()
        return {
            'neural': {
                'epoch':    n.epoch,
                'max':      n.max_epoch,
                'loss':     round(n.loss, 4),
                'val_acc':  round(n.val_acc, 4),
                'lr':       n.lr,
                'status':   n.status,
                'layers':   n.layer_activations,
                'loss_hist': n.loss_history[-50:],
                'acc_hist':  n.acc_history[-50:],
            },
            'security': {
                'devices':   list(sec['devices'].keys()),
                'threat':    sec['threat_lvl'],
                'scan_pct':  sec['scan_pct'],
            },
            'brain': {
                'streaming':  self.brain.ai_streaming if hasattr(self.brain, 'ai_streaming') else False,
                'rag_docs':   self.brain.rag.indexed,
                'ollama_up':  self.brain.ollama.available,
            }
        }



def get_obsidian_graph():
    """Parse ~/claude-wiki into nodes + edges for the 3D visualization."""
    import re
    from pathlib import Path
    WIKI = Path.home() / 'claude-wiki' / 'wiki'
    TYPE_COLORS = {
        'project': '#c8ff00', 'entity/person': '#ff33aa',
        'entity/institution': '#ff8800', 'technology': '#00ccff',
        'concept': '#aa33ff', 'certification': '#ffcc00',
        'session': '#33ff88', 'chat-history': '#00ff99',
        'agent-log': '#ff6600', 'meta': '#666666',
    }
    nodes, edges, seen = [], [], set()
    try:
        for md in WIKI.rglob('*.md'):
            name = md.stem
            if name in ('hot','index','log','overview') or name.startswith('_'):
                continue
            text = md.read_text(errors='ignore')[:3000]
            m    = re.search(r'^type:\s*(.+)$', text, re.MULTILINE)
            ntype = m.group(1).strip() if m else 'other'
            color = TYPE_COLORS.get(ntype, '#444444')
            if name not in seen:
                nodes.append({'id': name, 'type': ntype, 'color': color})
                seen.add(name)
            for link in re.findall(r'\[\[([^\]|#]+)', text):
                link = link.strip()
                if link and link != name:
                    edges.append({'from': name, 'to': link})
    except Exception:
        pass
    return {'nodes': nodes[:120], 'edges': edges[:500]}

def start_http(port=8766):
    """Serve the 3D visualization HTML over HTTP."""
    web_dir = Path(__file__).parent
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(web_dir), **kw)
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == '/api/graph':
                import json as _j
                data = _j.dumps(get_obsidian_graph()).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            else:
                super().do_GET()

    class ReuseTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    def _serve():
        try:
            with ReuseTCPServer(('', port), Handler) as srv:
                srv.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    return f'http://localhost:{port}/brain_3d.html'
