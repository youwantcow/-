#!/usr/bin/env python3
"""exam_tools.py — `기출 정리`(제작 지침 7-1)를 원문 보존 원칙대로 돌리기 위한 도구 (운영지침 v2.0)

  extract  기출.pdf --out 기출.txt
           pdftotext 로 읽기 순서를 지켜 글자를 뽑는다. 2단 편집이면 쪽을 왼쪽·오른쪽 열로 잘라 차례로 뽑는다.
           쪽마다 `=== p.N ===` 줄. (스캔본이라 글자가 거의 없으면 그 사실을 알리고 멈춘다 → 전사본 절차)
  number   기출.txt --out numbered.txt
           줄마다 `L0001|` 번호를 붙인다(서브에이전트가 문항 경계를 줄 번호로 적게 하기 위해). 빈 줄은 유지.
  assemble --subject 생화학 --out 기출/ --index 배정.tsv [--index 배정2.tsv …] --text 이름=기출.txt [--text …]
           배정표(서브에이전트 출력)대로 원문 줄을 **그대로 잘라** 주제별 파일 · 미분류 · 색인을 만들고 대조 보고를 출력한다.
           배정표 열(탭): 파일 | ID | 시작줄 | 끝줄 | 교수 원표기 | 교수 정리 | 정리 근거 | 주제 | 공통 | 복기본 | 재출제 | 배정 근거
             - 주제: 2-2의 주제명 그대로. 미분류면 `미분류`. 공통이면 주제 칸에 `A·B`처럼 모두 적고 공통 칸에 `공통`.
             - 복기본: 같은 ID의 다른 복기본이면 `A`/`B`… (한 ID 아래 모두 싣는다). 재출제: `22-1-5`처럼 다른 ID.
  stems    배정.tsv … --text 이름=기출.txt … --out stems.tsv
           문항마다 첫 줄(발문 요지)을 뽑아 재출제 후보 찾기용 표를 만든다.
"""
import argparse, os, re, subprocess, sys
from collections import OrderedDict


def read(p): return open(p, encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)) or '.', exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def page_info(pdf):
    out = run(['pdfinfo', pdf]); n = re.search(r'Pages:\s+(\d+)', out)
    s = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', out)
    return (int(n.group(1)) if n else 0), (float(s.group(1)) if s else 595.0), (float(s.group(2)) if s else 842.0)


def two_column(pdf, page):
    """-layout 출력에서 넓은 안쪽 공백이 있는 줄이 많으면 2단으로 본다"""
    lay = run(['pdftotext', '-layout', '-f', str(page), '-l', str(page), pdf, '-'])
    lines = [l for l in lay.splitlines() if l.strip()]
    if len(lines) < 8: return False
    inner = sum(1 for l in lines if re.search(r'\S\s{12,}\S', l))      # 두 열이 나란히 있는 줄
    lead = sum(1 for l in lines if re.match(r'\s{25,}\S', l))           # 오른쪽 열에만 글자가 있는 줄
    return (inner + lead) / len(lines) > 0.3


def cmd_extract(a):
    n, W, H = page_info(a.pdf)
    if not n: sys.exit('pdfinfo 로 쪽수를 읽지 못했다')
    out, total = [], 0
    for p in range(1, n + 1):
        if two_column(a.pdf, p):
            l = run(['pdftotext', '-f', str(p), '-l', str(p), '-x', '0', '-y', '0', '-W', str(int(W / 2)), '-H', str(int(H)), a.pdf, '-'])
            r = run(['pdftotext', '-f', str(p), '-l', str(p), '-x', str(int(W / 2)), '-y', '0', '-W', str(int(W / 2) + 1), '-H', str(int(H)), a.pdf, '-'])
            t = l.rstrip('\f\n') + '\n' + r.rstrip('\f\n'); tag = ' (2단)'
        else:
            t = run(['pdftotext', '-f', str(p), '-l', str(p), a.pdf, '-']).rstrip('\f\n'); tag = ''
        t = re.sub(r'\n{3,}', '\n\n', t)
        total += len(re.sub(r'\s', '', t))
        out.append(f'=== p.{p}{tag} ===\n{t}\n')
    write(a.out, '\n'.join(out))
    if total < 40 * n:
        print(f'⚠ 글자가 거의 없다({total}자/{n}쪽) — 스캔본이면 전사본 절차(7-1-1)로')
    print(f'{os.path.basename(a.pdf)}: {n}쪽 · {total:,}자 → {a.out}')


def cmd_number(a):
    lines = read(a.txt).split('\n')
    write(a.out, '\n'.join(f'L{i:04d}|{l}' for i, l in enumerate(lines, 1)))
    print(f'{len(lines)}줄 → {a.out}')


# ---------- assemble ----------
COLS = ['파일', 'ID', '시작줄', '끝줄', '교수 원표기', '교수 정리', '정리 근거', '주제', '공통', '복기본', '재출제', '배정 근거']


def read_index(paths):
    rows = []
    for p in paths:
        hdr = None
        for l in read(p).splitlines():
            if not l.strip() or l.startswith('#'): continue
            cs = [c.strip() for c in l.rstrip('\n').split('\t')]
            if hdr is None:
                if cs[0] == '파일' or cs[1:2] == ['ID']:
                    hdr = cs; continue
                hdr = COLS  # 머리 없이 바로 행이면 표준 열 순서로 본다
            d = dict(zip(hdr, cs + [''] * (len(hdr) - len(cs))))
            if not d.get('ID') or not d.get('시작줄'): continue
            rows.append(d)
    return rows


def lines_of(text, s, e):
    L = text.split('\n')
    s, e = int(re.sub(r'\D', '', s)), int(re.sub(r'\D', '', e))
    if s < 1 or e > len(L) or s > e: raise ValueError(f'줄 범위 밖: {s}-{e} (파일 {len(L)}줄)')
    return '\n'.join(L[s - 1:e]).strip('\n')


def topics_of(d):
    t = d.get('주제', '').strip()
    if not t or t == '미분류': return []
    return [x.strip() for x in re.split(r'[·,/]', t) if x.strip()]


def cmd_assemble(a):
    texts = {}
    for spec in a.text:
        name, path = spec.split('=', 1); texts[name] = read(path)
    rows = read_index(a.index)
    by_id = OrderedDict()
    for d in rows:
        by_id.setdefault(d['ID'], []).append(d)
    files = OrderedDict(); unassigned = []; idx = []; errors = []
    n_single = n_common = n_un = 0
    for qid, ds in by_id.items():
        d0 = ds[0]; tops = topics_of(d0)
        try:
            bodies = []
            for d in ds:
                if d['파일'] not in texts: raise ValueError(f"--text 에 없는 파일 이름: {d['파일']}")
                b = lines_of(texts[d['파일']], d['시작줄'], d['끝줄'])
                tag = f" · 복기본 {d['복기본']}" if d.get('복기본') else ''
                bodies.append((tag, b, d))
        except ValueError as ex:
            errors.append(f'{qid}: {ex}'); continue
        head = f"### {qid}" + (f" · 복기본 {len(bodies)}개" if len(bodies) > 1 else '')
        meta = f"- 교수: {d0.get('교수 원표기') or '(표기 없음)'} → {d0.get('교수 정리') or '미상'}" + (f" ({d0.get('정리 근거')})" if d0.get('정리 근거') else '')
        if d0.get('재출제'): meta += f" · 재출제: {d0['재출제']}"
        if len(tops) > 1: meta += f" · 공통: {' · '.join(tops)}"
        block = head + '\n' + meta + '\n\n' + '\n\n'.join((f"**복기본 {d['복기본']}**\n" if d.get('복기본') else '') + b for tag, b, d in bodies) + '\n'
        if not tops:
            n_un += 1
            unassigned.append(block + f"- 미분류 이유 · 후보: {d0.get('배정 근거', '')}\n")
        else:
            if len(tops) > 1: n_common += 1
            else: n_single += 1
            for t in tops: files.setdefault(t, []).append((qid, len(tops) > 1, block))
        idx.append((qid, d0))
    os.makedirs(a.out, exist_ok=True)
    made = []
    for t, items in files.items():
        singles = [q for q, c, _ in items if not c]; commons = [q for q, c, _ in items if c]
        hdr = (f"# 기출_{a.subject}_{t}\n\n- 문항 수 {len(items)} = 단독 {len(singles)} + 공통 {len(commons)}\n"
               + (f"- 공통 문항: {', '.join(commons)}\n" if commons else '') + "- 원문 보존: 발문·선지·답·근거는 기출 파일 글자 그대로(오탈자 포함). 정리는 `exam_tools.py assemble`.\n\n")
        path = os.path.join(a.out, f'기출_{a.subject}_{t}.md')
        write(path, hdr + '\n'.join(b for _, _, b in items)); made.append((t, len(items), os.path.basename(path)))
    if unassigned:
        write(os.path.join(a.out, f'기출_{a.subject}_미분류.md'), f"# 기출_{a.subject}_미분류 ({len(unassigned)}문항)\n\n" + '\n'.join(unassigned))
    L = [f'# 기출_{a.subject}_색인', '', f'- 원본 {len(by_id)} = 단독 배정 {n_single} + 공통 {n_common} + 미분류 {n_un}', '',
         '| ID | 파일 | 교수 원표기 → 정리 (근거) | 배정 주제 | 공통 | 재출제 · 복기본 | 배정 근거 |', '|---|---|---|---|---|---|---|']
    for qid, d in idx:
        tops = topics_of(d)
        L.append(f"| {qid} | {d['파일']} | {d.get('교수 원표기') or '—'} → {d.get('교수 정리') or '미상'}{(' (' + d['정리 근거'] + ')') if d.get('정리 근거') else ''} | "
                 f"{' · '.join(tops) if tops else '미분류'} | {'공통' if len(tops) > 1 else ''} | {d.get('재출제', '')}{(' · 복기본 ' + str(len(by_id[qid]))) if len(by_id[qid]) > 1 else ''} | {d.get('배정 근거', '')} |")
    write(os.path.join(a.out, f'기출_{a.subject}_색인.md'), '\n'.join(L) + '\n')
    tot_assign = sum(n for _, n, _ in made)
    print(f'대조 보고: 원본 {len(by_id)}문항(ID 기준 · 복기본 여럿은 하나) = 단독 {n_single} + 공통 {n_common} + 미분류 {n_un}')
    print(f'주제별 파일 문항 수 합계 {tot_assign} = 단독 {n_single} + 공통 배정 횟수 합 {tot_assign - n_single}  → ' + ('일치' if tot_assign - n_single == sum(len(topics_of(d)) for q, d in idx if len(topics_of(d)) > 1) else '불일치 ✗'))
    print('| 주제 | 문항 | 파일 |'); print('|---|---|---|')
    for t, n, f in made: print(f'| {t} | {n} | {f} |')
    if unassigned: print(f'| 미분류 | {len(unassigned)} | 기출_{a.subject}_미분류.md |')
    for e in errors: print('✗', e)
    sys.exit(1 if errors else 0)


def cmd_stems(a):
    texts = {}
    for spec in a.text:
        name, path = spec.split('=', 1); texts[name] = read(path)
    rows = read_index(a.index); seen = set(); L = ['ID\t파일\t교수\t주제\t발문 첫 줄']
    for d in rows:
        if d['ID'] in seen: continue
        seen.add(d['ID'])
        try: body = lines_of(texts[d['파일']], d['시작줄'], d['끝줄'])
        except Exception: body = ''
        stem = next((l.strip() for l in body.split('\n') if l.strip()), '')[:90]
        L.append(f"{d['ID']}\t{d['파일']}\t{d.get('교수 정리') or ''}\t{d.get('주제', '')}\t{stem}")
    write(a.out, '\n'.join(L) + '\n'); print(f'{len(L) - 1}문항 발문 → {a.out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('extract'); p.add_argument('pdf'); p.add_argument('--out', required=True)
    p = sp.add_parser('number'); p.add_argument('txt'); p.add_argument('--out', required=True)
    p = sp.add_parser('assemble'); p.add_argument('--subject', required=True); p.add_argument('--out', required=True); p.add_argument('--index', action='append', required=True); p.add_argument('--text', action='append', required=True)
    p = sp.add_parser('stems'); p.add_argument('index', nargs='+'); p.add_argument('--text', action='append', required=True); p.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.cmd == 'stems': a.index = a.index
    {'extract': cmd_extract, 'number': cmd_number, 'assemble': cmd_assemble, 'stems': cmd_stems}[a.cmd](a)


if __name__ == '__main__':
    main()
