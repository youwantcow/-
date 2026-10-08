# build_part.py — 학습자료 빌드 도구 (지침 v1.9)
#
#   빌드:   python3 build_part.py Part.html [Part2.html ...] [--pdf 강의자료.pdf --first 1] [--figs 기출그림_과목.pdf] [--theme theme.html]
#           · <!DOCTYPE 이 없는 파일(본문만 쓴 파일) → theme.html 로 감싼다 (제목은 첫 <h1>, <!--LEGEND--> 자리에 범례)
#           · --pdf 가 있으면 <img data-page="N"> 자리에 강의자료 PDF의 N쪽을 JPEG·base64로 삽입한다
#             --first: PDF 파일 1쪽이 원본에서 몇 쪽인지 (범위를 잘라 올린 파일이면 그 시작 쪽번호, 예: p41-80.pdf → 41)
#           · --figs 가 있으면 <img data-fig="N"> 자리에 기출그림 PDF의 N쪽(= 기출 파일의 〔그림 N〕)을 삽입한다 (--first 무관, 1쪽부터)
#           · 파일마다 <이름>_core.md (1순위·동일 기출 전문·이해 보조·AI 추정·마무리 발췌)를 함께 만든다 (--no-core 로 생략)
#   병합:   python3 build_part.py --merge 전체.html Part1.html Part2.html ...   (빌드된 파일들을 순서대로 하나로)
#           · Part마다 id와 그 id를 가리키는 #링크에 p<Part번호>- 접두어를 붙여 병합 후 링크가 다른 Part로 튀지 않게 한다
#           · 다른 Part의 id를 가리키는 링크(예: Part 3 본문의 "Part 2 · 12절")는 그 id가 있는 Part의 접두어로 바꾼다
#             (같은 id가 여러 Part에 있으면 앞쪽에서 가장 가까운 Part로 잇고, 검사 줄에 그 id를 알린다)
#           · 끝에 「중복 id · 끊긴 링크 · 이미지 n/n · Part 간 링크 n」 검사 결과를 출력한다
#
# theme.html 은 --theme 로 지정하거나, 이 스크립트와 같은 폴더에 둔다.
import argparse, base64, os, re, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--pdf"); ap.add_argument("--first", type=int, default=1)
ap.add_argument("--figs", help="기출그림 PDF (<img data-fig=\"N\"> 에 N쪽을 삽입)")
ap.add_argument("--width", type=int, default=1400); ap.add_argument("--quality", type=int, default=80)
ap.add_argument("--theme"); ap.add_argument("--no-core", action="store_true"); ap.add_argument("--merge")
a = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = a.theme or os.path.join(HERE, "theme.html")
IMG_ANY = r'<img\b[^>]*\bdata-(?:page|fig)="\d+"[^>]*>'

def read(p): return open(p, encoding="utf-8").read()
def write(p, s): open(p, "w", encoding="utf-8").write(s)

def theme_parts():
    if not os.path.exists(THEME):
        sys.exit(f"theme.html 을 찾을 수 없다: {THEME} (--theme 로 경로를 주거나 스크립트 옆에 둘 것)")
    t = read(THEME)
    m = re.search(r"<template id=\"legend\">\s*(.*?)\s*</template>", t, re.S)
    if not m or "<!--PART-->" not in t or "<!--TITLE-->" not in t:
        sys.exit("theme.html 형식 오류: <!--TITLE-->, <!--PART-->, <template id=\"legend\"> 가 있어야 한다")
    return t, m.group(1)

def wrap(body):  # 본문만 있는 HTML → 완성 문서
    t, legend = theme_parts()
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "학습자료"
    if "<!--LEGEND-->" in body:
        body = body.replace("<!--LEGEND-->", legend, 1)
    else:  # 범례 자리를 안 적었으면 meta 문단 뒤(없으면 h1 뒤, 그것도 없으면 맨 앞)에 넣는다
        m = re.search(r'<p class="meta">.*?</p>', body, re.S) or h1
        body = (body[:m.end()] + "\n\n" + legend + "\n" + body[m.end():]) if m else legend + "\n" + body
    return t.replace("<!--TITLE-->", title, 1).replace("<!--PART-->", body.strip(), 1)

def n_pages(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out); return int(m.group(1)) if m else 0

def render(pdf, file_page):  # 파일 기준 쪽번호(1부터) → JPEG bytes
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", f"quality={a.quality}", "-scale-to-x", str(a.width),
                        "-scale-to-y", "-1", "-f", str(file_page), "-l", str(file_page), pdf, os.path.join(d, "pg")], check=True)
        fs = [f for f in os.listdir(d) if f.endswith(".jpg")]
        if not fs: raise RuntimeError(f"{file_page}쪽 렌더 실패")
        return open(os.path.join(d, fs[0]), "rb").read()

_cache = {}
def embed(html, attr, pdf, first):  # <img data-page|data-fig="N"> 에 이미지 삽입. 반환: (html, 삽입 수, 자리표시자 수, 범위 밖 쪽 목록)
    total = n_pages(pdf); miss, done = [], [0]
    def sub(m):
        tag, page = m.group(0), int(m.group(1)); fp = page - first + 1
        if fp < 1 or fp > total:
            miss.append(page); return tag
        key = (pdf, page)
        if key not in _cache: _cache[key] = base64.b64encode(render(pdf, fp)).decode()
        tag = re.sub(r'\s+src="[^"]*"', "", tag); done[0] += 1
        return tag.replace("<img", f'<img src="data:image/jpeg;base64,{_cache[key]}"', 1)
    pat = r'<img\b[^>]*\b' + attr + r'="(\d+)"[^>]*>'
    n = len(re.findall(pat, html)); html = re.sub(pat, sub, html)
    return html, done[0], n, sorted(set(miss))

# ---------- core.md 추출 ----------
def _bs():
    try:
        import bs4
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "beautifulsoup4", "--break-system-packages"])
        import bs4
    return bs4

def md(el):  # 요소 → 마크다운 비슷한 텍스트
    from bs4 import NavigableString, Tag
    if isinstance(el, NavigableString): return str(el)
    if not isinstance(el, Tag): return ""
    n, cls = el.name, el.get("class", [])
    if n == "figure" and "exam" in cls:  # 기출 그림: 그림이 있다는 사실만 남긴다(복습에서 그림 문항임을 알 수 있게)
        cap = el.find("figcaption"); return "\n〔기출 그림: " + (text(cap) if cap else "") + "〕\n"
    if n in ("figure", "img", "script", "style", "template") or "cover" in cls: return ""
    if n == "br": return "\n"
    if n in ("h2", "h3", "h4"): return "\n" + "#" * int(n[1]) + " " + text(el) + "\n"
    if n == "p" and "hd" in cls: return "\n**" + text(el) + "**\n"
    if n == "div" and "qh" in cls: return "\n**" + text(el) + "**\n"
    if n == "p": return "\n" + "".join(md(c) for c in el.children).strip() + "\n"
    if n in ("ul", "ol"):
        out = "\n"
        for i, li in enumerate([c for c in el.children if isinstance(c, Tag) and c.name == "li"], 1):
            body = re.sub(r"\n\s*\n", "\n", "".join(md(c) for c in li.children)).strip()
            out += (f"{i}. " if n == "ol" else "- ") + body.replace("\n", "\n   ") + "\n"
        return out
    if n == "table":
        rows = [[text(c) for c in tr.find_all(["th", "td"])] for tr in el.find_all("tr")]
        if not rows: return ""
        w = max(len(r) for r in rows); rows = [r + [""] * (w - len(r)) for r in rows]
        head = "| " + " | ".join(rows[0]) + " |"; sep = "|" + "---|" * w
        return "\n" + "\n".join([head, sep] + [("| " + " | ".join(r) + " |") for r in rows[1:]]) + "\n"
    if n == "details":
        s = el.find("summary"); body = "".join(md(c) for c in el.children if c is not s).strip()
        return "\n" + (text(s) + " → " if s else "") + body + "\n"
    if n == "summary": return ""
    return "".join(md(c) for c in el.children)

def text(el): return re.sub(r"[ \t]+", " ", el.get_text("")).strip()

def core(html):
    _bs(); from bs4 import BeautifulSoup
    html = re.sub(r'src="data:[^"]*"', "", html)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    for sp in main.select("span.pg, span.lb, .qh > span, .box > .hd > .lb"):
        sp.insert_before(" "); sp.insert_after(" ")
    out = []; taken = []
    h1 = main.find("h1"); meta = main.find("p", class_="meta")
    out.append("# " + (text(h1) if h1 else "학습자료") + " — core")
    if meta: out.append(text(meta))
    out.append("(build_part.py 가 학습자료 HTML에서 기계적으로 추린 발췌. 압축·퀴즈·변형·안키의 입력용.)")
    groups = [
        ("1순위 — 교수님 강조", lambda e: e.name == "div" and "box" in e.get("class", []) and ({"p1", "p1d"} & set(e.get("class", [])))),
        ("동일 교수 기출 (전문)", lambda e: e.name == "div" and {"q", "same"} <= set(e.get("class", []))),
        ("이해 보조 — [필수 이해] · [놓치기 쉬운 포인트]", lambda e: e.name == "div" and "box" in e.get("class", []) and ({"must", "trap"} & set(e.get("class", [])))),
        ("AI 추정 — [예상 출제 포인트] · [누락 출제 포인트] (점선)", lambda e: e.name == "div" and {"box", "ai"} <= set(e.get("class", []))),
        ("[출제 제외 언급]", lambda e: e.name == "div" and {"box", "skip"} <= set(e.get("class", []))),
        ("[표 해설]", lambda e: e.name == "div" and {"box", "tbl"} <= set(e.get("class", []))),
        ("⚠ 확인 필요 (본문 자리의 플래그)", lambda e: e.name == "div" and {"box", "flag"} <= set(e.get("class", []))),
    ]
    for title, pred in groups:
        els = [e for e in main.find_all("div") if pred(e) and not any(p in taken for p in e.parents)]
        if not els: continue
        taken += els
        out.append("\n## " + title)
        for e in els:
            sec = e.find_previous("h2"); loc = f" (§ {text(sec)})" if sec else ""
            out.append(md(e).strip() + loc + "\n")
    diff = [e for e in main.find_all("div") if e.name == "div" and {"q", "diff"} <= set(e.get("class", []))]
    if diff:
        out.append("\n## 비동일 교수 기출 (발문·답만)")
        for e in diff:
            qh, st, key = e.find(class_="qh"), e.find(class_="stem"), e.find(class_="key")
            fig = e.find("figure", class_="exam")
            out.append("- " + " · ".join(text(x) for x in (qh, st, key) if x) + (" · 〔기출 그림〕" if fig else ""))
    end = main.find("section", id="end")
    if end:
        out.append("\n## Part 마무리 (인출 연습 · 혼동 쌍 · 암기 주문 후보)")
        for child in end.children:
            if getattr(child, "name", None) == "h2": continue
            if getattr(child, "name", None) in ("h3", "h4") and "커버리지" in text(child): break  # 구판(v1.8) 파일의 커버리지 보고는 뺀다
            s = md(child).strip()
            if s: out.append(s + "\n")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"

# ---------- 병합 ----------
def inner_main(html):
    m = re.search(r"<main>(.*?)</main>", html, re.S)
    return m.group(1).strip() if m else html

def prefix_ids(body, pre, parts, i, xref):
    # Part 안의 id에 접두어(p3-)를 붙이고, #링크는 가리키는 id가 있는 Part의 접두어로 바꾼다 — 병합 후 id 충돌·Part 간 링크 끊김 방지
    #   parts: [(접두어, 그 Part의 id 집합), …] (병합 순서), i: 지금 Part의 순번, xref: Part 간 링크 집계용 dict
    own = parts[i][1]
    def target(h):
        if h in own: return pre + h                           # 1) 같은 Part 안
        hits = [j for j, (_, ids) in enumerate(parts) if h in ids]
        if not hits: return h                                 # 3) 어디에도 없음 → 그대로(검사에서 끊긴 링크로 보고)
        if len(hits) > 1: xref["모호"].append(h)
        prev = [j for j in hits if j < i]                     # 2) 다른 Part — 여럿이면 앞쪽에서 가장 가까운 Part, 없으면 뒤쪽 첫 Part
        j = prev[-1] if prev else hits[0]
        xref["n"] += 1
        return parts[j][0] + h
    body = re.sub(r'(\sid=")([^"]+)"', lambda m: m.group(1) + pre + m.group(2) + '"', body)
    body = re.sub(r'(href="#)([^"]+)"', lambda m: m.group(1) + target(m.group(2)) + '"', body)
    return body

def img_counts(body):
    tags = re.findall(IMG_ANY, body)
    return len(tags), sum(1 for t in tags if 'src="data:image' in t)

if a.merge:
    t, legend = theme_parts(); raw = []
    for i, f in enumerate(a.files):
        b = inner_main(read(f))
        if i: b = b.replace(legend, "")  # 범례는 첫 Part 것만
        pm = re.search(r"Part\s*(\d+[a-z]?)", re.search(r"<h1[^>]*>(.*?)</h1>", b, re.S).group(1)) if re.search(r"<h1", b) else None
        raw.append((b, f"p{pm.group(1) if pm else i + 1}-"))
    parts = [(pre, set(re.findall(r'\sid="([^"]+)"', b))) for b, pre in raw]  # 1차: Part별 id 수집
    xref = {"n": 0, "모호": []}
    bodies = [prefix_ids(b, pre, parts, i, xref) for i, (b, pre) in enumerate(raw)]  # 2차: 접두어 적용
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", bodies[0], re.S)
    title = (re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "학습자료") + " (전체)"
    write(a.merge, t.replace("<!--TITLE-->", title, 1).replace("<!--PART-->", "\n\n<hr>\n\n".join(bodies), 1))
    out = read(a.merge); body = inner_main(out)
    ids = re.findall(r'\sid="([^"]+)"', body); dup = sorted({x for x in ids if ids.count(x) > 1})
    broken = sorted({h for h in re.findall(r'href="#([^"]+)"', body) if h not in set(ids)})
    imgs, filled = img_counts(body)
    print(f"병합 완료: {len(a.files)}개 → {a.merge} ({os.path.getsize(a.merge)/1e6:.1f} MB)")
    amb = sorted(set(xref["모호"]))
    print(f"  검사: 중복 id {len(dup)}{' ' + str(dup[:10]) if dup else ''} · 끊긴 링크 {len(broken)}{' ' + str(broken[:10]) if broken else ''} · 이미지 {filled}/{imgs}"
          f" · Part 간 링크 {xref['n']}{' (대상 id가 여러 Part에 있음 → 앞쪽 가장 가까운 Part로 연결: ' + str(amb[:10]) + ')' if amb else ''}")
    sys.exit(0)

for f in a.files:
    html = read(f); note = []
    if "<!DOCTYPE" not in html[:200]:
        html = wrap(html); note.append("theme 적용")
    if a.pdf:
        html, done, n, miss = embed(html, "data-page", a.pdf, a.first)
        note.append(f"이미지 {done}/{n} 삽입(PDF {n_pages(a.pdf)}쪽, 파일 1쪽 = 원본 p.{a.first})")
        if miss: note.append(f"범위 밖: {miss}")
    if a.figs:
        html, done, n, miss = embed(html, "data-fig", a.figs, 1)
        note.append(f"기출 그림 {done}/{n} 삽입(기출그림 PDF {n_pages(a.figs)}쪽)")
        if miss: note.append(f"기출그림 범위 밖: {miss}")
    write(f, html)
    if not a.no_core:
        cp = re.sub(r"\.html?$", "", f) + "_core.md"; write(cp, core(html)); note.append(f"core → {os.path.basename(cp)}")
    print(f"{os.path.basename(f)}: " + " · ".join(note) + f" · {os.path.getsize(f)/1e6:.1f} MB")
