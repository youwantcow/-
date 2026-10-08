#!/usr/bin/env python3
"""review_kit.py — STT 보정 강의록의 2차 검토(Gemini) 도구.

  make   강의록.md [--batch 40] [--out 검토요청.md] [--rules 규칙.txt]
         강의록의 〔?원문: …〕·〔불명확: …〕(구형 [불명확] 포함)에 ID를 붙여
         Gemini용 검토요청 파일(규칙 머리말 + 배치별 표)을 만든다.
  ids    강의록.md 58:37 02:03:29 …
         주어진 타임스탬프 블록에 있는 ID를 보여 준다(보정로그 2-1에 병기할 때).
  check  강의록.md gemini1.md [gemini2.md …] [--out 검토결과.md] [--all]
         Gemini 표를 ID로 대조한다: 받음·누락·중복·모르는 ID, 배치별 행 수.
         누락분은 재요청 파일로, 받은 것은 Claude 판단용 검토결과 파일로 만든다.
  apply  강의록.md 결정.md [--log 보정로그.md] [--out 강의록.md]
         Claude가 쓴 결정표를 강의록에 기계적으로 반영하고 로그 절을 덧붙인다.
         결정표: | ID | 조치 | 후보 | 대상 | 이유 |  조치 = 채택·대안·반대·동의·기각
           R행 채택: 〔불명확: ○○〕→ 후보〔?원문: ○○〕 (구형 [불명확]은 대상 칸에 대체할 원문 어절)
           R행 대안: 〔?원문: ○○ · 대안: 후보〕 / 반대: 〔?원문: ○○ · 2차 반대〕
           T행(표 2) 채택: 대상(현재 표기, 강의록에 1회만 있어야 함) → 후보〔?원문: 대상〕
         결정표에 검토결과의 '지문: `…`' 줄을 옮겨 두면 강의록이 바뀐 경우 반영을 막는다.

ID는 강의록 본문에서 결정적으로 매겨지므로, make 이후 apply까지 강의록을 고치지 않는다.
(파일 머리의 지문(sha1 앞 12자)으로 확인한다.)
"""
import argparse, hashlib, os, re, sys, unicodedata

MAX_BATCH = 40
TS_RE = re.compile(r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*$', re.M)
MARK_RE = re.compile(r'〔\?원문: [^〕]*〕|〔불명확: [^〕]*〕|\[불명확\]')
SEP = '\n---\n'

RULES = """너는 강의 녹취록(STT) 교정의 '두 번째 검토자'야.
첨부: ① 1차 보정이 끝난 강의록 ② 강의자료 PDF ③ 이 검토요청 파일(ID가 붙은 표).

[작업 범위]
- 내가 지정한 배치(예: B1)의 행만 채우고, 그 배치가 끝나면 멈춰. 다음 배치는 내가 요청할 때 한다.
- 강의록 본문을 다시 쓰지 마. 출력은 아래 두 표뿐이야.

[표 1 — 지정 배치의 모든 행, 빠짐없이]
출력 열: | ID | 판단 | 후보 | 근거 | 확신 |
- 문맥·표시는 다시 옮겨 적지 마. ID만 쓴다. 행을 빼거나 합치거나 순서를 바꾸지 마.
- 표시가 `고친말〔?원문: ○○〕`이면 ○○가 STT 원문, 앞 문맥 끝의 고친말이 1차 추정이야. 판단은 넷 중 하나:
  동의 / 새 후보(1차 추정과 다른 말일 때만) / 반대(1차 추정이 틀렸다고 보지만 대안 없음) / 판단 불가
- 표시가 `〔불명확: ○○〕`이면 ○○가 STT 원문이야. 판단은 새 후보 / 후보 없음 중 하나.
- 표시가 `[불명확]`(구형)이면 앞 문맥 끝의 어절이 STT 원문이야. 후보가 원문의 몇 어절을 대체하는지 근거에 적어.
- 근거에는 반드시 음절 대응을 적어: "원문 → 후보"와 차이 나는 음절 수(예: "주석→추석, 1음절").
  그다음에 문맥·슬라이드 쪽을 덧붙여.

[후보 규칙]
- 후보는 원문 ○○와 발음이 가까워야 해. 발음이 멀면 문맥상 그럴듯해도 '후보 없음'.
- 후보는 ○○의 범위만 대체해. 앞뒤 문장을 완성하거나, 교수님이 하지 않은 말을 보태거나,
  강의자료·교과서 내용을 끼워 넣지 마.
- 수량·수치에는 후보를 내지 마. 숫자가 들어간 용어(PI3K, HER2 등)는 대상이야.

[확신]
- 상: 음절 대부분이 겹치고 문맥상 다른 해석이 거의 없음
- 중: 발음이 가깝고 문맥에 맞지만 다른 해석도 가능
- 하: 추측

[표 2 — 표시 없는 곳의 오인식 의심]
- 지정 배치의 '시각 범위' 안에서만 찾아. 범위 밖은 보지 마.
- 출력 열: | 시각 | 현재 표기 | 후보 | 근거 | 확신 |  (현재 표기는 강의록에서 글자 그대로 복사)
- 없으면 "없음"이라고 한 줄.

[마지막 줄]
"B○: 입력 n행 / 표 1 출력 n행 / 표 2 m건" 을 적고 멈춰."""


# ---------- 공통 ----------
def read(p):
    return open(p, encoding='utf-8').read()


def write(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)


def body_start(t):
    i = t.find(SEP)
    return i + len(SEP) if i >= 0 else 0


def fingerprint(t):
    return hashlib.sha1(t.encode('utf-8')).hexdigest()[:12]


def lecture_name(path):
    n = os.path.splitext(os.path.basename(path))[0]
    return n[len('강의록_'):] if n.startswith('강의록_') else n


def extract(t):
    """강의록 본문의 표시 목록 [(id, start, end, mark, ts, pre, post, kind, orig)]"""
    b = body_start(t)
    stamps = [(m.start(), m.group(1)) for m in TS_RE.finditer(t) if m.start() >= b]
    rows, k = [], 0
    for m in MARK_RE.finditer(t, b):
        a, e, g = m.start(), m.end(), m.group(0)
        ts = '—'
        for p, s in stamps:
            if p <= a:
                ts = s
            else:
                break
        ls = t.rfind('\n', 0, a) + 1
        le = t.find('\n', e)
        le = len(t) if le < 0 else le
        pre = t[max(ls, a - 25):a]
        post = t[e:min(le, e + 10)]
        if g.startswith('〔?'):
            kind, orig = 'q', g[len('〔?원문: '):-1].split(' · ')[0]
        elif g.startswith('〔불명확'):
            kind, orig = 'u', g[len('〔불명확: '):-1]
        else:
            kind, orig = 'legacy', ''
        k += 1
        rows.append(dict(id=f'R{k:03d}', start=a, end=e, mark=g, ts=ts,
                         pre=pre, post=post, kind=kind, orig=orig))
    return rows, stamps


def cell(s):
    return s.replace('|', '／').replace('\n', ' ').strip()


def batches(rows, stamps, maxn=MAX_BATCH):
    """타임스탬프 경계를 우선해 최대 maxn행씩 나눈다."""
    out, cur = [], []
    minn = max(1, int(maxn * 0.75))
    for i, r in enumerate(rows):
        cur.append(r)
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt is None:
            break
        if len(cur) >= maxn or (len(cur) >= minn and nxt['ts'] != r['ts']):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    if len(out) > 1 and len(out[-1]) < maxn // 4 and len(out[-2]) + len(out[-1]) <= maxn + maxn // 4:
        last = out.pop()
        out[-1] = out[-1] + last
    res = []
    for j, bt in enumerate(out):
        start = bt[0]['ts']
        if j + 1 < len(out):
            end = out[j + 1][0]['ts']
            rng = f'{start} ~ {end} 직전' if end != bt[-1]['ts'] else f'{start} ~ {end} 블록 일부'
        else:
            rng = f'{start} ~ 끝'
        res.append(dict(name=f'B{j + 1}', rows=bt, range=rng))
    return res


def request_doc(title, fp, bts, total_note, rules=RULES):
    L = [f'# 검토요청 — {title}', '',
         f'- 강의록 지문: `{fp}` (이 파일은 이 버전의 강의록과 짝이다)',
         f'- {total_note}', '',
         '## Gemini 규칙', '', '```', rules, '```', '',
         '## 배치 목록', '', '| 배치 | ID 범위 | 행 수 | 시각 범위 |', '|---|---|---|---|']
    for b in bts:
        L.append(f"| {b['name']} | {b['rows'][0]['id']}–{b['rows'][-1]['id']} | {len(b['rows'])} | {b['range']} |")
    for b in bts:
        L += ['', f"## {b['name']} · {len(b['rows'])}행 · 시각 범위 {b['range']}", '',
              '| ID | 시각 | 앞 문맥 | 표시 | 뒤 문맥 | 판단 | 후보 | 근거 | 확신 |',
              '|---|---|---|---|---|---|---|---|---|']
        for r in b['rows']:
            L.append(f"| {r['id']} | {r['ts']} | …{cell(r['pre'])} | {cell(r['mark'])} | {cell(r['post'])}… |  |  |  |  |")
    return '\n'.join(L) + '\n'


# ---------- make ----------
def cmd_make(a):
    t = read(a.lecture)
    rows, stamps = extract(t)
    if not rows:
        sys.exit('표시(〔?원문〕·〔불명확〕·[불명확])가 없다.')
    bts = batches(rows, stamps, a.batch)
    nq = sum(r['kind'] == 'q' for r in rows)
    nu = sum(r['kind'] == 'u' for r in rows)
    nl = sum(r['kind'] == 'legacy' for r in rows)
    note = f'표시 총 {len(rows)} = 〔?원문〕 {nq} + 〔불명확〕 {nu}' + (f' + 구형 [불명확] {nl}' if nl else '') + f' = 배치 {len(bts)}개'
    name = lecture_name(a.lecture)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.lecture)), f'검토요청_{name}.md')
    rules = read(a.rules).strip() if a.rules else RULES
    write(out, request_doc(name, fingerprint(t), bts, note, rules))
    print(note)
    for b in bts:
        print(f"  {b['name']}: {b['rows'][0]['id']}–{b['rows'][-1]['id']} ({len(b['rows'])}행) · {b['range']}")
    print(f'→ {out}')


# ---------- ids ----------
def norm_ts(s):
    p = [int(x) for x in s.split(':')]
    while len(p) < 3:
        p.insert(0, 0)
    return tuple(p)


def cmd_ids(a):
    rows, _ = extract(read(a.lecture))
    for q in a.stamps:
        hit = [r for r in rows if r['ts'] != '—' and norm_ts(r['ts']) == norm_ts(q)]
        print(f'{q}: ' + (', '.join(f"{r['id']} {r['mark']}" for r in hit) if hit else '(표시 없음)'))


# ---------- Gemini 표 읽기 ----------
def parse_tables(text):
    """마크다운 표를 헤더 이름 기준으로 읽는다. 반환: [(헤더목록, 행dict)]"""
    out, header = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            header = None
            continue
        cells = [c.strip().strip('*`').strip() for c in s.strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cells if c):
            continue
        if header is None or any(h in cells for h in ('ID', '현재 표기', '판단')) and not re.fullmatch(r'R\d{3,}', cells[0]):
            header = cells
            continue
        out.append((header, dict(zip(header, cells + [''] * (len(header) - len(cells))))))
    return out


def get(d, *keys):
    for k in keys:
        for h, v in d.items():
            if h.startswith(k):
                return v
    return ''


# ---------- 음절 거리(참고용) ----------
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'


def jamo(s):
    r = []
    for ch in s:
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            r += [CHO[c // 588], JUNG[(c % 588) // 28]]
            if c % 28:
                r.append(JONG[c % 28])
        elif ch.isalnum():
            r.append(ch.lower())
    return r


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def dist(orig, cand):
    if not orig or not cand or cand in ('-', '—'):
        return ''
    hang = lambda s: sum('가' <= c <= '힣' for c in s)
    if hang(orig) == 0 or hang(cand) == 0:
        return '표기 다름'
    a, b = jamo(orig), jamo(cand)
    return f'{lev(a, b) / max(len(a), len(b)):.2f}'


# ---------- check ----------
def cmd_check(a):
    t = read(a.lecture)
    rows, stamps = extract(t)
    byid = {r['id']: r for r in rows}
    got, dup, unknown, t2 = {}, [], [], []
    for p in a.gemini:
        for header, d in parse_tables(read(p)):
            first = header[0] if header else ''
            rid = get(d, 'ID')
            if re.fullmatch(r'R\d{3,}', rid or ''):
                if rid not in byid:
                    unknown.append(rid)
                elif rid in got:
                    dup.append(rid)
                else:
                    got[rid] = d
            elif get(d, '현재 표기'):
                t2.append(d)
    bts = batches(rows, stamps, a.batch)
    asked = [b for b in bts if a.all or any(r['id'] in got for r in b['rows'])]
    idle = [b for b in bts if b not in asked]
    pool = [r for b in asked for r in b['rows']]
    miss = [r for r in pool if r['id'] not in got]
    print(f'요청 배치 {len(asked)}개 · {len(pool)}행 = 받음 {len(got)} + 누락 {len(miss)}'
          f'   (중복 {len(dup)} · 모르는 ID {len(unknown)} · 표 2 {len(t2)}건)')
    for b in asked:
        n = sum(r['id'] in got for r in b['rows'])
        flag = '' if n == len(b['rows']) else '  ← 누락'
        print(f"  {b['name']}: {n}/{len(b['rows'])}{flag}")
    if idle:
        print('  아직 안 받은 배치:', ', '.join(b['name'] for b in idle))
    if dup:
        print('  중복 ID(첫 행만 사용):', ', '.join(sorted(set(dup))))
    if unknown:
        print('  강의록에 없는 ID:', ', '.join(sorted(set(unknown))))

    name = lecture_name(a.lecture)
    d0 = os.path.dirname(os.path.abspath(a.out)) if a.out else os.path.dirname(os.path.abspath(a.lecture))
    if miss:
        rb = batches(miss, stamps, a.batch)
        for i, b in enumerate(rb):
            b['name'] = f'R{i + 1}'
        rp = os.path.join(d0, f'재요청_{name}.md')
        write(rp, request_doc(name + ' (누락분 재요청)', fingerprint(t), rb,
                              f'누락 {len(miss)}건 = 배치 {len(rb)}개 (ID는 원래 번호 유지)'))
        print(f'→ 재요청 {rp}')

    L = [f'# 검토결과 — {name}', '', f'- 강의록 지문: `{fingerprint(t)}`',
         f'- 받음 {len(got)} / 총 {len(rows)} · 표 2 {len(t2)}건',
         '- 음절거리: 자모 편집거리 비율(0 = 같음, 0.5 이상 = 발음이 멂). 참고용이며 판단은 Claude가 한다.', '',
         '## 표 1', '',
         '| ID | 시각 | 앞 문맥 | 표시 | 판단 | 후보 | 근거 | 확신 | 음절거리 |',
         '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        if r['id'] not in got:
            continue
        d = got[r['id']]
        cand = get(d, '후보')
        orig = r['orig']  # 구형 [불명확]은 원문 범위를 알 수 없어 거리 계산 생략
        L.append(f"| {r['id']} | {r['ts']} | …{cell(r['pre'])} | {cell(r['mark'])} | {cell(get(d, '판단'))} | "
                 f"{cell(cand)} | {cell(get(d, '근거'))} | {cell(get(d, '확신'))} | {dist(orig, cand)} |")
    L += ['', '## 표 2 (현재 표기의 강의록 출현 횟수 — 1이어야 반영 가능)', '',
          '| # | 시각 | 현재 표기 | 후보 | 근거 | 확신 | 출현 | 음절거리 |', '|---|---|---|---|---|---|---|---|']
    b0 = body_start(t)
    for i, d in enumerate(t2, 1):
        cur = get(d, '현재 표기')
        n = t.count(cur, b0) if cur else 0
        L.append(f"| T{i:02d} | {cell(get(d, '시각'))} | {cell(cur)} | {cell(get(d, '후보'))} | {cell(get(d, '근거'))} | "
                 f"{cell(get(d, '확신'))} | {n} | {dist(cur, get(d, '후보'))} |")
    out = a.out or os.path.join(d0, f'검토결과_{name}.md')
    write(out, '\n'.join(L) + '\n')
    print(f'→ 검토결과 {out}')


# ---------- apply ----------
ACTIONS = ('채택', '대안', '반대', '동의', '기각')


def cmd_apply(a):
    t = read(a.lecture)
    dec = read(a.decisions)
    fp = re.search(r'지문: `([0-9a-f]{12})`', dec)
    if fp and fp.group(1) != fingerprint(t):
        sys.exit(f'강의록 지문이 다르다(결정표 {fp.group(1)} ≠ 강의록 {fingerprint(t)}). '
                 'make 이후 강의록이 바뀌어 ID가 어긋났을 수 있다. 검토요청을 다시 만들거나 원래 강의록을 쓸 것.')
    rows, _ = extract(t)
    byid = {r['id']: r for r in rows}
    edits, log, fail = [], [], []
    b0 = body_start(t)
    for header, d in parse_tables(dec):
        rid, act = get(d, 'ID'), get(d, '조치')
        cand, target, why = get(d, '후보'), get(d, '대상'), get(d, '이유')
        if act not in ACTIONS:
            continue
        if re.fullmatch(r'R\d{3,}', rid):
            r = byid.get(rid)
            if not r:
                fail.append(f'{rid}: 강의록에 없는 ID'); continue
            new = None
            if act == '채택':
                if r['kind'] == 'u':
                    edits.append((r['start'], r['end'], f"{cand}〔?원문: {r['orig']}〕"))
                elif r['kind'] == 'legacy':
                    if not target:
                        fail.append(f'{rid}: 구형 [불명확]은 대상(대체할 원문) 칸이 필요'); continue
                    s = r['start'] - len(target)
                    if s < 0 or t[s:r['start']] != target:
                        fail.append(f'{rid}: 대상 "{target}"이 [불명확] 바로 앞에 없음'); continue
                    edits.append((s, r['end'], f'{cand}〔?원문: {target}〕'))
                else:
                    fail.append(f'{rid}: 〔?〕에는 채택 대신 대안/반대/동의를 쓴다'); continue
            elif act == '대안':
                if r['kind'] != 'q':
                    fail.append(f'{rid}: 대안은 〔?원문〕에만'); continue
                if cand and r['pre'].rstrip().endswith(cand):
                    fail.append(f'{rid}: 후보 "{cand}"가 1차 추정과 같다 → 동의로 처리할 것'); continue
                edits.append((r['start'], r['end'], f"〔?원문: {r['orig']} · 대안: {cand}〕"))
            elif act == '반대':
                if r['kind'] != 'q':
                    fail.append(f'{rid}: 반대는 〔?원문〕에만'); continue
                edits.append((r['start'], r['end'], f"〔?원문: {r['orig']} · 2차 반대〕"))
            log.append((rid, r['ts'], '…' + cell(r['pre']) + cell(r['mark']), act, cand, why))
        elif rid.upper().startswith('T'):
            if act != '채택':
                log.append((rid, '', cell(target), act, cand, why)); continue
            idx = [m.start() for m in re.finditer(re.escape(target), t)] if target else []
            idx = [i for i in idx if i >= b0]
            if len(idx) != 1:
                fail.append(f'{rid}: 대상 "{target}" 출현 {len(idx)}회(1회여야 함)'); continue
            edits.append((idx[0], idx[0] + len(target), f'{cand}〔?원문: {target}〕'))
            log.append((rid, '', cell(target), act, cand, why))
    edits.sort()
    for x, y in zip(edits, edits[1:]):
        if x[1] > y[0]:
            sys.exit(f'겹치는 수정이 있다: {t[x[0]:x[1]]} / {t[y[0]:y[1]]}')
    for s, e, n in reversed(edits):
        t = t[:s] + n + t[e:]
    out = a.out or a.lecture
    write(out, t)
    cnt = {k: sum(1 for l in log if l[3] == k) for k in ACTIONS}
    print('반영 ' + ' · '.join(f'{k} {v}' for k, v in cnt.items()) + f' · 실패 {len(fail)}')
    for f in fail:
        print('  실패', f)
    print(f'→ 강의록 {out} (지문 {fingerprint(t)})')
    if a.log:
        lg = read(a.log).rstrip()
        nums = [int(n) for n in re.findall(r'^## (\d+)\.', lg, re.M)]
        k = (max(nums) + 1) if nums else 1
        L = ['', '', f'## {k}. 2차 검토(Gemini) 반영', '',
             '반영 형식: 〔불명확〕 채택 → `후보〔?원문: ○○〕` · 〔?〕 대안 → `〔?원문: ○○ · 대안: 후보〕` · 반대 → `〔?원문: ○○ · 2차 반대〕`', '',
             '| ID | 시각 | 위치 | 조치 | 후보 | 이유 |', '|---|---|---|---|---|---|']
        L += [f'| {r} | {s} | {w} | {c} | {cell(d)} | {cell(e)} |' for r, s, w, c, d, e in log]
        write(a.log, lg + '\n'.join(L) + '\n')
        print(f'→ 로그 {a.log} ({k}절 추가)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    m = sp.add_parser('make'); m.add_argument('lecture'); m.add_argument('--batch', type=int, default=MAX_BATCH); m.add_argument('--out'); m.add_argument('--rules', help='Gemini 규칙 머리말을 이 파일 내용으로 바꾼다')
    i = sp.add_parser('ids'); i.add_argument('lecture'); i.add_argument('stamps', nargs='+')
    c = sp.add_parser('check'); c.add_argument('lecture'); c.add_argument('gemini', nargs='+'); c.add_argument('--batch', type=int, default=MAX_BATCH); c.add_argument('--out'); c.add_argument('--all', action='store_true', help='받은 행이 없는 배치도 누락으로 센다')
    p = sp.add_parser('apply'); p.add_argument('lecture'); p.add_argument('decisions'); p.add_argument('--log'); p.add_argument('--out')
    a = ap.parse_args()
    {'make': cmd_make, 'ids': cmd_ids, 'check': cmd_check, 'apply': cmd_apply}[a.cmd](a)


if __name__ == '__main__':
    main()
