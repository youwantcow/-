# build_part.py — 생화학 학습자료 빌드 도구 (지침 v1.6)
#
#   빌드:   python3 build_part.py Part.html [Part2.html ...] [--pdf 강의자료.pdf --first 1] [--theme theme.html]
#           · <!DOCTYPE 이 없는 파일(본문만 쓴 파일) → theme.html 로 감싼다 (제목은 첫 <h1>, <!--LEGEND--> 자리에 범례)
#           · --pdf 가 있으면 <img data-page="N"> 자리에 PDF의 N쪽을 JPEG·base64로 삽입한다
#             --first: PDF 파일 1쪽이 원본에서 몇 쪽인지 (범위를 잘라 올린 파일이면 그 시작 쪽번호, 예: p41-80.pdf → 41)
#           · 파일마다 <이름>_core.md (1순위·동일 기출 전문·이해 보조·AI 추정·마무리 발췌)를 함께 만든다 (--no-core 로 생략)
#   병합:   python3 build_part.py --merge 전체.html Part1.html Part2.html ...   (빌드된 파일들을 순서대로 하나로)
#
# theme.html 은 --theme 로 지정하거나, 이 스크립트와 같은 폴더에 둔다.
import argparse, base64, os, re, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--pdf"); ap.add_argument("--first", type=int, default=1)
ap.add_argument("--width", type=int, default=1400); ap.add_argument("--quality", type=int, default=80)
ap.add_argument("--theme"); ap.add_argument("--no-core", action="store_true"); ap.add_argument("--merge")
a = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = a.theme or os.path.join(HERE, "theme.html")

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
def embed(html):  # <img data-page="N"> 에 이미지 삽입. 반환: (html, 삽입 수, 자리표시자 수, 범위 밖 쪽 목록)
    total = n_pages(a.pdf); miss, done = [], [0]
    def sub(m):
        tag, page = m.group(0), int(m.group(1)); fp = page - a.first + 1
        if fp < 1 or fp > total:
            miss.append(page); return tag
        if page not in _cache: _cache[page] = base64.b64encode(render(a.pdf, fp)).decode()
        tag = re.sub(r'\s+src="[^"]*"', "", tag); done[0] += 1
        return tag.replace("<img", f'<img src="data:image/jpeg;base64,{_cache[page]}"', 1)
    pat = r'<img\b[^>]*\bdata-page="(\d+)"[^>]*>'
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
        ("⚠ 확인 필요", lambda e: e.name == "div" and {"box", "flag"} <= set(e.get("class", []))),
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
            out.append("- " + " · ".join(text(x) for x in (qh, st, key) if x))
    end = main.find("section", id="end")
    if end:
        out.append("\n## Part 마무리 (인출 연습 · 혼동 쌍 · 암기 주문 후보 · 확인 필요 목록)")
        for child in end.children:
            if getattr(child, "name", None) == "h2": continue
            if getattr(child, "name", None) in ("h3", "h4") and "커버리지" in text(child): break
            s = md(child).strip()
            if s: out.append(s + "\n")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"

# ---------- 병합 ----------
def inner_main(html):
    m = re.search(r"<main>(.*?)</main>", html, re.S)
    return m.group(1).strip() if m else html

if a.merge:
    t, legend = theme_parts(); bodies = []
    for i, f in enumerate(a.files):
        b = inner_main(read(f))
        if i: b = b.replace(legend, "")  # 범례는 첫 Part 것만
        bodies.append(b)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", bodies[0], re.S)
    title = (re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "학습자료") + " (전체)"
    write(a.merge, t.replace("<!--TITLE-->", title, 1).replace("<!--PART-->", "\n\n<hr>\n\n".join(bodies), 1))
    print(f"병합 완료: {len(a.files)}개 → {a.merge} ({os.path.getsize(a.merge)/1e6:.1f} MB)")
    sys.exit(0)

for f in a.files:
    html = read(f); note = []
    if "<!DOCTYPE" not in html[:200]:
        html = wrap(html); note.append("theme 적용")
    if a.pdf:
        html, done, n, miss = embed(html)
        note.append(f"이미지 {done}/{n} 삽입(PDF {n_pages(a.pdf)}쪽, 파일 1쪽 = 원본 p.{a.first})")
        if miss: note.append(f"범위 밖: {miss}")
    write(f, html)
    if not a.no_core:
        cp = re.sub(r"\.html?$", "", f) + "_core.md"; write(cp, core(html)); note.append(f"core → {os.path.basename(cp)}")
    print(f"{os.path.basename(f)}: " + " · ".join(note) + f" · {os.path.getsize(f)/1e6:.1f} MB")
