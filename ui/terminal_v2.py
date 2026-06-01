"""
NEXUS Terminal v2 — full-screen ANSI cockpit at 20fps.
Code rain background · holographic panels · agent swarm · camera · voice · github
"""

import sys, os, time, threading, textwrap, random, math
from datetime import datetime
from pathlib import Path


# ── ANSI primitives ───────────────────────────────────────────────────────────

ESC = '\x1b'
def mv(r,c):      return f'{ESC}[{r};{c}H'
def hide():       return f'{ESC}[?25l'
def show():       return f'{ESC}[?25h'
def alt():        return f'{ESC}[?1049h'
def norm():       return f'{ESC}[?1049l'
def rst():        return f'{ESC}[0m'
def bold():       return f'{ESC}[1m'
def dim():        return f'{ESC}[2m'
def blink():      return f'{ESC}[5m'
def rgb(r,g,b):   return f'{ESC}[38;2;{r};{g};{b}m'
def bgrgb(r,g,b): return f'{ESC}[48;2;{r};{g};{b}m'
def clrline():    return f'{ESC}[2K'

import re
def strip(s):     return re.sub(r'\x1b\[[0-9;]*m', '', s)

def vlen(s):      return len(strip(s))

def pad(s, w):
    v = vlen(s)
    return s + ' ' * max(0, w - v)

def gradient(text, r1,g1,b1, r2,g2,b2):
    n = max(len(text)-1, 1)
    out = []
    for i, ch in enumerate(text):
        t = i/n
        out.append(f'{rgb(int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))}{ch}')
    return ''.join(out) + rst()

def bar(pct, w=20, fc=(200,255,0), ec=(25,25,25)):
    f = int(pct*w/100)
    return rgb(*fc)+'█'*f + rst() + rgb(*ec)+'░'*(w-f)+rst()

def sparkline(data, w=30):
    chars = '▁▂▃▄▅▆▇█'
    if not data: return dim()+'─'*w+rst()
    window = list(data[-w:])
    mn, mx = min(window), max(window)
    rng = mx-mn or 1
    return ''.join(chars[min(7,int((v-mn)/rng*7.99))] for v in window)

SPIN = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
GLITCH = ['▓','▒','░','█','▄','▀','■','□','▪','▫']


# ── Code Rain engine ─────────────────────────────────────────────────────────

class CodeRain:
    """Samples real code from repos and renders falling columns."""

    def __init__(self, cols, rows):
        self.cols  = cols
        self.rows  = rows
        self.drops = []
        self.code_chars = []
        self._load_chars()
        self._init_drops()

    def _load_chars(self):
        """Load character pool from actual code files."""
        chars = set('abcdefghijklmnopqrstuvwxyz0123456789(){}[];:=+->.<>/!|&_*%#@')
        try:
            paths = []
            for repo in ['neuralkit','nanohttp','gitlet','tui','kontainer','pipecraft']:
                p = Path.home() / repo
                if p.exists():
                    paths += list(p.rglob('*.py'))[:2] + list(p.rglob('*.js'))[:2]
            for path in paths[:10]:
                try:
                    text = path.read_text(errors='ignore')
                    chars.update(c for c in text if c.isprintable() and c != ' ')
                except:
                    pass
        except:
            pass
        self.code_chars = list(chars)[:80]
        if not self.code_chars:
            self.code_chars = list('abcdefghijklmnopqrstuvwxyz0123456789(){}=><;')

    def _init_drops(self):
        self.drops = []
        for c in range(self.cols):
            self.drops.append({
                'col': c,
                'row': random.randint(-self.rows, 0),
                'speed': random.choice([1, 1, 1, 2]),
                'length': random.randint(4, 14),
                'chars': [random.choice(self.code_chars) for _ in range(20)],
                'bright': random.random() > 0.85,
            })

    def render_cell(self, row, col):
        """Return ANSI char for (row,col) based on current drop state."""
        for drop in self.drops:
            if drop['col'] != col:
                continue
            head = drop['row']
            dist = head - row
            if dist == 0:
                # Head of drop — brightest
                ch = random.choice(drop['chars'])
                if drop['bright']:
                    return rgb(255,255,255) + ch + rst()
                return rgb(200,255,0) + ch + rst()
            elif 0 < dist <= drop['length']:
                # Tail — fade to dim
                fade = 1.0 - dist/drop['length']
                g    = int(fade * 180)
                ch   = drop['chars'][dist % len(drop['chars'])]
                return rgb(0,g,0) + ch + rst()
        return ' '

    def tick(self):
        for drop in self.drops:
            drop['row'] += drop['speed']
            if drop['row'] - drop['length'] > self.rows:
                drop['row']   = random.randint(-8, 0)
                drop['speed'] = random.choice([1,1,1,2])
                drop['length']= random.randint(4,14)
                drop['bright']= random.random() > 0.85
                drop['chars'] = [random.choice(self.code_chars) for _ in range(20)]

    def render_stripe(self, row, col_start, col_end):
        """Render a horizontal stripe of rain (for background)."""
        parts = []
        for c in range(col_start, col_end):
            parts.append(self.render_cell(row, c))
        return ''.join(parts)


# ── Panel renderer ────────────────────────────────────────────────────────────

class NexusTerminalV2:
    def __init__(self, brain, rag, neural, security, swarm, vision, github, voice,
                 file_watch=None, self_modify=None, memory=None):
        self.brain    = brain
        self.rag      = rag
        self.neural   = neural
        self.security = security
        self.swarm    = swarm
        self.vision   = vision
        self.github   = github
        self.voice    = voice

        self.messages   = []
        self.input_buf  = ''
        self.tasks      = [
            {'name':'Ignite Ollama brain',      'pct':0,'done':False},
            {'name':'Index 9800+ documents',    'pct':0,'done':False},
            {'name':'Launch neural trainer',    'pct':0,'done':False},
            {'name':'Spawn agent swarm (5)',    'pct':0,'done':False},
            {'name':'Open camera vision',       'pct':0,'done':False},
            {'name':'Connect GitHub feed',      'pct':0,'done':False},
            {'name':'NEXUS online',             'pct':0,'done':False},
        ]

        self.file_watch  = file_watch
        self.self_modify = self_modify
        self.memory      = memory
        self.spin_idx    = 0
        self.ai_stream   = False
        self.cur_resp    = ''
        self.glitch_mode = False
        self.glitch_tick = 0
        self._running    = False
        self._buf        = []
        self._rlock      = threading.Lock()
        self.rain        = None
        self.rain_tick   = 0
        self.chat_scroll = 0   # lines scrolled up (0 = at bottom)
        # Command history recall (up/down arrows)
        self.cmd_history = list(memory.command_history()) if memory else []
        self.hist_idx    = len(self.cmd_history)   # points past the end
        self.saved_buf   = ''                       # buffer stashed during recall
        # Tab completion
        self.COMMANDS = ['/swarm','/consensus','/agent','/train','/search','/remember',
                         '/recall','/evolve','/diff','/camera','/voice','/scan','/3d',
                         '/clear','/help','/quit']

    def w(self, *p):   self._buf.append(''.join(str(x) for x in p))
    def flush(self):   sys.stdout.write(''.join(self._buf)); sys.stdout.flush(); self._buf.clear()

    # ── Layout ────────────────────────────────────────────────────────────────

    def render(self):
        with self._rlock:
            cols, rows = self._size()
            self._buf.clear()
            self.w(mv(1,1))

            # Code rain background (only on empty areas)
            if self.rain and self.rain_tick % 2 == 0:
                self.rain.tick()
            self.rain_tick += 1

            self._header(cols, rows)
            self._layout(cols, rows)
            self._footer(cols, rows)
            self.flush()
        self.spin_idx = (self.spin_idx + 1) % len(SPIN)

    def _size(self):
        import shutil
        # Try /dev/tty first (works even when stdin is redirected)
        try:
            with open('/dev/tty') as tty:
                s = os.get_terminal_size(tty.fileno())
                if s.columns > 20 and s.lines > 10:
                    return s.columns, s.lines
        except:
            pass
        # shutil checks COLUMNS/LINES env vars then stdout/stderr
        s = shutil.get_terminal_size(fallback=(180, 50))
        if s.columns > 20 and s.lines > 10:
            return s.columns, s.lines
        return 180, 50

    def _header(self, cols, rows):
        t = datetime.now().strftime('%H:%M:%S')
        spin = rgb(200,255,0)+SPIN[self.spin_idx]+rst() if self.ai_stream else rgb(0,80,0)+'●'+rst()

        pname  = getattr(self.brain.provider, 'name', 'Ollama')
        ollama = rgb(50,255,100)+'●'+rst() if self.brain.provider.available() else rgb(80,80,80)+'○'+rst()
        docs         = str(self.rag.indexed)
        agents_alive = sum(1 for a in self.swarm.agents.values() if a.status != 'idle')

        title = gradient('NEXUS',200,255,0,0,255,200) + dim()+'  //  DOMINION'+rst()

        # Build right side as plain text first to measure, then color
        right_plain = f'● OLLAMA  DOCS:{docs}  AGENTS:{agents_alive}/5  {t}'
        right_col   = max(1, cols - len(right_plain) - 2)
        right_full  = f'{spin} {ollama}{dim()} {pname}{rst()}  {dim()}DOCS:{rst()}{rgb(200,255,0)}{docs}{rst()}  {dim()}AGENTS:{rst()}{rgb(0,255,180)}{agents_alive}/5{rst()}  {dim()}{t}{rst()}'

        self.w(mv(1,1), bgrgb(2,2,8), ' '*cols, rst())
        self.w(mv(1,2), title)
        self.w(mv(1, right_col), right_full, rst())
        self.w(mv(2,1), rgb(20,20,40)+'─'*cols+rst())

    def _layout(self, cols, rows):
        body  = max(10, rows - 5)
        left  = max(30, int(cols * 0.42))
        mid   = max(20, int(cols * 0.30))
        right = max(15, cols - left - mid - 2)

        # LEFT: AI chat
        self._panel_chat(3, 1, left, body)

        # Divider 1
        for r in range(3, 3+body):
            self.w(mv(r, left+1), rgb(15,30,15)+'│'+rst())

        # MID col: Neural + Agents
        mid_half = body // 2
        self._panel_neural(3,           left+2, mid, mid_half)
        self._panel_agents(3+mid_half,  left+2, mid, body-mid_half)

        # Divider 2
        for r in range(3, 3+body):
            self.w(mv(r, left+mid+2), rgb(15,30,15)+'│'+rst())

        # RIGHT col: 5 panels
        right_x = left+mid+3
        q = max(3, body // 5)
        self._panel_camera(      3,         right_x, right, q+1)
        self._panel_security(    3+q+1,     right_x, right, q)
        self._panel_github(      3+q*2+1,   right_x, right, q)
        self._panel_filewatcher( 3+q*3+1,   right_x, right, q)
        self._panel_tasks(       3+q*4+1,   right_x, right, max(3, body-q*4-1))

    def _fmt_message(self, text, width, col_fn, cont_color):
        """
        Paragraph-aware formatter. Handles:
        - Blank lines between paragraphs (visual gap)
        - Fenced code blocks (``` ... ```) with different color
        - Proper word wrapping per paragraph
        Returns list of (prefix_char, styled_line) tuples.
        """
        out      = []
        in_code  = False
        paras    = text.split('\n')
        tw       = max(8, width - 4)

        for raw_line in paras:
            stripped = raw_line.strip()

            # Code fence toggle
            if stripped.startswith('```'):
                in_code = not in_code
                if in_code:
                    lang = stripped[3:].strip() or 'code'
                    out.append(('', rgb(100,100,100)+'── '+lang+' ─'*(max(0,tw-5-len(lang)))+''+rst()))
                else:
                    out.append(('', rgb(100,100,100)+'─'*tw+rst()))
                continue

            if in_code:
                # Code lines: monospace dim cyan, no wrap
                out.append(('  ', rgb(80,200,200)+raw_line[:tw]+rst()))
                continue

            if stripped == '':
                # Blank line = paragraph separator
                out.append(('', ''))
                continue

            # Normal text: wrap to width
            chunks = textwrap.wrap(stripped, tw) or ['']
            for i, chunk in enumerate(chunks):
                out.append(('  ' if i > 0 else None, col_fn(chunk)))

        return out

    def _panel_chat(self, row, col, w, h):
        streaming = self.ai_stream
        hdr      = gradient('◈ AI BRAIN',200,255,0,0,255,180)
        mode_txt = (SPIN[self.spin_idx]+' STREAMING ') if streaming else ('● READY       ')
        mode_col = rgb(200,255,0) if streaming else dim()
        mode     = mode_col + mode_txt + rst()

        # Scroll indicator
        total_scrollable = max(0, self.chat_scroll)
        scroll_info = (dim()+f' ↑{total_scrollable}ln '+rst()) if total_scrollable > 0 else ''
        self.w(mv(row,col), hdr, dim()+'  '+rst(), mode, scroll_info)

        border_char = GLITCH[self.spin_idx % len(GLITCH)] if streaming else '─'
        self.w(mv(row+1,col), rgb(0,60,0)+border_char*(w-1)+rst())

        # Build all lines
        avail = h - 4
        lines = []

        for role, text in self.messages:
            if role == 'user':
                pfx    = rgb(200,255,0)+bold()+'▸ '+rst()
                cfn    = lambda s: rgb(220,255,100)+s+rst()
                ccol   = rgb(220,255,100)
            else:
                pfx    = rgb(0,220,180)+bold()+'⬡ '+rst()
                cfn    = lambda s: rgb(180,220,200)+s+rst()
                ccol   = rgb(180,220,200)

            parts = self._fmt_message(text, w, cfn, ccol)
            for idx, (cont, styled) in enumerate(parts):
                actual_pre = pfx if idx == 0 else (cont if cont is not None else '  ')
                lines.append((actual_pre, styled))
            lines.append(('', ''))  # gap between messages

        # Streaming
        if self.cur_resp:
            spin_char = rgb(0,200,160)+GLITCH[self.spin_idx % len(GLITCH)]+' '+rst()
            for idx, chunk in enumerate(textwrap.wrap(self.cur_resp, max(8,w-4)) or ['']):
                pre = spin_char if idx == 0 else '  '
                lines.append((pre, rgb(180,230,200)+chunk+rst()))

        # Apply scroll: 0 = bottom, positive = scrolled up
        total = len(lines)
        if self.chat_scroll > 0:
            end   = max(avail, total - self.chat_scroll)
            start = max(0, end - avail)
            display = lines[start:end]
        else:
            display = lines[-avail:]

        # Render
        for i, (pre, txt) in enumerate(display):
            self.w(mv(row+2+i, col), ' '*(w-1))
            if pre == '' and txt == '':
                continue  # blank gap line — already cleared
            pre_w = vlen(strip(pre))
            max_c = max(1, w - pre_w - 2)
            vis   = strip(txt)
            if len(vis) > max_c:
                ansi_extra = len(txt) - len(vis)
                txt = txt[:max_c + ansi_extra]
            self.w(mv(row+2+i, col), pre, txt)

        for i in range(len(display), avail):
            self.w(mv(row+2+i, col), ' '*(w-1))

        # Scroll arrows on right edge
        if total > avail:
            self.w(mv(row+2,    col+w-2), dim()+'↑'+rst())
            self.w(mv(row+h-3,  col+w-2), dim()+'↓'+rst())
            pct  = min(avail-1, int((1 - self.chat_scroll/max(1,total-avail)) * (avail-2)))
            self.w(mv(row+2+pct, col+w-2), rgb(200,255,0)+'█'+rst())

        # Divider + input
        self.w(mv(row+h-2, col), rgb(0,40,0)+'─'*(w-1)+rst())
        caret = rgb(200,255,0)+'█'+rst() if not streaming else blink()+rgb(0,200,100)+'▮'+rst()
        max_d = max(1, w - 5)
        disp  = self.input_buf[-max_d:]
        trail = ' ' * max(0, max_d - len(disp))
        self.w(mv(row+h-1,col), rgb(0,100,50)+bold()+'▸ '+rst(), disp, caret, trail)

    def _panel_neural(self, row, col, w, h):
        n = self.neural
        pulse = '⬡' if n.status == 'training' else ('✓' if n.status == 'done' else '○')
        col_s = (lambda s: rgb(170,50,255)+s+rst()) if n.status == 'training' else \
                (lambda s: rgb(50,255,100)+s+rst()) if n.status == 'done' else \
                (lambda s: dim()+s+rst())

        self.w(mv(row,col), gradient('◈ NEURAL',170,50,255,100,0,255), dim()+f'  {n.dataset.upper()}  '+rst(), col_s(f'{pulse} {n.status.upper()}'))
        self.w(mv(row+1,col), rgb(30,15,40)+'─'*(w-1)+rst())

        ep  = int(n.epoch / max(n.max_epoch,1)*100)
        self.w(mv(row+2,col), dim()+'epoch '+rst(), rgb(200,200,255)+f'{n.epoch:3d}/{n.max_epoch}'+rst(), '  ', bar(ep, min(w-18,16),(170,50,255),(20,10,30)), f' {ep:3d}%')

        lc = (255,80,80) if n.loss>0.3 else (255,180,0) if n.loss>0.05 else (50,255,100)
        ac = (50,255,100) if n.val_acc>0.9 else (255,200,0)
        self.w(mv(row+3,col), dim()+'loss '+rst(), rgb(*lc)+f'{n.loss:.4f}'+rst(), dim()+'  acc '+rst(), rgb(*ac)+f'{n.val_acc:.4f}'+rst(), dim()+f'  lr '+rst(), rgb(0,200,255)+f'{n.lr:.2e}'+rst())

        # Layer activity bars
        self.w(mv(row+4,col), dim()+'layers '+rst())
        for i, act in enumerate(n.layer_activations[:min(6,w//4)]):
            c = (int(50+act*120), int(50+act*200), int(act*255))
            filled = int(act*3)
            self.w(rgb(*c)+'█'*filled+rst()+dim()+'░'*(3-filled)+rst()+' ')

        if h > 5:
            self.w(mv(row+5,col), dim()+'loss  '+rst(), rgb(170,50,255), sparkline(n.loss_history, w-8), rst())
        if h > 6:
            self.w(mv(row+6,col), dim()+'acc   '+rst(), rgb(50,255,100), sparkline(n.acc_history, w-8), rst())

    def _panel_agents(self, row, col, w, h):
        self.w(mv(row,col), gradient('◈ AGENT SWARM',255,140,0,255,50,100), dim()+'  5 PARALLEL AIs'+rst())
        self.w(mv(row+1,col), rgb(40,20,10)+'─'*(w-1)+rst())

        agents = self.swarm.status_snapshot()
        for i, ag in enumerate(agents[:min(h-3,5)]):
            r,g,b = ag['color']
            icon  = ag['icon']
            name  = ag['name']
            stat  = ag['status']
            thought = ag['thought'][:max(w-18,10)]

            # Status dot
            if stat == 'thinking':
                sdot = rgb(r,g,b)+SPIN[self.spin_idx]+rst()
            elif stat == 'done':
                sdot = rgb(50,255,100)+'✓'+rst()
            else:
                sdot = dim()+'○'+rst()

            self.w(mv(row+2+i, col),
                   sdot, ' ',
                   rgb(r,g,b)+bold()+f'{icon} {name:<8}'+rst(), ' ',
                   dim()+thought+rst())

        # Message bus feed
        recent = self.swarm.bus.recent(1)
        if recent and h > 8:
            msg = recent[0]
            self.w(mv(row+h-1,col), dim()+f'⇝ [{msg.sender}] {msg.content[:w-12]}'+rst())

    def _panel_camera(self, row, col, w, h):
        frame, faces, fps = self.vision.get_frame()
        status = self.vision.status

        face_str = (rgb(50,255,100)+f'● {faces} FACE{"S" if faces!=1 else ""}'+rst()) if faces > 0 else dim()+'○ NO FACE'+rst()
        self.w(mv(row,col), gradient('◈ VISION',255,100,0,255,200,0), dim()+f'  {status.upper()}  '+rst(), face_str, dim()+f'  {fps}fps'+rst())
        self.w(mv(row+1,col), rgb(40,20,0)+'─'*(w-1)+rst())

        if status == 'live' and frame:
            for i, line in enumerate(frame[:h-3]):
                if row+2+i >= row+h: break
                self.w(mv(row+2+i,col))
                # Trim to width
                visible = strip(line)
                trim_at = min(len(visible), w-1) * 2  # approximate
                self.w(line[:trim_at*3], rst())  # extra chars for ANSI overhead
        else:
            msgs = {
                'no-opencv':  ['OpenCV not found.','pip3 install opencv-python'],
                'no-device':  ['Camera not found.','Check /dev/video0'],
                'off':        ['Vision offline.', 'Camera disabled.'],
                'connecting': ['Initializing...'],
            }
            for i, m in enumerate(msgs.get(status, [status])[:h-3]):
                self.w(mv(row+2+i,col), dim()+m+rst())

    def _panel_security(self, row, col, w, h):
        sec = self.security.get_status()
        thr = sec['threat_lvl']
        thr_c = rgb(50,255,100) if thr=='LOW' else rgb(255,180,0) if thr=='MED' else rgb(255,50,50)

        self.w(mv(row,col), gradient('◈ SECURITY',255,50,50,255,150,0), dim()+'  THREAT: '+rst(), thr_c+thr+rst())
        self.w(mv(row+1,col), rgb(40,10,10)+'─'*(w-1)+rst())

        for i, (ip, info) in enumerate(list(sec['devices'].items())[:h-3]):
            name   = info.get('name','?')[:14]
            threat = info.get('threat','?')
            alive  = info.get('alive', True)
            dot = rgb(50,255,100)+'●'+rst() if alive else dim()+'○'+rst()
            tc  = rgb(50,255,100) if threat=='SAFE' else rgb(255,180,0) if 'TOKEN' in threat else rgb(255,50,50)
            row_txt = (dot+' '+dim()+ip[:14].ljust(14)+rst()+
                        ' '+dim()+name[:10].ljust(10)+rst()+'  '+tc+threat[:8]+rst())
            if vlen(strip(row_txt)) < w:
                self.w(mv(row+2+i,col), row_txt)

    def _panel_github(self, row, col, w, h):
        events, stars, last = self.github.get_feed()
        self.w(mv(row,col), gradient("◈ GITHUB",0,200,255,0,255,200),
               dim()+f'  HadiKhan777  '+rst(), rgb(255,220,0)+f'★{stars}'+rst())
        self.w(mv(row+1,col), rgb(10,20,40)+'─'*(w-1)+rst())

        for i, ev in enumerate(events[:h-3]):
            repo = ev['repo'][:12]
            age  = ev['age']
            lang = ev.get('lang','—')[:5]
            lc   = (0,200,255) if lang in ('JavaS','Node.') else (200,255,0) if lang=='Pytho' else (255,140,0)
            self.w(mv(row+2+i,col),
                   rgb(*lc)+f'{lang:<5}'+rst(), ' ',
                   rgb(200,255,220)+repo.ljust(12)+rst(), ' ',
                   dim()+age+rst())

    def _panel_filewatcher(self, row, col, w, h):
        events = self.file_watch.recent(h-3) if self.file_watch else []
        self.w(mv(row,col), gradient('◈ LIVE FILES',0,200,255,0,255,150),
               dim()+f'  watching {len(self.file_watch.watching if self.file_watch else [])} repos'+rst())
        self.w(mv(row+1,col), rgb(0,30,30)+'─'*(w-1)+rst())

        if not events:
            self.w(mv(row+2,col), dim()+'No changes detected yet...'+rst())
            return

        ext_colors = {'.py':(200,255,0),'.js':(255,220,0),'.ts':(0,150,255),
                      '.rs':(255,100,0),'.md':(150,150,255),'.html':(255,80,80)}
        for i, ev in enumerate(events[:h-3]):
            ec  = ext_colors.get(ev['ext'], (150,150,150))
            self.w(mv(row+2+i,col),
                   rgb(*ec)+ev['ext'][1:].upper().ljust(3)+rst(), ' ',
                   rgb(0,200,180)+ev['repo'][:8].ljust(8)+rst(), ' ',
                   dim()+ev['file'][:w-18]+rst(), ' ',
                   rgb(80,80,80)+ev['time']+rst())

    def _panel_tasks(self, row, col, w, h):
        self.w(mv(row,col), gradient('◈ BOOT',255,200,0,255,100,0))
        self.w(mv(row+1,col), rgb(40,30,0)+'─'*(w-1)+rst())

        for i, task in enumerate(self.tasks[:h-3]):
            if task['done']:
                ind = rgb(50,255,100)+'✓'+rst()
                b   = bar(100, min(w-18,12),(50,255,100),(10,30,10))
            elif task['pct']>0:
                ind = rgb(255,180,0)+SPIN[self.spin_idx]+rst()
                b   = bar(task['pct'], min(w-18,12),(255,180,0),(30,20,5))
            else:
                ind = dim()+'○'+rst()
                b   = bar(0, min(w-18,12),(60,60,60),(20,20,20))
            self.w(mv(row+2+i,col), ind,' ',dim()+task['name'][:w-18]+rst(),' ',b)

    def _footer(self, cols, rows):
        self.w(mv(max(3,rows-2),1), rgb(10,30,10)+'─'*cols+rst())
        pairs = [
            (rgb(200,255,0),   '/swarm',   ' all agents'),
            (rgb(0,255,180),   '/train',   ' dataset'),
            (rgb(0,200,255),   '/search',  ' web'),
            (rgb(255,180,0),   '/agent',   ' NAME task'),
            (rgb(170,50,255),  '/evolve',  ' self-modify'),
            (rgb(255,100,0),   '/camera',  ' toggle'),
            (rgb(80,200,255), '/3d',      ''),
            (rgb(255,50,100),  '/quit',    ''),
        ]
        cmds = '  '.join(c+k+rst()+dim()+v+rst() for c,k,v in pairs)
        self.w(mv(max(4,rows-1),1), dim()+'▸ '+rst(), cmds)

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_key(self, key):
        # ── Escape sequence state machine (arrow keys) ──────────────────────
        esc = getattr(self, '_esc', '')
        if esc:
            esc += key
            # Still building sequence
            if esc in ('\x1b[', '\x1b[<', '\x1b[5', '\x1b[6'):
                self._esc = esc
                return True
            self._esc = ''
            # Arrow keys
            if   esc == '\x1b[A': self._history_prev()       # up arrow
            elif esc == '\x1b[B': self._history_next()       # down arrow
            # Page Up / Page Down
            elif esc == '\x1b[5~': self.chat_scroll += 8     # Page Up
            elif esc == '\x1b[6~': self.chat_scroll = max(0, self.chat_scroll - 8)  # Page Down
            # Ctrl+Home / Ctrl+End
            elif esc == '\x1b[1~': self.chat_scroll = 9999   # scroll to top
            elif esc == '\x1b[4~': self.chat_scroll = 0      # scroll to bottom (End)
            # Mouse wheel (xterm: \x1b[<64;..M = up, 65 = down) — partial match ok
            elif 'M' in esc and '<64;' in esc: self.chat_scroll += 3
            elif 'M' in esc and '<65;' in esc: self.chat_scroll = max(0, self.chat_scroll - 3)
            return True
        if key == '\x1b':
            self._esc = '\x1b'
            return True
        # Mouse scroll wheel (xterm SGR: \x1b[<64;x;yM = wheel up, 65 = wheel down)
        if key == '\x1b' and getattr(self, '_esc', '') == '':
            self._esc = '\x1b'
            return True

        # ── Normal keys ─────────────────────────────────────────────────────
        if key in ('\r','\n'):
            self._submit()
        elif key in ('\x7f','\x08'):
            self.input_buf = self.input_buf[:-1]
        elif key == '\x03':                       # Ctrl-C
            return False
        elif key == '\x15':                       # Ctrl-U clear line
            self.input_buf = ''
        elif key == '\t':                         # Tab completion
            self._tab_complete()
        elif len(key)==1 and ord(key)>=32:
            self.input_buf += key
        return True

    def _history_prev(self):
        if not self.cmd_history:
            return
        if self.hist_idx == len(self.cmd_history):
            self.saved_buf = self.input_buf       # stash what was being typed
        self.hist_idx = max(0, self.hist_idx - 1)
        self.input_buf = self.cmd_history[self.hist_idx]

    def _history_next(self):
        if not self.cmd_history:
            return
        if self.hist_idx >= len(self.cmd_history):
            return
        self.hist_idx += 1
        if self.hist_idx == len(self.cmd_history):
            self.input_buf = self.saved_buf       # restore the in-progress line
        else:
            self.input_buf = self.cmd_history[self.hist_idx]

    def _tab_complete(self):
        buf = self.input_buf
        if not buf.startswith('/'):
            return
        matches = [c for c in self.COMMANDS if c.startswith(buf)]
        if len(matches) == 1:
            self.input_buf = matches[0] + ' '
        elif len(matches) > 1:
            # Complete to the longest common prefix
            prefix = matches[0]
            for m in matches[1:]:
                while not m.startswith(prefix):
                    prefix = prefix[:-1]
            self.input_buf = prefix
            self.messages.append(('nexus', 'completions: ' + '  '.join(matches)))

    def _submit(self):
        text = self.input_buf.strip()
        if not text: return
        self.input_buf = ''
        # Record to command history (in-RAM + persistent)
        self.cmd_history.append(text)
        self.hist_idx = len(self.cmd_history)
        self.saved_buf = ''
        if self.memory:
            self.memory.add_command(text)
        if text.startswith('/'):
            self._cmd(text); return
        self.messages.append(('user', text))
        self.chat_scroll = 0  # snap to bottom on new message

        def stream():
            self.ai_stream = True
            self.cur_resp  = ''
            self.glitch_mode = True

            def tok(t):
                self.cur_resp += t
                # Trigger agents based on content
                if len(self.cur_resp) == len(t):  # first token
                    self.swarm.dispatch(text)

            self.brain.think(text, tok)
            full = self.cur_resp
            self.messages.append(('nexus', full))
            if self.voice.enabled:
                self.voice.speak(full[:200])
            self.cur_resp  = ''
            self.ai_stream = False
            self.glitch_mode = False

        threading.Thread(target=stream, daemon=True).start()

    def _cmd(self, cmd):
        parts = cmd.split()
        c = parts[0].lower()

        if c == '/train':
            ds = parts[1] if len(parts)>1 else 'spiral'
            self.neural.stop(); time.sleep(0.2); self.neural.start(ds)
            self.messages.append(('nexus',f'Neural training restarted: {ds}'))

        elif c == '/swarm':
            task = ' '.join(parts[1:]) or 'Analyze current system state and surface insights.'
            self.swarm.broadcast(task)
            self.messages.append(('nexus',f'Broadcast to all 5 agents: "{task[:60]}"'))

        elif c == '/consensus':
            question = ' '.join(parts[1:])
            if not question:
                self.messages.append(('nexus','Usage: /consensus <question> — all 5 agents answer, then synthesize'))
            else:
                self.messages.append(('user', question))
                def run_consensus():
                    self.ai_stream = True
                    self.cur_resp  = ''
                    res = self.swarm.consensus(
                        question,
                        on_token=lambda t: setattr(self, 'cur_resp', self.cur_resp + t),
                        ollama=self.brain.ollama)
                    self.messages.append(('nexus', '[CONSENSUS] ' + res['consensus']))
                    if self.memory:
                        self.memory.add_message('user', question)
                        self.memory.add_message('nexus', res['consensus'][:500])
                    self.cur_resp  = ''
                    self.ai_stream = False
                threading.Thread(target=run_consensus, daemon=True).start()
                self.messages.append(('nexus','5 agents deliberating in parallel...'))

        elif c == '/remember':
            fact = ' '.join(parts[1:])
            if not fact:
                self.messages.append(('nexus','Usage: /remember <fact> — NEXUS keeps this across restarts'))
            elif self.memory:
                self.memory.remember(fact)
                self.messages.append(('nexus',f'Committed to long-term memory: "{fact[:80]}"'))
            else:
                self.messages.append(('nexus','Memory subsystem not available.'))

        elif c == '/recall':
            if not self.memory:
                self.messages.append(('nexus','Memory subsystem not available.'))
            else:
                facts = self.memory.facts()
                st = self.memory.stats()
                if facts:
                    listing = '\n'.join(f'  • {f}' for f in facts[-12:])
                    self.messages.append(('nexus',
                        f'[MEMORY] boot #{st["boots"]} · {st["total_msgs"]} msgs · '
                        f'{st["age_days"]}d old · {st["facts"]} facts\n{listing}'))
                else:
                    self.messages.append(('nexus',
                        f'[MEMORY] boot #{st["boots"]} · {st["total_msgs"]} msgs · '
                        f'{st["age_days"]}d old · no facts yet. Use /remember <fact>'))

        elif c == '/scan':
            threading.Thread(target=self.security._scan_subnet, daemon=True).start()
            self.messages.append(('nexus','Network scan initiated.'))

        elif c == '/search':
            query = ' '.join(parts[1:])
            if not query:
                self.messages.append(('nexus','Usage: /search <query>'))
            else:
                def do_search():
                    from brain.websearch import search, format_for_llm
                    self.ai_stream = True
                    results = search(query)
                    summary = format_for_llm(query, results)
                    self.messages.append(('nexus', summary))
                    self.ai_stream = False
                threading.Thread(target=do_search, daemon=True).start()
                self.messages.append(('nexus', f'Searching: "{query}"...'))

        elif c == '/camera':
            if self.vision.status in ('live',):
                self.vision.stop()
                self.messages.append(('nexus','Camera disabled.'))
            else:
                self.vision.start()
                self.messages.append(('nexus','Camera enabled. Opening /dev/video0...'))

        elif c == '/evolve':
            def do_evolve():
                self.ai_stream = True
                self.cur_resp  = ''
                def tok(t): self.cur_resp += t
                self.self_modify.analyze_self(tok)
                full = self.cur_resp
                self.messages.append(('nexus', f'[SELF-ANALYSIS]\n{full}'))
                self.cur_resp = ''
                self.ai_stream = False
            threading.Thread(target=do_evolve, daemon=True).start()
            self.messages.append(('nexus', 'Analyzing own source code for improvements...'))

        elif c == '/diff':
            diff = self.self_modify.git_diff()
            self.messages.append(('nexus', f'[GIT DIFF]\n{diff}'))

        elif c == '/3d':
            import subprocess
            subprocess.Popen(['xdg-open','http://localhost:8766/brain_3d.html'])
            self.messages.append(('nexus','3D brain visualization opened.'))

        elif c == '/voice':
            self.voice.enabled = not self.voice.enabled
            self.messages.append(('nexus',f'Voice {"ON" if self.voice.enabled else "OFF"}.'))

        elif c == '/agent':
            # Route to a specific agent: /agent CODER write a fibonacci function
            if len(parts) > 2:
                target = parts[1].upper()
                task   = ' '.join(parts[2:])
                self.swarm.dispatch(task, target=target)
                self.messages.append(('nexus', f'Task sent to {target}: {task[:60]}'))
            else:
                agents = ', '.join(self.swarm.agents.keys())
                self.messages.append(('nexus', f'Agents: {agents}\nUsage: /agent <NAME> <task>'))

        elif c == '/clear':
            self.messages.clear()

        elif c in ('/quit','/exit','/q'):
            self._running = False

        elif c == '/help':
            self.messages.append(('nexus',
                'NEXUS COMMANDS\n'
                '──────────────────────────────\n'
                '/swarm [task]         broadcast to all 5 agents\n'
                '/agent NAME task      send to specific agent\n'
                '/train [dataset]      spiral|moons|circles|xor\n'
                '/search <query>       web search via DuckDuckGo\n'
                '/evolve               self-analyze & improve\n'
                '/diff                 show own git changes\n'
                '/camera               toggle camera vision\n'
                '/voice                toggle voice (espeak)\n'
                '/scan                 rescan network\n'
                '/3d                   open 3D brain viz\n'
                '/clear  /quit'
            ))
        else:
            # Smart route to swarm
            self.swarm.dispatch(cmd[1:])
            self.messages.append(('nexus',f'Routed to swarm: {cmd}'))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        import termios, tty
        import traceback

        LOG = open('/tmp/nexus_debug.log', 'w')

        # Use /dev/tty if available (works even when stdin is redirected),
        # otherwise fall back to stdin
        try:
            tty_file = open('/dev/tty', 'r+b', buffering=0)
            tty_fd   = tty_file.fileno()
        except OSError:
            tty_file = None
            tty_fd   = sys.stdin.fileno()

        cols, rows = self._size()
        LOG.write(f'Terminal size: {cols}x{rows}\n'); LOG.flush()
        self.rain  = CodeRain(cols, rows)

        sys.stdout.write(alt()+hide())
        sys.stdout.flush()
        old = termios.tcgetattr(tty_fd)
        self._running = True

        try:
            tty.setraw(tty_fd)

            def render_loop():
                time.sleep(0.3)   # let terminal settle after setraw
                err_count = 0
                while self._running:
                    try:
                        self.render()
                    except Exception as ex:
                        err_count += 1
                        LOG.write(f'Render error #{err_count}: {ex}\n{traceback.format_exc()}\n')
                        LOG.flush()
                        if err_count > 10:
                            self._running = False
                            break
                    time.sleep(1/20)

            threading.Thread(target=render_loop, daemon=True).start()
            LOG.write('Render loop started\n'); LOG.flush()

            while self._running:
                try:
                    # Read up to 16 bytes — captures complete escape sequences in one read
                    raw = os.read(tty_fd, 16)
                    seq = raw.decode('utf-8', errors='ignore')

                    # Handle complete escape sequences directly (no state machine needed)
                    if   seq == '\x1b[5~':            self.chat_scroll += 8; continue
                    elif seq == '\x1b[6~':            self.chat_scroll = max(0, self.chat_scroll - 8); continue
                    elif seq == '\x1b[1~':            self.chat_scroll = 9999; continue  # Home
                    elif seq == '\x1b[4~':            self.chat_scroll = 0; continue     # End
                    elif seq in ('\x1b[A', '\x1bOA'): self._history_prev(); continue
                    elif seq in ('\x1b[B', '\x1bOB'): self._history_next(); continue
                    # Mouse wheel SGR: \x1b[<64;x;yM = up, <65 = down
                    elif '\x1b[<64;' in seq:          self.chat_scroll += 3; continue
                    elif '\x1b[<65;' in seq:          self.chat_scroll = max(0, self.chat_scroll - 3); continue

                    # Process remaining bytes one at a time for normal keys
                    for key in seq:
                        if not self.handle_key(key):
                            self._running = False
                            break
                except KeyboardInterrupt:
                    break
                except Exception as ex:
                    LOG.write(f'Input error: {ex}\n'); LOG.flush()
        finally:
            self._running = False
            termios.tcsetattr(tty_fd, termios.TCSADRAIN, old)
            if tty_file: tty_file.close()
            sys.stdout.write(show()+norm())
            sys.stdout.flush()
            LOG.write('NEXUS exited cleanly\n'); LOG.close()
            print('\nNEXUS DOMINION offline.')

    def update_task(self, idx, pct, done=False):
        if 0<=idx<len(self.tasks):
            self.tasks[idx]['pct']  = pct
            self.tasks[idx]['done'] = done

    def add_message(self, role, text):
        self.messages.append((role, text))
