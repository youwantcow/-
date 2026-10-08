#!/usr/bin/env python3
"""exam_tools.py — `기출정리`(제작 지침 7-1)를 원문 보존 원칙대로, 그림까지 챙겨 돌리기 위한 도구 (지침 v1.9)

  extract  기출.pdf --out 기출.txt
           pdftotext 로 읽기 순서를 지켜 글자를 뽑는다. 2단 편집이면 쪽을 왼쪽·오른쪽 열로 잘라 차례로 뽑는다.
           쪽마다 `=== p.N ===` 줄. (스캔본이라 글자가 거의 없으면 그 사실을 알리고 멈춘다 → 전사본 절차)
           한글(hwp)·워드(docx) 파일은 먼저 PDF로 내보내서 쓴다.
  number   기출.txt --out numbered.txt
           줄마다 `L0001|` 번호를 붙인다(배정표에 문항 경계를 줄 번호로 적기 위해). 빈 줄은 유지.
  figs     기출.pdf --out figs/ [--min 40] [--vec 20]
           쪽마다 그림이 있을 만한 곳을 찾는다: ① 래스터 이미지(사진·캡처)는 bbox 를 읽어 figs/auto_pN_k.png 로 바로 잘라 두고
           ② 벡터 도형(구조식·화살표·그래프)이 --vec(기본 20)개 이상인 쪽은 「벡터 n개」로 알린다(자동으로 못 자른다 → pages --grid 로 보고 crop).
           결과는 figs/figs.tsv(쪽 | 종류 | 파일 | 위치) 와 채팅용 표. 어느 문항의 그림인지는 Claude 가 쪽 이미지를 보고 정한다.
  pages    기출.pdf --out pages/ [--grid 20] [--dpi 110] [--pages 3,5-7]
           쪽을 JPEG 로 렌더한다. --grid N 이면 N×N 격자와 눈금(0~N)을 덧그린다 → crop 의 --box 를 눈금으로 읽는다.
  crop     기출.pdf --page N --box x0,y0,x1,y1 --out figs/ID.png [--grid 20] [--dpi 200] [--pad 0.01]
           쪽 N 의 사각형을 잘라 PNG 로 둔다. --box 값이 모두 1 이하면 쪽의 비율(0~1), 아니면 --grid 눈금 단위.
           그림 하나 = 파일 하나. 한 문항에 그림이 둘이면 ID.png · ID_2.png 처럼 둔다.
  assemble --subject 생화학 --out 기출/ --index 배정.tsv [--index …] --text 이름=기출.txt [--text …]
           [--figs figs/ --figpdf 기출그림_생화학.pdf [--prev-figpdf 기존_기출그림.pdf]] [--append]
           배정표대로 원문 줄을 **그대로 잘라** 주제별 파일 · 미분류 · 색인을 만들고 대조 보고를 출력한다.
           배정표 열(탭): 파일 | ID | 시작줄 | 끝줄 | 교수 원표기 | 교수 정리 | 정리 근거 | 주제 | 공통 | 복기본 | 재출제 | 배정 근거 | 그림
             - 주제: 2-2의 주제명 그대로. 미분류면 `미분류`. 공통이면 주제 칸에 `A·B`처럼 모두 적고 공통 칸에 `공통`.
             - 복기본: 같은 ID의 다른 복기본이면 `A`/`B`… (한 ID 아래 모두 싣는다). 재출제: `22-1-5`처럼 다른 ID.
             - 그림: 이 문항의 그림 파일(figs/ 안의 이름, 여러 개면 `;`로 — 첫 행에만 적는다). 그림이 있어야 하는데 원본에 없으면 `누락`. 그림 없는 문항은 비운다.
             - 머리 줄의 열 이름은 띄어쓰기를 무시하고 맞춘다(「교수 원표기」=「교수원표기」). 머리 줄이 없으면 위 순서로 본다.
           --figs/--figpdf 가 있으면 그림 파일을 한 장에 하나씩 모아 `기출그림_[과목].pdf` 를 만들고, 문항 블록과 색인에
           `〔그림 n〕`(그 PDF의 n쪽) 표시를 넣는다. --prev-figpdf(지난 정리의 PDF)가 있으면 그 뒤에 이어 붙인다(기존 쪽번호 유지).
           --append 면 --out 에 이미 있는 주제별 파일 · 미분류 · 색인에 **더한다**(같은 ID는 새 것으로 바꾼다). 기출정리를 여러 번
           나눠 돌릴 때 쓴다 — 그 전에 이번 배정표에 나온 주제의 기존 파일과 색인 · 미분류를 지식에서 내려 --out 에 두어야 한다.
  stems    배정.tsv … --text 이름=기출.txt … --out stems.tsv
           문항마다 첫 줄(발문 요지)을 뽑아 재출제 후보 찾기용 표를 만든다.
"""
import argparse, glob, os, re, subprocess, sys
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


def need(mod, pkg=None):
    try:
        return __import__(mod)
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg or mod, '--break-system-packages'])
        return __import__(mod)


# ---------- extract · number ----------
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
    if not n: sys.exit('pdfinfo 로 쪽수를 읽지 못했다 (PDF가 맞는지, hwp·docx 면 PDF로 내보냈는지 확인)')
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


# ---------- 쪽 렌더 · 그림 ----------
def render_page(pdf, page, dpi):
    """쪽 하나 → PIL Image (pdftoppm)"""
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['pdftoppm', '-r', str(dpi), '-f', str(page), '-l', str(page), '-png', pdf, os.path.join(d, 'pg')], check=True)
        fs = [f for f in os.listdir(d) if f.endswith('.png')]
        if not fs: raise RuntimeError(f'{page}쪽 렌더 실패')
        im = Image.open(os.path.join(d, fs[0])); im.load()
        return im.convert('RGB')


def font(size):
    """한글이 되는 글꼴을 찾는다(없으면 기본 글꼴 — 그때는 한글이 깨지므로 호출 쪽에서 ASCII 만 쓴다). 반환: (font, 한글 가능 여부)"""
    from PIL import ImageFont
    cands = ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
             '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
             '/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf', 'C:/Windows/Fonts/malgun.ttf', '/System/Library/Fonts/AppleSDGothicNeo.ttc']
    try:
        extra = run(['fc-list', ':lang=ko', 'file']).replace(':', '').split()
    except Exception:
        extra = []
    for p in cands + extra:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size), True
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size), False
    except TypeError:
        return ImageFont.load_default(), False


def parse_pages(spec, n):
    if not spec: return list(range(1, n + 1))
    out = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            s, e = part.split('-', 1); out += list(range(int(s), int(e) + 1))
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def cmd_pages(a):
    from PIL import ImageDraw
    n, W, H = page_info(a.pdf)
    os.makedirs(a.out, exist_ok=True)
    f, _ = font(max(12, a.dpi // 8))
    for p in parse_pages(a.pages, n):
        im = render_page(a.pdf, p, a.dpi)
        if a.grid:
            dr = ImageDraw.Draw(im, 'RGBA'); w, h = im.size; g = a.grid
            for i in range(g + 1):
                x = round(i * w / g); y = round(i * h / g)
                dr.line([(x, 0), (x, h)], fill=(255, 0, 0, 90 if i % 5 else 170), width=1)
                dr.line([(0, y), (w, y)], fill=(255, 0, 0, 90 if i % 5 else 170), width=1)
                dr.text((min(x + 2, w - 24), 2), str(i), fill=(220, 0, 0, 255), font=f)
                dr.text((2, min(y + 2, h - 18)), str(i), fill=(220, 0, 0, 255), font=f)
        path = os.path.join(a.out, f'p{p}.jpg'); im.save(path, 'JPEG', quality=85)
    print(f'{os.path.basename(a.pdf)}: {len(parse_pages(a.pages, n))}쪽 렌더 → {a.out}/pN.jpg' + (f' (격자 {a.grid}×{a.grid}, 눈금 0~{a.grid}: 왼쪽 위가 0,0)' if a.grid else ''))


def cmd_figs(a):
    pdfplumber = need('pdfplumber')
    os.makedirs(a.out, exist_ok=True)
    rows, auto = [], 0
    with pdfplumber.open(a.pdf) as doc:
        for p, page in enumerate(doc.pages, 1):
            W, H = float(page.width), float(page.height)
            k = 0
            for im in page.images:
                x0, top, x1, bottom = float(im['x0']), float(im['top']), float(im['x1']), float(im['bottom'])
                if (x1 - x0) < a.min or (bottom - top) < a.min:
                    continue  # 로고·구분선 크기는 건너뛴다
                k += 1
                box = (max(0, x0 / W), max(0, top / H), min(1, x1 / W), min(1, bottom / H))
                name = f'auto_p{p}_{k}.png'
                try:
                    crop_to(a.pdf, p, box, os.path.join(a.out, name), 200, 0.005)
                    auto += 1
                    rows.append((p, '이미지', name, '%.2f,%.2f,%.2f,%.2f' % box))
                except Exception as ex:
                    rows.append((p, '이미지', f'(실패: {ex})', '%.2f,%.2f,%.2f,%.2f' % box))
            vec = len(page.curves) + len(page.lines) + len(page.rects)
            if vec >= a.vec:
                rows.append((p, f'벡터 {vec}개', '(자동 추출 불가 — pages --grid 로 보고 crop)', ''))
    write(os.path.join(a.out, 'figs.tsv'), '쪽\t종류\t파일\t위치(x0,y0,x1,y1 비율)\n' + '\n'.join('\t'.join(map(str, r)) for r in rows) + '\n')
    cand = sorted({r[0] for r in rows})
    print(f'{os.path.basename(a.pdf)}: 그림 후보 쪽 {len(cand)}개 {cand} · 자동 추출 이미지 {auto}개 → {a.out}/ (목록 figs.tsv)')
    if rows:
        print('| 쪽 | 종류 | 파일 | 위치 |'); print('|---|---|---|---|')
        for r in rows: print(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} |')
    print('※ 후보가 없어도 발문에 "그림·구조·다음 중 …"가 있으면 그 쪽을 pages 로 열어 확인할 것. 어느 문항의 그림인지는 쪽 이미지를 보고 배정표 「그림」 칸에 적는다.')


def crop_to(pdf, page, box, out, dpi, pad):
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    im = render_page(pdf, page, dpi); w, h = im.size
    x0, y0, x1, y1 = box
    x0, y0 = max(0.0, x0 - pad), max(0.0, y0 - pad); x1, y1 = min(1.0, x1 + pad), min(1.0, y1 + pad)
    if x1 <= x0 or y1 <= y0: raise ValueError(f'상자가 비었다: {box}')
    im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))).save(out, 'PNG')
    return out


def cmd_crop(a):
    vals = [float(v) for v in a.box.split(',')]
    if len(vals) != 4: sys.exit('--box 는 x0,y0,x1,y1 네 값')
    if all(v <= 1 for v in vals): box = tuple(vals)
    else: box = tuple(v / a.grid for v in vals)
    crop_to(a.pdf, a.page, box, a.out, a.dpi, a.pad)
    from PIL import Image
    w, h = Image.open(a.out).size
    print(f'p.{a.page} {a.box} → {a.out} ({w}×{h}px)')


# ---------- assemble ----------
COLS = ['파일', 'ID', '시작줄', '끝줄', '교수 원표기', '교수 정리', '정리 근거', '주제', '공통', '복기본', '재출제', '배정 근거', '그림']
COL_NORM = {re.sub(r'\s+', '', c): c for c in COLS}
FIG_RE = re.compile(r'〔그림 (\d+)〕')


def read_index(paths):
    rows = []
    for p in paths:
        hdr = None
        for l in read(p).splitlines():
            if not l.strip() or l.startswith('#'): continue
            cs = [c.strip() for c in l.rstrip('\n').split('\t')]
            if hdr is None:
                if cs[0] == '파일' or cs[1:2] == ['ID']:
                    hdr = [COL_NORM.get(re.sub(r'\s+', '', c), c) for c in cs]  # 머리의 띄어쓰기 차이는 무시한다
                    unknown = [h for h in hdr if h not in COLS]
                    if unknown: print(f'⚠ {os.path.basename(p)}: 모르는 열 {unknown} (쓸 수 있는 열: {COLS})')
                    continue
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


def fig_names(d):
    g = (d.get('그림') or '').strip()
    if not g or g in ('누락', '없음', '—', '-'): return []
    return [x.strip() for x in re.split(r'[;,]', g) if x.strip()]


def pdf_pages(path):
    try: return page_info(path)[0]
    except Exception: return 0


def make_figpdf(items, out, prev=None, subject=''):
    """items: [(ID, 주제표시, 원본표시, 이미지경로)] → 한 장에 하나씩. prev 가 있으면 그 쪽들 뒤에 붙인다. 반환: (처음 새 쪽 번호, 총 쪽수)"""
    from PIL import Image, ImageDraw
    import shutil
    if prev and os.path.abspath(prev) == os.path.abspath(out):  # 같은 파일에 덧붙일 때는 원본을 먼저 비켜 둔다
        shutil.copy2(prev, out + '.prev.pdf'); prev = out + '.prev.pdf'
    start = pdf_pages(prev) + 1 if prev else 1
    pages = []
    f, ko = font(22)
    for i, (qid, topic, src, path) in enumerate(items):
        im = Image.open(path).convert('RGB')
        maxw = 1400
        if im.width > maxw: im = im.resize((maxw, int(im.height * maxw / im.width)))
        if im.width < 500: im = im.resize((500, int(im.height * 500 / im.width)))
        head = f'그림 {start + i} · {qid} · {topic} · 원본 {src}' if ko else f'fig {start + i} / {src}'
        pg = Image.new('RGB', (im.width + 40, im.height + 70), 'white')
        dr = ImageDraw.Draw(pg); dr.text((20, 14), head, fill=(60, 60, 60), font=f)
        dr.line([(20, 48), (pg.width - 20, 48)], fill=(200, 200, 200), width=1)
        pg.paste(im, (20, 56)); pages.append(pg)
    tmp = out + '.new.pdf' if prev else out
    if pages:
        pages[0].save(tmp, 'PDF', save_all=True, append_images=pages[1:], resolution=150)
    if prev:
        if not pages:
            if os.path.abspath(prev) != os.path.abspath(out): shutil.copy2(prev, out)
        else:
            try:
                pypdf = need('pypdf')
                w = pypdf.PdfWriter()
                for src in (prev, tmp):
                    for pg in pypdf.PdfReader(src).pages: w.add_page(pg)
                with open(out, 'wb') as fh: w.write(fh)
                os.remove(tmp)
            except Exception as ex:  # pypdf 가 안 되면 기존 쪽을 렌더해 다시 묶는다(쪽 번호는 같다)
                old = [render_page(prev, p, 150) for p in range(1, start)]
                old[0].save(out, 'PDF', save_all=True, append_images=old[1:] + pages, resolution=150)
                os.remove(tmp)
                print(f'  (pypdf 대신 렌더 병합: {ex})')
        if prev.endswith('.prev.pdf') and os.path.exists(prev): os.remove(prev)
    return start, start - 1 + len(pages)


def split_blocks(md):
    """주제별 파일 → (머리, OrderedDict{ID: 블록})"""
    parts = re.split(r'(?m)^(?=### )', md)
    head = parts[0]; blocks = OrderedDict()
    for b in parts[1:]:
        m = re.match(r'### (\S+)', b)
        if m: blocks[m.group(1)] = b if b.endswith('\n') else b + '\n'
    return head, blocks


def topic_header(subject, t, blocks):
    def meta(b):
        ls = b.split('\n'); return ls[1] if len(ls) > 1 else ''
    commons = [q for q, b in blocks.items() if '· 공통:' in meta(b)]
    n = len(blocks)
    return (f"# 기출_{subject}_{t}\n\n- 문항 수 {n} = 단독 {n - len(commons)} + 공통 {len(commons)}\n"
            + (f"- 공통 문항: {', '.join(commons)}\n" if commons else '')
            + "- 원문 보존: 발문·선지·답·근거는 기출 파일 글자 그대로(오탈자 포함). 정리는 `exam_tools.py assemble`.\n"
            + "- 그림: `〔그림 n〕`은 프로젝트 파일 `기출그림_[과목].pdf`의 n쪽. `그림: 누락`은 원본 복기에 그림이 빠진 문항.\n\n")


def parse_index_md(md):
    """기존 색인 → OrderedDict{ID: 행(list)}"""
    rows = OrderedDict(); hdr = None
    for l in md.splitlines():
        s = l.strip()
        if not s.startswith('|'): continue
        cs = [c.strip() for c in s.strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cs if c): continue
        if hdr is None: hdr = cs; continue
        if cs and cs[0]: rows[cs[0]] = cs + [''] * (len(hdr) - len(cs))
    return hdr, rows


IDX_HDR = ['ID', '파일', '교수 원표기 → 정리 (근거)', '배정 주제', '공통', '재출제 · 복기본', '그림', '배정 근거']


def cmd_assemble(a):
    texts = {}
    for spec in a.text:
        name, path = spec.split('=', 1); texts[name] = read(path)
    rows = read_index(a.index)
    by_id = OrderedDict()
    for d in rows:
        by_id.setdefault(d['ID'], []).append(d)
    # 그림 → 기출그림 PDF 쪽 번호
    fig_pages, fig_items, fig_missing = {}, [], []
    if a.figs or a.figpdf:
        if not (a.figs and a.figpdf): sys.exit('--figs 와 --figpdf 는 함께 준다')
        start = pdf_pages(a.prev_figpdf) + 1 if a.prev_figpdf else 1
        if a.append and not a.prev_figpdf and os.path.exists(os.path.join(a.out, f'기출_{a.subject}_색인.md')):
            _, old = parse_index_md(read(os.path.join(a.out, f'기출_{a.subject}_색인.md')))
            used = [int(n) for r in old.values() for n in FIG_RE.findall(' '.join(r))]
            if used: sys.exit(f'기존 색인에 그림 {max(used)}쪽까지 있다 — 기존 기출그림 PDF를 --prev-figpdf 로 주어야 쪽 번호가 이어진다')
        n = start
        for qid, ds in by_id.items():
            names = fig_names(ds[0])
            if not names: continue
            pages = []
            for nm in names:
                p = os.path.join(a.figs, nm)
                if not os.path.exists(p): fig_missing.append(f'{qid}: {nm}'); continue
                src = f"{ds[0]['파일']}"
                fig_items.append((qid, ' · '.join(topics_of(ds[0])) or '미분류', src, p)); pages.append(n); n += 1
            fig_pages[qid] = pages
    files = OrderedDict(); unassigned = OrderedDict(); idx = OrderedDict(); errors = []
    for qid, ds in by_id.items():
        d0 = ds[0]; tops = topics_of(d0)
        try:
            bodies = []
            for d in ds:
                if d['파일'] not in texts: raise ValueError(f"--text 에 없는 파일 이름: {d['파일']}")
                bodies.append((lines_of(texts[d['파일']], d['시작줄'], d['끝줄']), d))
        except ValueError as ex:
            errors.append(f'{qid}: {ex}'); continue
        head = f"### {qid}" + (f" · 복기본 {len(bodies)}개" if len(bodies) > 1 else '')
        meta = f"- 교수: {d0.get('교수 원표기') or '(표기 없음)'} → {d0.get('교수 정리') or '미상'}" + (f" ({d0.get('정리 근거')})" if d0.get('정리 근거') else '')
        if d0.get('재출제'): meta += f" · 재출제: {d0['재출제']}"
        if len(tops) > 1: meta += f" · 공통: {' · '.join(tops)}"
        g = (d0.get('그림') or '').strip(); figline = ''
        if qid in fig_pages and fig_pages[qid]:
            figline = '- 그림: ' + ' '.join(f'〔그림 {p}〕' for p in fig_pages[qid]) + f' (기출그림_{a.subject}.pdf)\n'
        elif g == '누락':
            figline = '- 그림: 누락 (원본 복기에 그림이 없음 — 발문만으로 풀어야 한다)\n'
        elif g and not fig_pages.get(qid):
            figline = f'- 그림: 파일 없음({g}) — 재확인\n'
        block = head + '\n' + meta + '\n' + figline + '\n' + '\n\n'.join((f"**복기본 {d['복기본']}**\n" if d.get('복기본') else '') + b for b, d in bodies) + '\n'
        if not tops:
            unassigned[qid] = block + f"- 미분류 이유 · 후보: {d0.get('배정 근거', '')}\n"
        else:
            for t in tops: files.setdefault(t, OrderedDict())[qid] = block
        figcell = ', '.join(map(str, fig_pages.get(qid, []))) or ('누락' if g == '누락' else '')
        idx[qid] = [qid, d0['파일'],
                    f"{d0.get('교수 원표기') or '—'} → {d0.get('교수 정리') or '미상'}{(' (' + d0['정리 근거'] + ')') if d0.get('정리 근거') else ''}",
                    ' · '.join(tops) if tops else '미분류', '공통' if len(tops) > 1 else '',
                    f"{d0.get('재출제', '')}{(' · 복기본 ' + str(len(ds))) if len(ds) > 1 else ''}", figcell, d0.get('배정 근거', '')]
    os.makedirs(a.out, exist_ok=True)
    # --append: 기존 파일과 합친다
    new_ids = set(idx)
    if a.append:
        for path in glob.glob(os.path.join(a.out, f'기출_{a.subject}_*.md')):
            name = os.path.basename(path)[len(f'기출_{a.subject}_'):-3]
            if name == '색인': continue
            _, old = split_blocks(read(path))
            if name == '미분류':
                merged = OrderedDict((q, b) for q, b in old.items() if q not in new_ids); merged.update(unassigned); unassigned = merged
            else:
                merged = OrderedDict((q, b) for q, b in old.items() if q not in new_ids)
                merged.update(files.get(name, OrderedDict())); files[name] = merged
        ip = os.path.join(a.out, f'기출_{a.subject}_색인.md')
        if os.path.exists(ip):
            hdr, old = parse_index_md(read(ip))
            if hdr and len(hdr) == 7:  # 구형 색인(그림 열 없음) → 그림 열을 끼운다
                old = OrderedDict((q, r[:6] + [''] + r[6:]) for q, r in old.items())
            merged = OrderedDict((q, r) for q, r in old.items() if q not in new_ids); merged.update(idx); idx = merged
    made = []
    for t, blocks in files.items():
        path = os.path.join(a.out, f'기출_{a.subject}_{t}.md')
        write(path, topic_header(a.subject, t, blocks) + '\n'.join(blocks.values())); made.append((t, len(blocks), os.path.basename(path)))
    up = os.path.join(a.out, f'기출_{a.subject}_미분류.md')
    if unassigned:
        write(up, f"# 기출_{a.subject}_미분류 ({len(unassigned)}문항)\n\n" + '\n'.join(unassigned.values()))
    elif os.path.exists(up):  # 전에 있던 미분류가 모두 배정됐으면 빈 파일로 바꿔 둔다(지식의 사본도 같은 내용으로 교체)
        write(up, f"# 기출_{a.subject}_미분류 (0문항)\n\n- 미분류 문항 없음.\n")
    n_un = len(unassigned); n_common = sum(1 for r in idx.values() if r[4] == '공통'); n_single = len(idx) - n_common - n_un
    n_fig = sum(1 for r in idx.values() if r[6] and r[6] != '누락'); n_figmiss = sum(1 for r in idx.values() if r[6] == '누락')
    L = [f'# 기출_{a.subject}_색인', '', f'- 원본 {len(idx)} = 단독 배정 {n_single} + 공통 {n_common} + 미분류 {n_un}',
         f'- 그림 있는 문항 {n_fig} (기출그림_{a.subject}.pdf) · 그림 누락(복기에 없음) {n_figmiss}', '',
         '| ' + ' | '.join(IDX_HDR) + ' |', '|' + '---|' * len(IDX_HDR)]
    for r in idx.values():
        L.append('| ' + ' | '.join(c.replace('|', '／') for c in r[:len(IDX_HDR)]) + ' |')
    write(os.path.join(a.out, f'기출_{a.subject}_색인.md'), '\n'.join(L) + '\n')
    figmsg = ''
    if a.figpdf:
        s, e = make_figpdf(fig_items, a.figpdf, a.prev_figpdf, a.subject)
        figmsg = f' · 기출그림 PDF {os.path.basename(a.figpdf)}: ' + (f'{s}~{e}쪽 추가' if fig_items else '추가 없음') + (f' (기존 {s - 1}쪽 유지)' if a.prev_figpdf else '') + f' · 총 {e}쪽'
    # 대조: 주제 파일이 출력 폴더에 있는 문항만 검증한다(--append 때 내려 두지 않은 주제의 문항은 「미검증」)
    verified = {q for q, r in idx.items() if r[3] != '미분류' and all(t in files for t in r[3].split(' · '))}
    unverified = [q for q, r in idx.items() if r[3] != '미분류' and q not in verified]
    tot_assign = sum(1 for blocks in files.values() for q in blocks if q in verified)
    v_single = sum(1 for q in verified if idx[q][4] != '공통'); v_common_slots = sum(len(idx[q][3].split(' · ')) for q in verified if idx[q][4] == '공통')
    print(f'대조 보고{"(누적)" if a.append else ""}: 원본 {len(idx)}문항(ID 기준 · 복기본 여럿은 하나) = 단독 {n_single} + 공통 {n_common} + 미분류 {n_un}'
          + (f' — 이번 배정표 {len(new_ids)}문항' if a.append else ''))
    print(f'주제별 파일 문항 수 합계 {tot_assign} = 단독 {v_single} + 공통 배정 횟수 합 {tot_assign - v_single}  → '
          + ('일치' if tot_assign == v_single + v_common_slots else '불일치 ✗')
          + (f'  (주제 파일을 내려 두지 않아 미검증 {len(unverified)}문항: {", ".join(unverified[:8])}{" …" if len(unverified) > 8 else ""})' if unverified else ''))
    print(f'그림: 있음 {n_fig}문항 · 누락 {n_figmiss}문항' + figmsg)
    print('| 주제 | 문항 | 파일 |'); print('|---|---|---|')
    for t, n, f in made: print(f'| {t} | {n} | {f} |')
    if unassigned: print(f'| 미분류 | {len(unassigned)} | 기출_{a.subject}_미분류.md |')
    for m in fig_missing: print('✗ 그림 파일 없음', m)
    for e in errors: print('✗', e)
    sys.exit(1 if (errors or fig_missing) else 0)


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
    p = sp.add_parser('figs'); p.add_argument('pdf'); p.add_argument('--out', required=True); p.add_argument('--min', type=float, default=40, help='이 크기(pt) 미만의 이미지는 무시')
    p.add_argument('--vec', type=int, default=20, help='벡터 도형이 이 수 이상이면 후보 쪽')
    p = sp.add_parser('pages'); p.add_argument('pdf'); p.add_argument('--out', required=True); p.add_argument('--grid', type=int, default=0); p.add_argument('--dpi', type=int, default=110); p.add_argument('--pages')
    p = sp.add_parser('crop'); p.add_argument('pdf'); p.add_argument('--page', type=int, required=True); p.add_argument('--box', required=True); p.add_argument('--out', required=True)
    p.add_argument('--grid', type=int, default=20); p.add_argument('--dpi', type=int, default=200); p.add_argument('--pad', type=float, default=0.01)
    p = sp.add_parser('assemble'); p.add_argument('--subject', required=True); p.add_argument('--out', required=True); p.add_argument('--index', action='append', required=True); p.add_argument('--text', action='append', required=True)
    p.add_argument('--figs'); p.add_argument('--figpdf'); p.add_argument('--prev-figpdf'); p.add_argument('--append', action='store_true')
    p = sp.add_parser('stems'); p.add_argument('index', nargs='+'); p.add_argument('--text', action='append', required=True); p.add_argument('--out', required=True)
    a = ap.parse_args()
    {'extract': cmd_extract, 'number': cmd_number, 'figs': cmd_figs, 'pages': cmd_pages, 'crop': cmd_crop, 'assemble': cmd_assemble, 'stems': cmd_stems}[a.cmd](a)


if __name__ == '__main__':
    main()
