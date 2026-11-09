#!/usr/bin/env python3
# map_kit.py · 지침 v2.8 — 뼈대 지도(한 장 보드) 빌드 · 내보내기
#   build   뼈대.json → 뼈대 HTML (map_theme.html에 자료를 심는다) + 검사 보고
#   outline 뼈대.json → Obsidian용 들여쓰기 아웃라인 .md ([[개념]] 링크 선택)
#   canvas  뼈대.json → Obsidian Canvas(.canvas) — 보드를 끌어 옮길 수 있는 도화지로
# 사용:
#   python3 kit/map_kit.py build   work/[강의]/뼈대.json -o work/out/[과목]_[강의명]_뼈대.html [--theme kit/map_theme.html]
#   python3 kit/map_kit.py outline work/[강의]/뼈대.json -o work/out/[과목]_[강의명]_뼈대.md [--links]
#   python3 kit/map_kit.py canvas  work/[강의]/뼈대.json -o work/out/[과목]_[강의명]_뼈대.canvas
import argparse, json, os, re, sys, html as htmlmod
from html.parser import HTMLParser

VER = 'map_kit v1.0 · 지침 v2.8'
CLS = {'c-tx', 'c-pt', 'c-tr', 'c-po', 'c-gy', 'c-am', 'c-tl'}

# ───────────────────────── 공통 ─────────────────────────
def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def count(pat, s):
    return len(re.findall(pat, s))

def all_html(d):
    parts = [d.get('one', '')]
    for n in d.get('nodes', []):
        parts += [n.get('name', ''), n.get('why', ''), n.get('why2', ''), n.get('full', '')]
    for b in d.get('branches', []):
        parts += [b.get('title', '')] + list(b.get('keys', [])) + [b.get('full', '')]
    for t in d.get('tables', []):
        parts += [t.get('title', ''), t.get('html', '')]
    return '\n'.join(parts)

# ───────────────────────── 검사 ─────────────────────────
def check(d):
    errs, warns = [], []
    m = d.get('meta', {})
    for k in ('subject', 'lecture', 'prof', 'pages', 'date', 'shape'):
        if not m.get(k):
            errs.append(f'meta.{k} 없음')
    if m.get('shape') and m['shape'] not in ('흐름', '기둥', '방사'):
        errs.append(f"meta.shape 는 흐름 · 기둥 · 방사 중 하나 (지금: {m['shape']})")
    if m.get('shape') and not m.get('shape_reason'):
        warns.append('meta.shape_reason 없음 — 어느 슬라이드가 척추인지 적는다')
    g = d.get('grid') or {}
    cols = g.get('cols') or []
    widths = g.get('widths') or []
    if not cols or len(cols) != len(widths):
        errs.append('grid.cols 와 grid.widths 의 길이가 다르거나 비어 있음')
    ids = {}
    def reg(kind, o):
        i = o.get('id')
        if not i:
            errs.append(f'{kind} 에 id 없음: {str(o)[:60]}')
            return
        if i in ids:
            errs.append(f'id 중복: {i} ({ids[i]} · {kind})')
        ids[i] = kind
    for kind in ('pills', 'nodes', 'branches', 'tables'):
        for o in d.get(kind, []):
            reg(kind, o)
    def pos(kind, o):
        if o.get('col') not in cols:
            errs.append(f"{kind} {o.get('id')}: col {o.get('col')!r} 이 grid.cols 에 없음")
        r = o.get('row')
        if not isinstance(r, int) or r < 1:
            errs.append(f"{kind} {o.get('id')}: row 는 1 이상의 정수 (지금: {r!r})")
        if o.get('cls') and o['cls'] not in CLS:
            errs.append(f"{kind} {o.get('id')}: cls {o['cls']!r} 는 {sorted(CLS)} 중 하나")
    for kind in ('pills', 'nodes', 'branches', 'tables'):
        for o in d.get(kind, []):
            pos(kind, o)
    for dv in d.get('dividers', []):
        if not isinstance(dv.get('row'), int):
            errs.append('dividers 의 row 는 정수')
    node_ids = {n['id'] for n in d.get('nodes', []) if n.get('id')}
    nodes = d.get('nodes', [])
    if not nodes:
        errs.append('nodes 가 비어 있음')
    if len([n for n in nodes if not n.get('thin')]) > 10:
        warns.append(f'1층 마디가 {len(nodes)}개 — 10개를 넘으면 뼈대가 아니라 목차다. 묶을 수 있는지 본다')
    for n in nodes:
        if not n.get('why') and not n.get('thin'):
            warns.append(f"마디 {n['id']}: 「왜」 줄이 없음")
        for fld in ('why', 'why2'):
            t = n.get(fld, '')
            if t and not re.search(r'class="tg (q|s|a|x)"', t):
                warns.append(f"마디 {n['id']}.{fld}: 꼬리표(교수님 · 자료 · 추정 · 제외)가 없음")
    for b in d.get('branches', []):
        if b.get('p') not in node_ids:
            errs.append(f"가지 {b.get('id')}: 부모 p={b.get('p')!r} 가 nodes 에 없음")
        if b.get('p2') and b['p2'] not in node_ids:
            errs.append(f"가지 {b.get('id')}: p2={b['p2']!r} 가 nodes 에 없음")
        ks = b.get('keys', [])
        if len(ks) > 6:
            warns.append(f"가지 {b['id']}: 핵심 줄 {len(ks)}개 — 6개를 넘으면 상자가 길어진다. 서랍(full)으로 내린다")
        for k in ks:
            plain = re.sub(r'<[^>]+>', '', k)
            if len(plain) > 120:
                warns.append(f"가지 {b['id']}: 핵심 줄이 {len(plain)}자 — 「{plain[:30]}…」 (110자 안으로)")
        if not b.get('ref'):
            warns.append(f"가지 {b['id']}: ref(Part · 절 · 쪽) 없음")
    per_node = {}
    for b in d.get('branches', []):
        per_node[b.get('p')] = per_node.get(b.get('p'), 0) + 1
    for nid, c in per_node.items():
        if c > 6:
            warns.append(f'마디 {nid}: 가지 {c}개 — 6개를 넘으면 2층이 아니라 3층을 2층에 올린 것')
    for key in ('flow', 'dash', 'links'):
        for pair in d.get(key, []):
            if not (isinstance(pair, list) and len(pair) == 2):
                errs.append(f'{key}: [from, to] 쌍이어야 함: {pair}')
                continue
            for x in pair:
                if x not in ids:
                    errs.append(f'{key}: {x!r} 가 어느 상자의 id 도 아님')
    # 인용 표시 검사: <q> 안에 「…」 끊김 표시 외의 손질 흔적은 알 수 없으니 개수만 센다
    return errs, warns

def stats(d):
    h = all_html(d)
    nodes = d.get('nodes', [])
    br = d.get('branches', [])
    s = {
        '마디': len(nodes), '얇은 마디': len([n for n in nodes if n.get('thin')]),
        '가지': len(br), '사실 줄': sum(len(b.get('keys', [])) for b in br),
        '가로줄 표': len(d.get('tables', [])),
        '빈칸': count(r'class="k[" ]', h) + count(r"class='k[' ]", h),
        '기출 ID': len(set(re.findall(r'class="ex">([^<]+)<', h))),
        '수업 퀴즈': len(set(re.findall(r'class="qz">([^<]+)<', h))),
        '교수님 인용': count(r'class="tg q"', h), '자료': count(r'class="tg s"', h),
        '추정': count(r'class="tg a"', h), '제외': count(r'class="tg x"', h),
    }
    return s

def report(d, errs, warns, out=None, size=None):
    s = stats(d)
    m = d.get('meta', {})
    print(f"뼈대: 척추 {m.get('shape','?')}({m.get('shape_reason','근거 없음')}) · 마디 {s['마디']}(얇은 {s['얇은 마디']}) · 가지 {s['가지']} · 사실 {s['사실 줄']}줄 · 가로줄 표 {s['가로줄 표']} · 빈칸 {s['빈칸']} · 기출 {s['기출 ID']} · 퀴즈 {s['수업 퀴즈']} · 인용 {s['교수님 인용']} · 자료 {s['자료']} · 추정 {s['추정']} · 제외 {s['제외']}")
    for w in warns:
        print('△', w)
    for e in errs:
        print('✕', e)
    if out and not errs:
        print(f"→ {out}" + (f" ({size/1024:.0f} KB)" if size else ''))

# ───────────────────────── build ─────────────────────────
def build(args):
    d = load(args.json)
    errs, warns = check(d)
    if errs:
        report(d, errs, warns)
        sys.exit(1)
    theme = args.theme or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'map_theme.html')
    with open(theme, encoding='utf-8') as f:
        t = f.read()
    mv = re.search(r'map theme v([\d.]+)', t)
    if not mv:
        print('✕ map_theme.html 머리에 「map theme v…」 가 없다 — 템플릿이 아니다')
        sys.exit(1)
    data = json.dumps(d, ensure_ascii=False).replace('</', '<\\/')
    m = d.get('meta', {})
    title = f"{m.get('lecture','')} — 뼈대 지도"
    out_html = t.replace('{{TITLE}}', htmlmod.escape(title)).replace('{{DATA}}', data)
    out = args.o or re.sub(r'\.json$', '', args.json) + '.html'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(out_html)
    report(d, errs, warns, out, os.path.getsize(out))

# ───────────────────────── HTML → 마크다운 ─────────────────────────
class ToMd(HTMLParser):
    """학습자료 컴포넌트 문법의 HTML 조각을 Obsidian 마크다운으로. links=True 면 .k 를 [[ ]] 로."""
    def __init__(self, links=False):
        super().__init__(convert_charrefs=True)
        self.links = links
        self.out = []
        self.stack = []      # 열린 태그
        self.depth = 0       # ul 깊이
        self.in_tr = False
        self.row = []
        self.cell = None
        self.table = []
        self.k = None
    def _txt(self, s):
        if self.cell is not None:
            self.cell.append(s)
        elif self.k is not None:
            self.k.append(s)
        else:
            self.out.append(s)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class', '')
        self.stack.append(tag)
        if tag in ('b', 'strong'):
            if 'k' in cls.split():
                self.k = []
            else:
                self._txt('**')
        elif tag == 'q':
            self._txt('“')
        elif tag == 'i' and cls.startswith('tg'):
            self._txt('「')
        elif tag == 'span':
            if 'ex' in cls.split():
                self._txt('[기출 ')
            elif 'qz' in cls.split():
                self._txt('[')
            elif 'ref' in cls.split():
                self._txt(' (')
            elif 'h' in cls.split():
                self._txt('**')
        elif tag == 'ul':
            self.depth += 1
        elif tag == 'li':
            self.out.append('\n' + '  ' * (self.depth - 1) + '- ')
        elif tag == 'p':
            self.out.append('\n')
        elif tag == 'br':
            self.out.append('\n')
        elif tag == 'table':
            self.table = []
        elif tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = []
        elif tag == 'sub':
            self._txt('_')
        elif tag == 'sup':
            self._txt('^')
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        if tag in ('b', 'strong'):
            if self.k is not None:
                word = ''.join(self.k).strip()
                self.k = None
                self._txt(f'[[{word}]]' if self.links and linkable(word) else f'**{word}**')
            else:
                self._txt('**')
        elif tag == 'q':
            self._txt('”')
        elif tag == 'i':
            self._txt('」')
        elif tag == 'span':
            # 닫는 span 종류를 모르므로 열 때 넣은 표식으로 판단
            pass
        elif tag == 'ul':
            self.depth -= 1
        elif tag in ('td', 'th'):
            self.row.append(''.join(self.cell).strip().replace('|', '\\|'))
            self.cell = None
        elif tag == 'tr':
            self.table.append(self.row)
        elif tag == 'table':
            if self.table:
                hdr = self.table[0]
                lines = ['| ' + ' | '.join(hdr) + ' |', '|' + '---|' * len(hdr)]
                for r in self.table[1:]:
                    lines.append('| ' + ' | '.join(r) + ' |')
                self.out.append('\n' + '\n'.join(lines) + '\n')
            self.table = []
    def handle_data(self, data):
        self._txt(data)
    def text(self):
        s = ''.join(self.out)
        # span 표식 닫기: '[기출 ID' → '[기출 ID]', '(ref' → '(ref)'
        s = re.sub(r'\[기출 ([^\]\n]+?)(?=\s|$|\)|,|·|\[)', r'[기출 \1]', s)
        s = re.sub(r'\[(Quiz-[^\]\n]+?)(?=\s|$|\)|,|·|\[)', r'[\1]', s)
        s = re.sub(r' \(([^()\n]*?)(?=\n|$)', r' (\1)', s)
        s = re.sub(r'[ \t]+', ' ', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
        return s.strip()

def linkable(w):
    """[[ ]] 로 만들 만한 개념어인가 — 숫자 · 방향 · 짧은 조사 · 나열은 굵게만."""
    if not w or len(w) > 36:
        return False
    if re.search(r'[→↑↓⊣✕○%=,/]|\d{2,}', w):
        return False
    if not re.match(r'^[A-Za-z가-힣]', w):
        return False
    hangul = re.sub(r'[^가-힣]', '', w)
    if hangul and len(w) < 3 and not re.search(r'[A-Za-z]', w):
        return False
    return len(w) >= 2

def md(html, links=False):
    if not html:
        return ''
    p = ToMd(links)
    p.feed(html)
    return p.text()

def plain(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html or '')).strip()

# ───────────────────────── outline ─────────────────────────
def outline(args):
    d = load(args.json)
    m = d.get('meta', {})
    L = args.links
    o = []
    o.append('---')
    o.append(f"subject: {m.get('subject','')}")
    o.append(f"lecture: {m.get('lecture','')}")
    o.append(f"prof: {m.get('prof','')}")
    o.append(f"shape: {m.get('shape','')}")
    o.append(f"date: {m.get('date','')}")
    o.append('tags: [뼈대]')
    o.append('---')
    o.append(f"# {m.get('lecture','')} — 뼈대 (척추: {m.get('shape','')} · {m.get('shape_reason','')})")
    if d.get('one'):
        o.append('')
        o.append('> ' + md(d['one'], L).replace('\n', ' '))
    nodes = d.get('nodes', [])
    br = d.get('branches', [])
    tables = d.get('tables', [])
    for n in nodes:
        o.append('')
        o.append(f"## {n.get('num','')} {plain(n.get('name',''))} — {n.get('cat','')}" + (f" · {n.get('loc')}" if n.get('loc') else ''))
        for fld in ('why', 'why2'):
            if n.get(fld):
                o.append('> ' + md(n[fld], L).replace('\n', ' '))
        for b in [x for x in br if x.get('p') == n['id']]:
            o.append(f"- **{plain(b.get('title',''))}** ({b.get('ref','')})")
            for k in b.get('keys', []):
                o.append('  - ' + md(k, L).replace('\n', ' '))
            if args.full and b.get('full'):
                body = md(b['full'], L)
                for ln in body.split('\n'):
                    if ln.strip():
                        o.append('    ' + ln if ln.startswith('-') else '    - ' + ln)
        extra = [x for x in br if x.get('p2') == n['id']]
        for b in extra:
            o.append(f"- (걸침) **{plain(b.get('title',''))}** → [[{plain(b.get('title','')).split(' — ')[0]}]]" if L else f"- (걸침) **{plain(b.get('title',''))}**")
    if tables:
        o.append('')
        o.append('## 가로줄')
        for t in tables:
            o.append('')
            o.append(f"### {plain(t.get('title',''))}")
            if t.get('ref'):
                o.append(f"_{t['ref']}_")
            o.append(md(t.get('html', ''), L))
    out = args.o or re.sub(r'\.json$', '', args.json) + '.md'
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(o) + '\n')
    links = len(set(re.findall(r'\[\[([^\]]+)\]\]', '\n'.join(o))))
    print(f"아웃라인: 마디 {len(nodes)} · 가지 {len(br)} · 줄 {len(o)} · [[링크]] {links}{' (--links)' if L else ''} → {out}")

# ───────────────────────── canvas ─────────────────────────
CANVAS_COLOR = {'c-tx': '1', 'c-am': '2', 'c-gy': None, 'c-tr': '4', 'c-pt': '5', 'c-tl': '5', 'c-po': '6'}

def est_height(text, width, font=14):
    """텍스트 카드의 대략 높이(px) — 줄 수 × 줄 높이. Obsidian에서 끌어 늘릴 수 있으니 대략이면 된다."""
    cpl = max(12, int(width / (font * 0.95)))   # 한 줄 글자 수(한글 기준)
    lines = 0
    for ln in text.split('\n'):
        lines += max(1, -(-len(ln) // cpl))
    return int(lines * font * 1.5 + 28)

def canvas(args):
    d = load(args.json)
    m = d.get('meta', {})
    G = d.get('grid') or {}
    cols, widths = G['cols'], G['widths']
    GAP, RGAP, SCALE = 40, 60, 1.25     # Obsidian 카드가 더 크게 읽히도록 폭을 키운다
    R0 = 1 if d.get('one') else 0
    x0 = {}
    x = 0
    for c, w in zip(cols, widths):
        x0[c] = x
        x += int(w * SCALE) + GAP
    W = lambda c, span=1: sum(int(widths[cols.index(c) + i] * SCALE) for i in range(span)) + GAP * (span - 1)
    items = []  # (id, col, row, span, rowspan, text, color, kind)
    if d.get('one'):
        items.append(('one', cols[0], 1, len(cols), 1, md(d['one']), None, 'one'))
    for p in d.get('pills', []):
        items.append((p['id'], p['col'], p['row'] + R0, p.get('span', 1), 1, '**' + md(p['html']).replace('\n', ' · ') + '**', None, 'pill'))
    for n in d.get('nodes', []):
        t = f"# {n.get('num','')} {plain(n.get('name',''))}\n_{n.get('cat','')}" + (f" · {n.get('loc')}" if n.get('loc') else '') + '_'
        for fld in ('why', 'why2'):
            if n.get(fld):
                t += '\n\n' + md(n[fld])
        items.append((n['id'], n['col'], n['row'] + R0, n.get('span', 1), n.get('rowspan', 2 if n.get('two') else 1), t, CANVAS_COLOR.get(n.get('cls')), 'node'))
    for b in d.get('branches', []):
        t = f"### {plain(b.get('title',''))}\n_{b.get('ref','')}_\n" + '\n'.join('- ' + md(k).replace('\n', ' ') for k in b.get('keys', []))
        items.append((b['id'], b['col'], b['row'] + R0, b.get('span', 1), b.get('rowspan', 1), t, CANVAS_COLOR.get(b.get('cls')), 'br'))
    for tb in d.get('tables', []):
        t = f"### {plain(tb.get('title',''))}\n_{tb.get('ref','')}_\n\n" + md(tb.get('html', ''))
        items.append((tb['id'], tb['col'], tb['row'] + R0, tb.get('span', 1), tb.get('rowspan', 1), t, None, 'xt'))
    # 행 높이: 그 행에서 시작하는 카드 중 가장 높은 것(여러 행에 걸친 카드는 나눠서)
    rowh = {}
    sized = []
    for (i, c, r, sp, rs, text, color, kind) in items:
        w = W(c, sp)
        h = est_height(text, w) if kind != 'pill' else 70
        sized.append((i, c, r, sp, rs, text, color, kind, w, h))
        per = h / rs
        for k in range(rs):
            rowh[r + k] = max(rowh.get(r + k, 60), per)
    y0, y = {}, 0
    for r in range(1, max(rowh) + 2):
        y0[r] = y
        y += rowh.get(r, 60) + RGAP
    nodes_out, edges_out = [], []
    for (i, c, r, sp, rs, text, color, kind, w, h) in sized:
        tot = sum(rowh.get(r + k, 60) for k in range(rs)) + RGAP * (rs - 1)
        node = {'id': i, 'type': 'text', 'text': text, 'x': x0[c], 'y': int(y0[r]), 'width': w, 'height': int(max(h, tot if kind != 'pill' else h))}
        if color:
            node['color'] = color
        nodes_out.append(node)
    k = 0
    for a, b in d.get('flow', []):
        k += 1
        edges_out.append({'id': f'e{k}', 'fromNode': a, 'fromSide': 'bottom', 'toNode': b, 'toSide': 'top', 'toEnd': 'arrow'})
    for a, b in d.get('dash', []):
        k += 1
        edges_out.append({'id': f'e{k}', 'fromNode': a, 'fromSide': 'right', 'toNode': b, 'toSide': 'left', 'toEnd': 'none', 'color': '0'})
    for b in d.get('branches', []):
        for pid in (b.get('p'), b.get('p2')):
            if not pid:
                continue
            k += 1
            pc, bc = cols.index(next(n['col'] for n in d['nodes'] if n['id'] == pid)), cols.index(b['col'])
            side = ('left', 'right') if bc < pc else ('right', 'left') if bc > pc else ('bottom', 'top')
            edges_out.append({'id': f'e{k}', 'fromNode': pid, 'fromSide': side[0], 'toNode': b['id'], 'toSide': side[1], 'toEnd': 'none'})
    for a, b in d.get('links', []):
        k += 1
        edges_out.append({'id': f'e{k}', 'fromNode': a, 'fromSide': 'right', 'toNode': b, 'toSide': 'left', 'toEnd': 'none'})
    out = args.o or re.sub(r'\.json$', '', args.json) + '.canvas'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'nodes': nodes_out, 'edges': edges_out}, f, ensure_ascii=False, indent=1)
    print(f"캔버스: 카드 {len(nodes_out)} · 선 {len(edges_out)} · 크기 {x}×{int(y)} → {out}")

# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description=VER)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build'); b.add_argument('json'); b.add_argument('-o'); b.add_argument('--theme'); b.set_defaults(fn=build)
    o = sub.add_parser('outline'); o.add_argument('json'); o.add_argument('-o'); o.add_argument('--links', action='store_true', help='.k 핵심어를 [[ ]] 로'); o.add_argument('--full', action='store_true', help='가지의 전문(full)까지'); o.set_defaults(fn=outline)
    c = sub.add_parser('canvas'); c.add_argument('json'); c.add_argument('-o'); c.set_defaults(fn=canvas)
    k = sub.add_parser('check'); k.add_argument('json'); k.set_defaults(fn=lambda a: (lambda d: report(d, *check(d)))(load(a.json)))
    a = ap.parse_args()
    a.fn(a)

if __name__ == '__main__':
    main()
