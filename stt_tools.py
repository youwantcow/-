#!/usr/bin/env python3
"""stt_tools.py — STT 보정을 사람이 「계속」을 치지 않고 자동으로 돌리기 위한 도구 (운영지침 v2.0)

  split  원문.txt --out chunks/ [--size 3500] [--min 2000]
         원문을 타임스탬프(없으면 문단·문장) 경계에서 약 size자씩 잘라 chunks/01.txt … 로 둔다.
         구간마다 앞 구간의 끝 300자를 chunks/01.prev.txt 로 함께 둔다(문맥 참고용 — 보정 대상 아님).
         chunks/manifest.tsv 와 표를 출력한다.
  join   --header 머리말.md --out 강의록.md chunks/ parts/
         parts/01.md … (각 구간의 보정본)을 순서대로 이어 강의록을 만든다. 머리말 뒤에 '---' 줄을 넣는다(review_kit 규약).
         구간 끝의 〈입력 약 N자 → 출력 약 M자〉 줄은 본문에서 빼고 검사표에만 쓴다.
         검사: 구간별 입력·출력 글자 수(마커·〔〕 병기 제외)와 비율, 앞뒤 경계 일치. 비율이 0.75~1.25 밖이면 종료 코드 1(그 구간을 다시 보정할 것).
  logs   --name 강의명 --out 보정로그.md parts/ [--lecture 강의록.md] [--print-21]
         parts/01.log.md … (구간별 로그)를 02 프롬프트의 1~4절 구조로 합친다. 같은 수정은 횟수를 합치고 용어집 후보는 중복을 뺀다.
         --lecture 를 주면 2-1 표의 각 행에 review_kit 의 ID(R001…)를 병기한다(같은 폴더의 review_kit.py 사용).
         --print-21 은 채팅에 붙일 2-1 표만 출력한다.
  gloss  보정로그.md --out pairs.tsv
         보정로그의 「3. 용어집 추가 후보」 표를 ctx_edit.py glossary-bulk 용 TSV로 뽑는다.
  slides 강의자료.pdf --out slides.txt [--first 1]
         pdftotext 로 쪽마다 `=== p.N ===` 표시를 붙인 텍스트를 만든다(--first: 파일 1쪽의 원본 쪽번호).
  prompt --template prompts/stt_chunk.md --n 1 --total 3 --rules 02.md --slides slides.txt --chunks chunks --parts parts
         --info "과목: … · 강의명: … · 담당 교수: …" [--glossary gloss.md] --out prompts/01.md
         서브에이전트에게 줄 구간 프롬프트를 채워 만든다. 규칙(02의 절대 원칙~슬라이드 마커)·슬라이드 텍스트·용어집·앞 구간·원문을
         프롬프트 안에 통째로 넣으므로 서브에이전트는 Read 없이 Write 두 번으로 끝난다(토큰 절약).

구간 로그 파일 형식(서브에이전트가 지킨다 — kit/prompts/stt_chunk.md):
  ## 1. 수정 로그 / ## 2. 불확실 목록 (### 2-1. 녹음으로 먼저 다시 들을 곳 · ### 2-2. 전체) /
  ## 3. 용어집 추가 후보 / ## 4. 시험 관련 발언 색인   — 각 절은 표 하나. 분량(0절)은 join 이 센다.
"""
import argparse, difflib, glob, os, re, sys

TS_LINE = re.compile(r'^\s*\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*$')          # 줄 전체가 타임스탬프
TS_LEAD = re.compile(r'^\s*\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?[\s\-–:]+(?=\S)')  # 줄 머리의 타임스탬프
MARK = re.compile(r'【[^】]*】|〔[^〕]*〕|\[불명확\]')
SENT_END = re.compile(r'(?<=[.?!。])\s+|(?<=[다요죠네까]\.)\s+')
SUMMARY = re.compile(r'^\s*〈\s*입력\s*약?\s*([\d,]+)\s*자\s*→\s*출력\s*약?\s*([\d,]+)\s*자\s*〉\s*$')


def read(p): return open(p, encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)
def nchars(s): return len(re.sub(r'\s+', '', s))
def eff(s): return nchars(MARK.sub('', s))   # 마커·병기를 뺀 글자 수


# ---------- split ----------
def blocks_of(text):
    """[(시각 or None, 본문)] — 타임스탬프 단위, 없으면 빈 줄 단위 문단"""
    lines = text.splitlines()
    has_ts = any(TS_LINE.match(l) or TS_LEAD.match(l) for l in lines)
    out, cur, ts = [], [], None
    if has_ts:
        for l in lines:
            m = TS_LINE.match(l)
            if m:
                if cur: out.append((ts, '\n'.join(cur)))
                cur, ts = [l], m.group(1)
                continue
            m = TS_LEAD.match(l)
            if m:
                if cur: out.append((ts, '\n'.join(cur)))
                cur, ts = [l], m.group(1)
                continue
            cur.append(l)
        if cur: out.append((ts, '\n'.join(cur)))
    else:
        for para in re.split(r'\n\s*\n', text):
            if para.strip(): out.append((None, para))
    return out


def split_long(block, size):
    """한 블록이 너무 길면 문장 끝에서 나눈다"""
    ts, body = block
    if nchars(body) <= size * 1.3: return [block]
    pieces, cur = [], ''
    for s in SENT_END.split(body):
        if cur and nchars(cur) + nchars(s) > size:
            pieces.append(cur); cur = s
        else:
            cur = (cur + ' ' + s) if cur else s
    if cur: pieces.append(cur)
    return [(ts if i == 0 else None, p) for i, p in enumerate(pieces)]


def cmd_split(a):
    text = read(a.src)
    if text.startswith('﻿'): text = text[1:]
    bl = []
    for b in blocks_of(text): bl += split_long(b, a.size)
    chunks, cur, n = [], [], 0
    for b in bl:
        if cur and n + nchars(b[1]) > a.size and n >= a.min:
            chunks.append(cur); cur, n = [], 0
        cur.append(b); n += nchars(b[1])
    if cur: chunks.append(cur)
    if len(chunks) > 1 and sum(nchars(b[1]) for b in chunks[-1]) < a.size // 4:
        last = chunks.pop(); chunks[-1] += last   # 꼬리가 너무 짧으면 앞 구간에 붙인다
    os.makedirs(a.out, exist_ok=True)
    for f in glob.glob(os.path.join(a.out, '*.txt')) + glob.glob(os.path.join(a.out, 'manifest.tsv')): os.remove(f)
    rows, prev = [], ''
    for i, ch in enumerate(chunks, 1):
        body = '\n'.join(b[1] for b in ch).strip('\n') + '\n'
        write(os.path.join(a.out, f'{i:02d}.txt'), body)
        write(os.path.join(a.out, f'{i:02d}.prev.txt'), prev[-300:])
        tss = [b[0] for b in ch if b[0]]
        rows.append((f'{i:02d}', nchars(body), tss[0] if tss else '—', tss[-1] if tss else '—', len(ch)))
        prev = body
    write(os.path.join(a.out, 'manifest.tsv'), '구간\t글자수\t첫시각\t끝시각\t블록수\n' + '\n'.join('\t'.join(map(str, r)) for r in rows) + '\n')
    total = nchars(text)
    print(f'원문 {total:,}자(공백 제외) → 구간 {len(chunks)}개 (목표 {a.size}자) · 타임스탬프 {"있음" if any(r[2] != "—" for r in rows) else "없음"}')
    print('| 구간 | 글자 수 | 시각 범위 | 블록 |'); print('|---|---|---|---|')
    for r in rows: print(f'| {r[0]} | {r[1]:,} | {r[2]} ~ {r[3]} | {r[4]} |')
    print(f'→ {a.out}/01.txt … {len(chunks):02d}.txt (+ .prev.txt, manifest.tsv)')


# ---------- join ----------
def part_files(d, suffix):
    fs = sorted(glob.glob(os.path.join(d, f'[0-9][0-9]{suffix}')))
    if not fs: sys.exit(f'{d} 에 {suffix} 파일이 없다')
    return fs


def strip_summary(s):
    """끝의 〈입력 약 N자 → 출력 약 M자〉 줄을 떼어 (본문, (N, M) or None)"""
    lines = s.rstrip('\n').split('\n'); summ = None
    while lines and (not lines[-1].strip() or SUMMARY.match(lines[-1])):
        m = SUMMARY.match(lines[-1])
        if m: summ = (int(m.group(1).replace(',', '')), int(m.group(2).replace(',', '')))
        lines.pop()
    return '\n'.join(lines).strip('\n') + '\n', summ


def tail_sim(a, b, n=80):
    a, b = re.sub(r'\s+', '', MARK.sub('', a))[-n:], re.sub(r'\s+', '', MARK.sub('', b))[-n:]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0


def head_sim(a, b, n=80):
    a, b = re.sub(r'\s+', '', MARK.sub('', a))[:n], re.sub(r'\s+', '', MARK.sub('', b))[:n]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0


def cmd_join(a):
    srcs = part_files(a.chunks, '.txt'); outs = part_files(a.parts, '.md')
    if len(srcs) != len(outs):
        sys.exit(f'구간 수가 다르다: 원문 {len(srcs)} vs 보정본 {len(outs)} — 빠진 구간: '
                 + ', '.join(sorted({os.path.basename(s)[:2] for s in srcs} - {os.path.basename(o)[:2] for o in outs})))
    header = read(a.header).rstrip('\n') + '\n'
    bodies, rows, bad = [], [], 0
    for s, o in zip(srcs, outs):
        src = read(s); body, summ = strip_summary(read(o))
        ei, eo = eff(src), eff(body); ratio = eo / ei if ei else 0
        ts, hs = tail_sim(src, body), head_sim(src, body)
        flag = ''
        if ratio < 0.75 or ratio > 1.25: flag = '✗ 분량 이상(누락·요약 의심) → 다시 보정'; bad += 1
        elif ratio < 0.88 or ratio > 1.12: flag = '⚠ 분량 차이 큼 — 경계 확인'
        if ts < 0.45: flag += ' ✗ 끝부분 불일치'; bad += 1
        if hs < 0.45: flag += ' ✗ 첫부분 불일치'; bad += 1
        marks = len(MARK.findall(body)); pages = len(re.findall(r'【p\.[^】]*】', body))
        rows.append((os.path.basename(o)[:2], ei, eo, ratio, pages, marks - pages, flag))
        bodies.append(body)
    write(a.out, header + '\n---\n\n' + '\n\n'.join(b.rstrip('\n') for b in bodies) + '\n')
    write(os.path.join(a.parts, '_stats.tsv'), '구간\t입력\t출력\t비율\t【p】\t〔〕\t검사\n' + '\n'.join(f'{r[0]}\t{r[1]}\t{r[2]}\t{r[3]:.2f}\t{r[4]}\t{r[5]}\t{r[6]}' for r in rows) + '\n')
    print(f'강의록 결합: 구간 {len(outs)}개 → {a.out} ({os.path.getsize(a.out)/1e3:.0f} KB)')
    print('| 구간 | 입력 | 출력 | 비율 | 【p】 | 〔〕 | 검사 |'); print('|---|---|---|---|---|---|---|')
    for r in rows: print(f'| {r[0]} | {r[1]:,} | {r[2]:,} | {r[3]:.2f} | {r[4]} | {r[5]} | {r[6]} |')
    tin, tout = sum(r[1] for r in rows), sum(r[2] for r in rows)
    print(f'합계: 입력 {tin:,} → 출력 {tout:,} (비율 {tout/tin if tin else 0:.2f}) · 【p】 {sum(r[4] for r in rows)} · 보정 표시 {sum(r[5] for r in rows)}'
          + (f' · ✗ {bad}건 — 해당 구간을 다시 보정한 뒤 join 재실행' if bad else ' · 검사 통과'))
    sys.exit(1 if bad else 0)


# ---------- logs ----------
def sections(md):
    """'## n.' / '### n-m.' 제목 → 그 아래 본문. 키: '0','1','2-1','2-2','3','4'"""
    out, key = {}, None
    for l in md.splitlines():
        m = re.match(r'^#{2,3}\s*(\d(?:-\d)?)\.', l)
        if m: key = m.group(1); out[key] = []; continue
        if key: out[key].append(l)
    return {k: '\n'.join(v) for k, v in out.items()}


def table_rows(md):
    """마크다운 표 → (머리, [행])"""
    hdr, rows = None, []
    for l in md.splitlines():
        s = l.strip()
        if not s.startswith('|'):
            continue
        cs = [c.strip() for c in s.strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cs if c): continue
        if hdr is None: hdr = cs; continue
        if all(not c or c in ('없음', '-', '—') for c in cs): continue
        rows.append(cs + [''] * (len(hdr) - len(cs)))
    return hdr, rows


def render(hdr, rows):
    if not hdr: return '(없음)\n'
    L = ['| ' + ' | '.join(hdr) + ' |', '|' + '---|' * len(hdr)]
    L += ['| ' + ' | '.join(c.replace('|', '／') for c in r[:len(hdr)]) + ' |' for r in rows] if rows else ['| ' + ' | '.join(['없음'] + [''] * (len(hdr) - 1)) + ' |']
    return '\n'.join(L) + '\n'


def cmd_logs(a):
    fs = part_files(a.parts, '.log.md')
    agg = {k: (None, []) for k in ('1', '2-1', '2-2', '3', '4')}
    stats = {}
    sp_ = os.path.join(a.parts, '_stats.tsv')
    if os.path.exists(sp_):
        for l in read(sp_).splitlines()[1:]:
            c = l.split('\t'); stats[c[0]] = c
    summ = []
    for f in fs:
        n = os.path.basename(f)[:2]; sec = sections(read(f))
        st = stats.get(n)
        summ.append((n, st[1], st[2], st[3], st[4], st[5], st[6]) if st else (n, '?', '?', '?', '?', '?', 'join 미실행'))
        for k in agg:
            hdr, rows = table_rows(sec.get(k, ''))
            if hdr and agg[k][0] is None: agg[k] = (hdr, agg[k][1])
            for r in rows: agg[k][1].append([n] + r)
    # 1절: 같은 수정은 횟수를 합친다 (첫 열 '원문 → 수정' 기준)
    h1, r1 = agg['1']
    if h1:
        ci = next((i for i, h in enumerate(h1) if '횟수' in h), None)
        merged, order = {}, []
        for r in r1:
            key = r[1]
            if key not in merged: merged[key] = list(r); order.append(key)
            elif ci is not None:
                try: merged[key][ci + 1] = str(int(re.sub(r'\D', '', merged[key][ci + 1]) or 1) + int(re.sub(r'\D', '', r[ci + 1]) or 1))
                except ValueError: pass
                merged[key][0] = merged[key][0] + ',' + r[0]
        r1 = [merged[k] for k in order]
    # 3절: 용어집 후보 중복 제거
    h3, r3 = agg['3']
    seen, u3 = set(), []
    for r in r3:
        k = re.sub(r'\s+', '', r[1]).lower()
        if k and k not in seen: seen.add(k); u3.append(r)
    name = a.name
    # 2-1: ID 병기
    h21, r21 = agg['2-1']
    if a.lecture and h21:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            import review_kit
            rows, _ = review_kit.extract(read(a.lecture))
            ti = next((i for i, h in enumerate(h21) if '시각' in h), None)
            mi = next((i for i, h in enumerate(h21) if '표시' in h), None)
            for r in r21:
                hit = []
                if ti is not None:
                    q = r[ti + 1].strip()
                    same = [x for x in rows if x['ts'] != '—' and review_kit.norm_ts(x['ts']) == review_kit.norm_ts(q)] if re.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?', q) else []
                    if mi is not None and r[mi + 1].strip():
                        key = re.sub(r'\s+', '', r[mi + 1])
                        narrow = [x for x in same if re.sub(r'\s+', '', x['mark']) in key or key in re.sub(r'\s+', '', x['mark'])]
                        same = narrow or same
                    hit = [x['id'] for x in same]
                r.append(', '.join(hit) if hit else '(ID 없음 — 시각·표시 확인)')
            h21 = h21 + ['ID']
        except Exception as ex:
            print(f'⚠ ID 병기 실패: {ex}')
    L = [f'# 보정로그 — {name}', '', f'구간 {len(fs)}개를 자동 병합한 로그(stt_tools.py logs). 각 표의 첫 열은 구간 번호.', '',
         '## 0. 구간별 분량 (stt_tools join 검사)', '', '| 구간 | 입력(자) | 출력(자) | 비율 | 【p】 | 〔〕 | 검사 |', '|---|---|---|---|---|---|---|']
    L += [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |' for r in summ]
    L += ['', '## 1. 수정 로그', '', render(['구간'] + (h1 or ['원문 → 수정', '횟수', '근거']), r1),
          '## 2. 불확실 목록', '', '### 2-1. 녹음으로 먼저 다시 들을 곳', '',
          render(['구간'] + (h21 or ['시각', '표시', '앞뒤 문맥', '왜 먼저']), r21),
          '### 2-2. 전체', '', render(['구간'] + (agg['2-2'][0] or ['시각', '표시', '앞뒤 문맥']), agg['2-2'][1]),
          '## 3. 용어집 추가 후보', '', render(['구간'] + (h3 or ['STT 표기', '올바른 표기']), u3),
          '## 4. 시험 관련 발언 색인', '', render(['구간'] + (agg['4'][0] or ['【p.N】', '시각', '첫 어절', '종류']), agg['4'][1])]
    write(a.out, '\n'.join(L))
    counts = {'수정 로그': len(r1), '녹음으로 먼저 다시 들을 곳': len(r21), '불확실 전체': len(agg['2-2'][1]), '용어집 후보': len(u3), '시험 발언 색인': len(agg['4'][1])}
    print(f'→ {a.out} · ' + ' · '.join(f'{k} {v}' for k, v in counts.items()))
    if a.print_21:
        print(); print(render(['구간'] + (h21 or []), r21))


def cmd_gloss(a):
    sec = sections(read(a.log)); hdr, rows = table_rows(sec.get('3', ''))
    if not hdr: sys.exit('3절(용어집 추가 후보) 표가 없다')
    si = next((i for i, h in enumerate(hdr) if 'STT' in h), 1 if hdr[0] == '구간' else 0)
    ri = next((i for i, h in enumerate(hdr) if '올바른' in h), si + 1)
    pairs = [(r[si], r[ri]) for r in rows if r[si] and r[ri]]
    write(a.out, 'STT표기\t올바른표기\n' + '\n'.join(f'{s}\t{r}' for s, r in pairs) + '\n')
    print(f'용어집 후보 {len(pairs)}쌍 → {a.out}')


def cmd_slides(a):
    import subprocess
    r = subprocess.run(['pdftotext', '-layout', a.pdf, '-'], capture_output=True, text=True)
    if r.returncode != 0: sys.exit('pdftotext 실패: ' + r.stderr[:300])
    pages = r.stdout.split('\f')
    while pages and not pages[-1].strip(): pages.pop()
    out = []
    for i, pg in enumerate(pages):
        body = re.sub(r'[ \t]+\n', '\n', pg).strip('\n')
        out.append(f'=== p.{i + a.first} ===\n' + (body if body.strip() else '(글자 없음 — 그림·사진 쪽)') + '\n')
    write(a.out, '\n'.join(out))
    print(f'슬라이드 텍스트: {len(pages)}쪽 (p.{a.first}~p.{a.first + len(pages) - 1}) → {a.out} ({os.path.getsize(a.out)/1e3:.0f} KB)')


def rules_excerpt(path):
    """02 프롬프트에서 구간 보정에 필요한 절만(절대 원칙 ~ 슬라이드 마커). 「분량 처리」부터는 뺀다"""
    t = read(path)
    i = t.find('## 절대 원칙'); j = t.find('## 분량 처리')
    return t[i:j].strip() if i >= 0 and j > i else t.strip()


def cmd_prompt(a):
    """입력(규칙·슬라이드·용어집·앞 구간·원문)을 프롬프트 안에 통째로 넣는다 → 서브에이전트가 Read 를 하지 않는다"""
    t = read(a.template); n = f'{a.n:02d}'
    ab = os.path.abspath
    g = read(a.glossary).strip() if a.glossary and os.path.exists(a.glossary) else '(없음)'
    prev_p = os.path.join(a.chunks, n + '.prev.txt')
    prev = read(prev_p).strip() if os.path.exists(prev_p) else ''
    rep = {'{{N}}': str(a.n), '{{TOTAL}}': str(a.total), '{{RULES}}': rules_excerpt(a.rules), '{{SLIDES}}': read(a.slides).strip(),
           '{{PREV}}': prev or '(없음 — 첫 구간)', '{{CHUNK}}': read(os.path.join(a.chunks, n + '.txt')).rstrip('\n'),
           '{{OUT}}': ab(os.path.join(a.parts, n + '.md')), '{{LOG}}': ab(os.path.join(a.parts, n + '.log.md')),
           '{{LECTURE_INFO}}': a.info, '{{GLOSSARY}}': g}
    for k, v in rep.items(): t = t.replace(k, v)
    left = re.findall(r'{{[A-Z_]+}}', t)
    if left: sys.exit(f'채우지 못한 자리표시자: {left}')
    write(a.out, t); print(f'프롬프트 {n} → {a.out} ({nchars(t):,}자)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('split'); p.add_argument('src'); p.add_argument('--out', default='chunks'); p.add_argument('--size', type=int, default=3500); p.add_argument('--min', type=int, default=2000)
    p = sp.add_parser('join'); p.add_argument('chunks'); p.add_argument('parts'); p.add_argument('--header', required=True); p.add_argument('--out', required=True)
    p = sp.add_parser('logs'); p.add_argument('parts'); p.add_argument('--name', required=True); p.add_argument('--out', required=True); p.add_argument('--lecture'); p.add_argument('--print-21', action='store_true')
    p = sp.add_parser('gloss'); p.add_argument('log'); p.add_argument('--out', required=True)
    p = sp.add_parser('slides'); p.add_argument('pdf'); p.add_argument('--out', required=True); p.add_argument('--first', type=int, default=1)
    p = sp.add_parser('prompt'); p.add_argument('--template', required=True); p.add_argument('--n', type=int, required=True); p.add_argument('--total', type=int, required=True)
    p.add_argument('--rules', required=True); p.add_argument('--slides', required=True); p.add_argument('--chunks', default='chunks'); p.add_argument('--parts', default='parts')
    p.add_argument('--info', required=True); p.add_argument('--glossary'); p.add_argument('--out', required=True)
    a = ap.parse_args()
    {'split': cmd_split, 'join': cmd_join, 'logs': cmd_logs, 'gloss': cmd_gloss, 'slides': cmd_slides, 'prompt': cmd_prompt}[a.cmd](a)


if __name__ == '__main__':
    main()
