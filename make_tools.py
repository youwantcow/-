#!/usr/bin/env python3
"""make_tools.py — 학습자료 자동 제작(제작 시작 → 마지막 Part → 병합)을 위한 보조 도구 (운영지침 v2.0)

  pages     강의자료.pdf --out pages/ [--first 1] [--width 1600]
            쪽마다 pages/p<원본쪽번호>.jpg 를 만든다(서브에이전트가 Read 로 보는 용도. 삽입용 이미지는 build_part.py 가 따로 만든다).
  pagestats 강의록.md [--out stats.tsv]
            【p.N】 마커 기준으로 쪽마다 교수님 발화 글자 수(공백 제외)를 센다 → 인벤토리의 「강의록 언급」 판단 근거.
  slice     강의록.md --pages 12-27 --out slice.md [--margin 2]
            해당 쪽 범위(±margin)의 마커 블록만 뽑는다. 【p.–】(슬라이드 무관) 블록은 앞뒤 블록이 범위에 들면 함께 넣는다.
  fill      템플릿.md --set KEY=VALUE ... [--set-file KEY=파일] --out 채운프롬프트.md
            {{KEY}} 자리표시자를 채운다. 값이 파일 경로면 절대 경로로 바꾼다. --set-file 은 파일 내용을 통째로 넣는다(서브에이전트의 Read 호출을 줄인다).
            남은 자리표시자가 있으면 멈춘다.
  plan      --total-pages N --inventory inv.md [--target 12] [--max 15]
            인벤토리(쪽 | 주제 | … | 밀도)로 Part 분할안 초안을 낸다: 밀도 상=0.6쪽 가중, 하=1.6쪽 가중으로 target 안에서 자르되 주제 경계를 우선한다.
            결과는 초안일 뿐이고 최종 분할은 Claude가 정한다(한 대사 경로·표 묶음을 쪼개지 않는다).
"""
import argparse, os, re, subprocess, sys


def read(p): return open(p, encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)


def cmd_pages(a):
    os.makedirs(a.out, exist_ok=True)
    out = subprocess.run(['pdfinfo', a.pdf], capture_output=True, text=True).stdout
    m = re.search(r'Pages:\s+(\d+)', out); n = int(m.group(1)) if m else 0
    if not n: sys.exit('pdfinfo 로 쪽수를 읽지 못했다')
    subprocess.run(['pdftoppm', '-jpeg', '-jpegopt', 'quality=85', '-scale-to-x', str(a.width), '-scale-to-y', '-1', a.pdf, os.path.join(a.out, 'tmp')], check=True)
    made = []
    for f in sorted(os.listdir(a.out)):
        m = re.match(r'tmp-(\d+)\.jpg$', f)
        if m:
            orig = int(m.group(1)) + a.first - 1
            os.replace(os.path.join(a.out, f), os.path.join(a.out, f'p{orig}.jpg')); made.append(orig)
    print(f'쪽 이미지 {len(made)}장: p{min(made)}~p{max(made)} → {a.out}/pN.jpg (파일 1쪽 = 원본 p.{a.first})')


MARK = re.compile(r'【p\.(\d+|–|-)\??】')


def blocks(text):
    """[(쪽 or None, 본문)] — 마커 단위. 마커 앞 머리말은 쪽 None"""
    i = text.find('\n---\n'); body = text[i + 5:] if i >= 0 else text
    out, last, page = [], 0, None
    for m in MARK.finditer(body):
        out.append((page, body[last:m.start()])); page = m.group(1); last = m.start()
    out.append((page, body[last:]))
    return out


def cmd_pagestats(a):
    st = {}
    for pg, b in blocks(read(a.lecture)):
        if pg is None: continue
        key = '–' if pg in ('–', '-') else int(pg)
        st[key] = st.get(key, 0) + len(re.sub(r'\s|【[^】]*】', '', b))
    rows = sorted(((k, v) for k, v in st.items() if k != '–'), key=lambda x: x[0])
    tot = sum(v for _, v in rows) or 1; avg = tot / max(1, len(rows))
    L = ['쪽\t글자수\t평균 대비\t언급']
    for k, v in rows:
        r = v / avg; lab = '길게' if r >= 1.8 else '보통' if r >= 0.6 else '짧게' if v > 0 else '없음'
        L.append(f'{k}\t{v}\t{r:.1f}\t{lab}')
    if '–' in st: L.append(f'–\t{st["–"]}\t\t슬라이드 무관')
    s = '\n'.join(L) + '\n'
    if a.out: write(a.out, s); print(f'쪽 {len(rows)}개 · 평균 {avg:.0f}자 → {a.out}')
    else: print(s)


def cmd_slice(a):
    lo, hi = [int(x) for x in a.pages.split('-')]
    lo, hi = lo - a.margin, hi + a.margin
    bl = blocks(read(a.lecture)); keep = []
    for i, (pg, b) in enumerate(bl):
        if pg is None: continue
        if pg in ('–', '-'):
            near = [bl[j][0] for j in (i - 1, i + 1) if 0 <= j < len(bl) and bl[j][0] not in (None, '–', '-')]
            if any(lo <= int(p) <= hi for p in near): keep.append(b)
        elif lo <= int(pg) <= hi: keep.append(b)
    s = ''.join(keep)
    write(a.out, f'(강의록 발췌 — 원본 쪽 {a.pages} ±{a.margin} 범위의 【p.N】 블록만. 전체는 원본 강의록 참조)\n\n' + s)
    print(f'발췌 {len(keep)}블록 · {len(re.sub(r"\\s", "", s)):,}자 → {a.out}')


def cmd_fill(a):
    t = read(a.template)
    for kv in a.set_file or []:  # {{KEY}} 자리에 파일 내용을 통째로 넣는다(서브에이전트가 Read 하지 않게)
        k, v = kv.split('=', 1); t = t.replace('{{' + k + '}}', read(v).rstrip('\n'))
    for kv in a.set or []:
        if '=' not in kv: sys.exit(f'--set 은 KEY=VALUE 꼴: {kv}')
        k, v = kv.split('=', 1)
        if a.set_abs and os.path.exists(v): v = os.path.abspath(v)
        t = t.replace('{{' + k + '}}', v)
    left = sorted(set(re.findall(r'{{[A-Z_0-9]+}}', t)))
    if left: sys.exit(f'채우지 못한 자리표시자: {left}')
    write(a.out, t); print(f'→ {a.out} ({len(t):,}자)')


def cmd_plan(a):
    rows = []
    for l in read(a.inventory).splitlines():
        if not l.strip().startswith('|'): continue
        cs = [c.strip() for c in l.strip().strip('|').split('|')]
        m = re.match(r'(\d+)', cs[0]) if cs else None
        if not m or all(re.fullmatch(r':?-+:?', c) for c in cs if c): continue
        dens = next((c for c in cs if c in ('상', '중', '하')), '중')
        rows.append((int(m.group(1)), cs[1] if len(cs) > 1 else '', dens))
    if not rows: sys.exit('인벤토리에서 쪽 행을 읽지 못했다 (첫 열이 쪽번호인 표여야 한다)')
    w = {'상': 1 / 0.6, '중': 1.0, '하': 1 / 1.6}
    parts, cur, load = [], [], 0.0
    for i, (pg, topic, d) in enumerate(rows):
        cur.append(pg); load += w[d]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        boundary = nxt is None or (nxt[1] and nxt[1] != topic)
        if nxt is None or (load >= a.target and boundary) or load >= a.max:
            parts.append((cur[0], cur[-1], round(load, 1))); cur, load = [], 0.0
    print('| Part | 쪽 범위 | 가중 쪽수 |'); print('|---|---|---|')
    for i, (s, e, l) in enumerate(parts, 1): print(f'| {i} | p.{s}–{e} | {l} |')
    print(f'(초안 — 밀도 가중. 주제 경계·대사 경로·표 묶음을 보고 Claude가 최종 조정)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('pages'); p.add_argument('pdf'); p.add_argument('--out', default='pages'); p.add_argument('--first', type=int, default=1); p.add_argument('--width', type=int, default=1600)
    p = sp.add_parser('pagestats'); p.add_argument('lecture'); p.add_argument('--out')
    p = sp.add_parser('slice'); p.add_argument('lecture'); p.add_argument('--pages', required=True); p.add_argument('--out', required=True); p.add_argument('--margin', type=int, default=2)
    p = sp.add_parser('fill'); p.add_argument('template'); p.add_argument('--set', action='append'); p.add_argument('--set-file', action='append'); p.add_argument('--out', required=True); p.add_argument('--set-abs', action='store_true', default=True)
    p = sp.add_parser('plan'); p.add_argument('--total-pages', type=int); p.add_argument('--inventory', required=True); p.add_argument('--target', type=float, default=12); p.add_argument('--max', type=float, default=15)
    a = ap.parse_args()
    {'pages': cmd_pages, 'pagestats': cmd_pagestats, 'slice': cmd_slice, 'fill': cmd_fill, 'plan': cmd_plan}[a.cmd](a)


if __name__ == '__main__':
    main()
