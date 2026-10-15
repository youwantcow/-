#!/usr/bin/env python3
"""note_kit.py — 요약·핵심 개념 노트 = 학습팩 (지침 v2.2 `노트` · 7-4)

Univ AI 웹앱의 「AI 요약」(SummaryService.generateSummary)과 「핵심 개념」(ConceptService.extractConceptsFromUrl)을
이 프로젝트에 옮긴 것. 근거는 `분석_UnivAI_요약_핵심개념.md`. 원본(강의자료 PDF)이 아니라 **완성된 Part 파일**을 재료로 한다 —
Part에는 라벨(1순위 · 기출 · 표기)이 이미 붙어 있으므로, 노트는 새 사실을 만들지 않고 그 근거를 따라 다시 묶는다.
v2.2: 같은 JSON 한 번으로 「학습팩」 전부를 만든다(Univ AI가 문서 하나에서 요약·개념·퀴즈·플래시카드·마인드맵을 따로 생성하는 것을
한 번의 작성 + 스크립트 파생으로 바꾼 것 — 근거 `분석_UnivAI_퀴즈_플래시카드_마인드맵_유니.md`).
  · 마인드맵 = 요약 절 × 개념 쪽 범위로 스크립트가 그린다(정적 SVG — 추가 작성 없음). 개념 사이 연결은 JSON `links`(선택)
  · 플래시카드 = 핵심 개념 카드 그대로(theme v2.2의 「카드 복습」이 상자 5개 간격 반복으로 넘겨 준다 — 추가 작성 없음)
  · 퀴즈 = JSON `quiz`(개념 하나에 묶인 문항 · 선지별 해설 · 근거). 보기를 누르면 채점되고, 틀리면 그 개념 카드로 간다
v2.3: `sheet` — 복습 프로젝트 `압축`의 기계 초안(복습 지침 v1.9). Part core에서 ① · ② · ⑤를 그대로 뽑고, Claude는 검토와
③ 혼동 쌍 · ④ 통암기만 쓴다(근거 `검토_일괄생성·비교·간소화·토큰.md` S2). scan · build · check · extract 의 결과는 v2.2와 같다.
v2.4: `sheet --pairs` — ③ 자리에 Part core 「혼동 쌍」 표를 강의 단위로 모은 후보 표(같은 쌍 이름은 한 줄 + 출처 Part)를 넣는다.
`--pairs` 없이 돌린 sheet 와 다른 명령의 결과는 v2.3과 같다.

  scan    Part.html … [--pages 16-37] [--out work/[강의명]/노트_재료.md]
          이미지를 뗀 Part에서 쪽 순서대로 「재료」를 뽑는다(Univ AI의 extractPDFText 자리): 본문 · 박스(라벨) · 기출(발문·선지·답) ·
          표. 인용할 수 있는 id(쪽 [p.N] · 1순위 박스 [#e3] · 기출 카드 [#q24-1-17])를 함께 적는다. Claude는 이 파일만 읽고 노트 JSON을 쓴다.
          끝에 「재료: …」 한 줄. 120,000자를 넘으면 범위를 나누라고 알리고 나눌 곳을 제안한다(Univ AI의 대형 문서 안내 자리).
  build   노트.json --parts Part.html … [--out …_노트.html] [--pdf 강의자료.pdf --first 1] [--theme theme.html]
          JSON 검사 → 본문 HTML → build_part.py(테마 · 그림 · core). 검사(아래)에 걸리면 파일을 쓰지 않고 종료 코드 1.
            ✕ 오류: 끊긴 인용(없는 쪽·id · 범위 밖 · 여러 Part에 있는 id) · 1순위 박스 누락 · 개념에 제목/정의/쪽 없음 ·
                    개념 50개 초과 · LaTeX · 요점 없는 절 · 퀴즈(없는 개념 · 답이 선지 밖 · 해설/근거 없음 · 30문항 초과) ·
                    연결(없는 개념 · 관계/근거 없음 · 20개 초과)
            △ 조정·경고: 같은 개념 중복(앞의 것만 남김) · 근거보다 높은 중요도(낮춤) · 동일 교수 기출 미인용 · 상세도보다 많은 요점 ·
                    같은 발문 중복(뒤의 것 버림) · 퀴즈가 안 다룬 핵심 개념 · 선지 수와 선지별 해설 수 불일치
  check   노트.html Part.html …     노트를 만든 뒤 Part 본문이 바뀌었는지(이미지를 뗀 본문의 지문 비교 — 이미지 삽입은 변경이 아님)
  extract 노트.html [--out 노트.json]   노트 HTML 안에 넣어 둔 JSON을 꺼낸다(다른 채팅에서 `노트 추가`·`노트 수정`)
  sheet   Part_core.md … [--note 노트_core.md …] [--pairs] [--out work/out/압축_초안_[강의명].md]
          한 강의의 Part core(build_part.py 의 `…_core.md`)에서 압축 시트 초안을 만든다(복습 프로젝트 `압축`).
            ① 「## 1순위」 박스마다 제목 · 쪽 · 한 줄 결론 · 첫 인용 · 기출 연계 — [출제 언급]·[반복 출제]는 전부(개수 = Part core
               박스 수, 하나도 빼거나 합치지 않음), [자세히 설명]은 참고 한 줄씩. 「한 줄 결론:」이 없는 박스는 ✎ 로 남기고 알린다
            ② 동일 교수 기출 카드마다 ID · 발문 요지 · 답 · 근거 첫 줄 · 〔그림 n〕 · ⚠(정답 재검토). 재출제로 답이 같은 짝은 한 줄.
               비동일 기출은 참고 한 줄씩
            ⑤ [출제 제외 언급] + Part 마무리의 「⚠ 확인 필요 목록」을 종류별로(문장은 core 그대로)
            ③ 혼동 쌍 · ④ 통암기는 ✎ 빈칸(후보 수만 적는다). --note 가 있으면 ⓪ 강의 흐름(요약 절마다 한 줄)을 넣고 ①을 그 절 순서로 묶는다
            --pairs: ③에 후보 표 — Part 마무리 「### 혼동 쌍」의 쌍 표(쌍 · A · B · 기준)는 행 그대로, 비교표(머리 첫 칸이 빈 「속성 × 항목」 표)는
               표 하나를 한 쌍으로 접고(「속성: 값」을 ; 로 잇는다), 쌍 이름이 같은(괄호 · 띄어쓰기 · 대소문자 · A/B 순서 무시) 행은 한 줄로
               묶어 출처 Part를 붙인다. 그 밖의 표 · 표 없는 Part · 노트 core 「핵심」「중요」 개념의 「자주 혼동되는 점」은 후보 줄로만
          강의가 섞였거나 같은 Part가 두 번이면 쓰지 않고 종료 코드 1. 끝에 「압축 초안: …」 한 줄.

노트 JSON 형식은 지침 부록 A-3. 필요한 것: python3 · beautifulsoup4(없으면 pip 로 설치 시도) · 같은 폴더의 build_part.py · theme.html(v2.2).
sheet 는 python3 만 있으면 된다(core 는 글자 파일이다).
"""
import argparse, datetime, hashlib, html as H, json, os, re, subprocess, sys, unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NOTE_V = 1                      # 노트 형식 판 (Univ AI summaryGenerationVersion 자리 — 바뀌면 check 가 구판이라고 알린다)
GUIDE_V = "v2.2"
SIG_V, CHUNK = "sha256-chunks-v2", 4 * 1024 * 1024   # upload_kit.py 와 같은 지문 계산
MAX_CHARS = 120_000             # 재료가 이보다 길면 범위 노트로 나눈다
CC_MIN, CC_MAX, CC_DEF = 5, 50, 15                  # Univ AI 개념 수: 5~50, 기본 15
QZ_MAX, QZ_DEF, LK_MAX = 30, 10, 20                 # 노트 퀴즈 0~30(Univ AI 퀴즈 기본 10) · 개념 연결 최대 20
QTYPE = {"mc": "객관식", "short": "단답"}
CIRC = "①②③④⑤⑥⑦⑧⑨⑩"
POINTS_MAX = {1: 3, 2: 6, 3: 10}
DETAIL = {1: "간결", 2: "표준", 3: "상세"}
STYLE = {"outline": "개조식", "prose": "서술식"}
CDETAIL = {"concise": "간결", "standard": "표준", "deep": "상세"}
IMP = {"high": ("hi", "핵심"), "medium": ("md", "중요"), "low": ("lo", "참고")}
RANK = {"low": 0, "medium": 1, "high": 2}
BOXES = ("p1d", "p1", "skip", "fig", "tbl", "must", "trap", "ai", "flag")   # p1d 를 p1 보다 먼저 본다
MEDIUM_KINDS = {"qdiff", "must", "trap", "tbl", "fig"}
CITE = re.compile(r"\[(?:p\.?\s*(\d+)(?:\s*[-–~]\s*(\d+))?|#([^\]\s]+))\]")
HERE = os.path.dirname(os.path.abspath(__file__))


def read(p): return open(p, encoding="utf-8-sig").read()
def write(p, s):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def _bs():
    try:
        import bs4
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "beautifulsoup4", "--break-system-packages"])
        import bs4
    return bs4


def signature(data):  # upload_kit.signature 와 같은 계산(파일 대신 바이트열)
    h = hashlib.sha256(f"{SIG_V}:{CHUNK}:{len(data)}:".encode())
    for i in range(0, len(data), CHUNK):
        h.update(hashlib.sha256(data[i:i + CHUNK]).digest())
    return f"{SIG_V}_{len(data)}_{h.hexdigest()}"


def main_body(raw):  # 이미지(base64)를 뗀 <main> 안쪽 — 지문과 재료는 이것으로 만든다
    raw = re.sub(r'\ssrc="data:[^"]*"', "", raw)
    m = re.search(r"<main>(.*?)</main>", raw, re.S)
    return (m.group(1) if m else raw).strip()


def T(el): return re.sub(r"\s+", " ", el.get_text(" ")).strip()


def first_num(s):
    m = re.search(r"(\d+)", s or ""); return int(m.group(1)) if m else None


def span(s):  # "16-19" · "p.16–19" · 16 → (16, 19)
    nums = [int(x) for x in re.findall(r"\d+", str(s))]
    if not nums: return None
    return (nums[0], nums[1] if len(nums) > 1 else nums[0])


# ---------- Part 읽기 (scan · build 공용) ----------
def load_parts(files, rng=None):
    bs4 = _bs(); from bs4 import Tag
    inv = {"pages": {}, "ids": {}, "dup": set(), "marked": set(), "parts": [], "items": []}
    for f in files:
        body = main_body(read(f)); base = os.path.basename(f)
        soup = bs4.BeautifulSoup(body, "html.parser")
        h1 = soup.find("h1"); h1t = T(h1) if h1 else base
        pm = re.search(r"Part\s*(\d+[a-z]?)", h1t)
        part = {"file": base, "path": f, "part": pm.group(1) if pm else "?", "title": re.sub(r"\s*[—-]\s*Part.*$", "", h1t),
                "meta": T(soup.find("p", class_="meta")) if soup.find("p", class_="meta") else "",
                "sig": signature(body.encode("utf-8")), "pages": []}
        inv["parts"].append(part)

        def add_id(i, rec):
            if i in inv["ids"] and inv["ids"][i]["file"] != base: inv["dup"].add(i)
            inv["ids"].setdefault(i, rec)

        for sec in soup.find_all("section"):
            if sec.find_parent("section"): continue
            sid = sec.get("id", ""); h2 = sec.find("h2"); stitle = T(h2) if h2 else ""
            page = first_num(T(h2.find(class_="pg"))) if h2 and h2.find(class_="pg") else None
            for ch in sec.children:
                if not isinstance(ch, Tag) or ch.name == "h2": continue
                cls = set(ch.get("class", []))
                it = {"file": base, "part": part["part"], "sec": sid, "stitle": stitle, "page": page, "id": ch.get("id")}
                if ch.name == "figure" and "slide" in cls and "exam" not in cls:
                    img = ch.find("img", attrs={"data-page": True})
                    if img and str(img["data-page"]).isdigit():
                        page = int(img["data-page"]); it["page"] = page
                        if page not in inv["pages"]: inv["pages"][page] = base; part["pages"].append(page)
                        if ch.get("id"): add_id(ch["id"], {"kind": "page", "page": page, "file": base, "label": f"p.{page}"})
                    cap = ch.find("figcaption"); it.update(kind="slide", label="슬라이드", text=T(cap) if cap else "")
                elif ch.name == "div" and "box" in cls:
                    kind = next((k for k in BOXES if k in cls), "box")
                    hd = ch.find(class_="hd"); lb = ch.find(class_="lb")
                    label = T(lb) if lb else ("⚠" if kind == "flag" else "박스")
                    pg = hd.find(class_="pg") if hd else None
                    if pg and first_num(T(pg)): it["page"] = first_num(T(pg))
                    title = T(hd).replace(label, "", 1).strip() if hd else ""
                    if pg: title = title.replace(T(pg), "").strip()
                    rest = [c for c in ch.children if c is not hd]
                    text = " ".join(T(c) if isinstance(c, Tag) else str(c).strip() for c in rest).strip()
                    it.update(kind=kind, label=label, title=title, text=text)
                    if ch.get("id"): add_id(ch["id"], {"kind": kind, "page": it["page"], "file": base, "label": label, "title": title})
                elif ch.name == "div" and "q" in cls:
                    same = "same" in cls; qh = ch.find(class_="qh"); st = ch.find(class_="stem"); key = ch.find(class_="key")
                    opts = [T(li) for li in ch.select("ol.opt > li")]
                    qhp = first_num(re.search(r"대응\s*p\.?\s*(\d+)", T(qh)).group(1)) if qh and re.search(r"대응\s*p\.?\s*(\d+)", T(qh)) else None
                    if qhp: it["page"] = qhp
                    text = (T(qh) if qh else "") + (f" — 발문: {T(st)}" if st else "") + (f" | 선지: {' / '.join(opts)}" if opts else "") + (f" | {T(key)}" if key else "")
                    if ch.find("figure", class_="exam"): text += " | 〔기출 그림〕"
                    it.update(kind="qsame" if same else "qdiff", label="기출(동일)" if same else "기출(비동일·미상)", text=text)
                    if ch.get("id"): add_id(ch["id"], {"kind": it["kind"], "page": it["page"], "file": base, "label": "기출", "title": T(qh) if qh else ""})
                elif ch.name == "div" and "recall" in cls:
                    continue  # 인출 연습은 Part 내용을 다시 묻는 것이라 재료에 넣지 않는다
                elif ch.name in ("p", "ul", "ol", "h3", "h4", "div", "table", "blockquote", "details"):
                    if ch.name == "div" and "big" in cls: continue
                    if ch.find("table"):
                        rows = [" | ".join(T(c) for c in tr.find_all(["th", "td"])) for tr in ch.find_all("tr")]
                        it.update(kind="table", label="표", text=" ⏎ ".join(rows))
                    else:
                        it.update(kind="text", label="소제목" if ch.name in ("h3", "h4") else "본문", text=T(ch))
                else:
                    continue
                if ch.select_one("b.bd, mark.hl, span.hand") and it["page"]: inv["marked"].add(it["page"])
                if not it.get("text") and not it.get("title"): continue
                if rng and (it["page"] is None or not rng[0] <= it["page"] <= rng[1]): continue
                inv["items"].append(it)
    return inv


def part_span(p): return f"p.{min(p['pages'])}–{max(p['pages'])}" if p["pages"] else "쪽 없음"


# ---------- scan ----------
def cmd_scan(a):
    rng = span(a.pages) if a.pages else None
    inv = load_parts(a.files, rng)
    items = inv["items"]
    if not items: print("재료가 비어 있다 — Part 파일과 --pages 범위를 확인할 것"); return 1
    title = inv["parts"][0]["title"]
    out = [f"# 노트 재료 — {title}" + (f" · 범위 p.{rng[0]}–{rng[1]}" if rng else ""),
           f"(note_kit.py scan · {datetime.date.today()} · 노트 JSON은 이 파일만 읽고 쓴다. 인용은 [p.N] · [p.a-b] · [#id] — 아래에 보이는 것만 쓸 수 있다)", ""]
    out.append("| Part | 파일 | 쪽 | 지문(본문) |\n|---|---|---|---|")
    for p in inv["parts"]: out.append(f"| {p['part']} | {p['file']} | {part_span(p)} | {p['sig'][-12:]} |")
    cur = (None, None)
    for it in items:
        if (it["file"], it["sec"]) != cur:
            if it["file"] != cur[0]:
                p = next(p for p in inv["parts"] if p["file"] == it["file"]); out.append(f"\n## Part {p['part']} · {part_span(p)}")
            cur = (it["file"], it["sec"]); out.append(f"\n### §{it['sec']} {it['stitle']}")
        pg = f"[p.{it['page']}]" if it["page"] else "[p.?]"
        idt = f" #{it['id']}" if it.get("id") and it["kind"] != "slide" else ""
        if it["kind"] in ("text", "slide", "table"): head = it["label"]
        elif it["kind"].startswith("q"): head = it["label"] + idt
        else: head = it["label"] + idt + (f" {it['title']}" if it.get("title") else "")
        out.append(f"{pg} {head}" + (f": {it['text']}" if it["text"] else ""))
    md = "\n".join(out) + "\n"
    dst = a.out or os.path.join("work", re.sub(r"[\\/:*?\"<>|]", "_", title), "노트_재료" + (f"_p{rng[0]}-{rng[1]}" if rng else "") + ".md")
    write(dst, md)

    k = lambda *ks: sum(1 for it in items if it["kind"] in ks)
    lab = lambda s: sum(1 for it in items if it["kind"] in ("p1", "p1d") and s in it["label"])
    pages = sorted({it["page"] for it in items if it["page"]})
    print(f"재료: Part {len(inv['parts'])}개 · 쪽 {len(pages)}(p.{pages[0]}–{pages[-1]}) · 섹션 {len({(i['file'], i['sec']) for i in items})} · "
          f"1순위 {k('p1', 'p1d')}(출제 언급 {lab('출제 언급')} · 자세히 설명 {lab('자세히 설명')} · 기타 {k('p1', 'p1d') - lab('출제 언급') - lab('자세히 설명')}) · "
          f"기출 동일 {k('qsame')} · 비동일·미상 {k('qdiff')} · 필수 이해 {k('must')} · 놓치기 쉬운 {k('trap')} · 표 {k('tbl', 'table')} · "
          f"AI 추정 {k('ai')} · ⚠ {k('flag')} · 글자 {len(md):,} → {dst}")
    noid = [it for it in items if it["kind"] in ("p1", "p1d") and not it.get("id")]
    if noid: print(f"  · id 없는 1순위 박스 {len(noid)}개 — 인용은 그 쪽([p.N])으로 센다: " + ", ".join(f"p.{i['page']}" for i in noid[:10]))
    if inv["dup"]: print(f"  · 여러 Part에 같은 id {len(inv['dup'])}개 — 이 id들은 인용하지 말고 쪽으로 인용: {sorted(inv['dup'])[:10]}")
    if len(md) > MAX_CHARS:
        cuts, acc, start = [], 0, None
        per = {}
        for it in items: per[it["file"]] = per.get(it["file"], 0) + len(it["text"]) + 40
        for p in inv["parts"]:
            if not p["pages"]: continue
            if start is None: start = min(p["pages"])
            acc += per.get(p["file"], 0)
            if acc > MAX_CHARS * 0.8: cuts.append(f"p.{start}-{max(p['pages'])}"); acc, start = 0, None
        if start is not None: cuts.append(f"p.{start}-{max(max(p['pages']) for p in inv['parts'] if p['pages'])}")
        print(f"⚠ 재료가 {MAX_CHARS:,}자를 넘는다 — 한 번에 쓰면 뒤쪽이 얕아진다. 범위 노트로 나눌 것: " + " · ".join(f"`노트 {c}`" for c in cuts))
    return 0


# ---------- build ----------
ALLOWED = ("sub", "sup", "b", "i")


def rich(s, ctx):
    s = H.escape(str(s), quote=False)
    for t in ALLOWED: s = s.replace(f"&lt;{t}&gt;", f"<{t}>").replace(f"&lt;/{t}&gt;", f"</{t}>")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = s.replace("[외부 지식]", '<span class="lb in c-flag">외부 지식</span>')
    return CITE.sub(lambda m: link(m, ctx), s)


def link(m, ctx):
    inv = ctx["inv"]
    if m.group(3):
        i = m.group(3); r = inv["ids"].get(i)
        if not r: return m.group(0)
        cls = "ref p1" if r["kind"] in ("p1", "p1d") else "ref q" if r["kind"].startswith("q") else "ref"
        txt = (f"기출 {i[1:] if i.startswith('q') else i}" if r["kind"].startswith("q")
               else f"{r['label']} p.{r['page']}" if r["kind"] in ("p1", "p1d") and r.get("page") else r["label"])
        return f'<a class="{cls}" href="#{H.escape(i)}" data-file="{H.escape(r["file"])}">{H.escape(txt)}</a>'
    a_, b_ = int(m.group(1)), int(m.group(2) or m.group(1))
    t = next((p for p in range(a_, b_ + 1) if p in inv["pages"]), a_)  # 범위면 슬라이드가 있는 첫 쪽으로 (애니메이션 쪽은 마지막 쪽만 들어 있다)
    return f'<a class="ref" href="#pg{t}" data-file="{H.escape(inv["pages"].get(t, ""))}">p.{a_}{"–" + str(b_) if b_ != a_ else ""}</a>'


def cites(s):  # → (쪽 묶음 목록, id 집합). 쪽 묶음은 [p.N] 하나 또는 [p.a-b] 하나
    spans, ids = [], set()
    for m in CITE.finditer(str(s or "")):
        if m.group(3): ids.add(m.group(3))
        else:
            a_, b_ = int(m.group(1)), int(m.group(2) or m.group(1)); spans.append((min(a_, b_), max(a_, b_)))
    return spans, ids


def norm_title(s): return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", s).lower())


def strs(x): return [s.strip() for s in x if isinstance(s, str) and s.strip()] if isinstance(x, list) else []


def validate(note, inv):
    err, warn, adj = [], [], []
    st = note.get("settings") or {}
    S = {"detail": st.get("detail") if st.get("detail") in (1, 2, 3) else 2,
         "style": st.get("style") if st.get("style") in STYLE else "outline",
         "easy": st.get("easy") if isinstance(st.get("easy"), bool) else True,
         "concepts": st.get("concepts") if isinstance(st.get("concepts"), int) else CC_DEF,
         "conceptDetail": st.get("conceptDetail") if st.get("conceptDetail") in CDETAIL else "standard",
         "request": st.get("request") if isinstance(st.get("request"), str) else "",
         "quiz": st.get("quiz") if isinstance(st.get("quiz"), int) and not isinstance(st.get("quiz"), bool) else QZ_DEF}
    if not CC_MIN <= S["concepts"] <= CC_MAX:
        warn.append(f"settings.concepts {S['concepts']} → {max(CC_MIN, min(CC_MAX, S['concepts']))} (5~50)"); S["concepts"] = max(CC_MIN, min(CC_MAX, S["concepts"]))
    rng = span(note["range"]) if note.get("range") else None
    allp, alli = set(), set()

    def check_cites(where, s, extra=None, count=True):
        # 인용 검사. 반환: (인용한 쪽 집합, id 집합). count=False 면 1순위 반영 계산에 넣지 않는다(개념·절의 pages 칸 — 범위 전체를
        # 「인용」으로 치면 그 범위의 id 없는 1순위 박스가 저절로 반영된 것처럼 보이기 때문)
        spans, ids = cites(s)
        if extra: spans.append(extra)
        ps = set()
        for a_, b_ in spans:
            got = [p for p in range(a_, b_ + 1) if p in inv["pages"]]
            lab = f"p.{a_}" + (f"-{b_}" if b_ != a_ else "")
            if not got: err.append(f"{where}: [{lab}] — Part에 그 쪽 슬라이드가 없다(재료 파일의 [p.N]을 쓸 것)")
            elif rng and not (rng[0] <= a_ and b_ <= rng[1]): err.append(f"{where}: [{lab}] — 노트 범위 p.{rng[0]}–{rng[1]} 밖")
            ps.update(range(a_, b_ + 1))
        if count: allp.update(ps); alli.update(ids)
        for i in sorted(ids):
            if i not in inv["ids"]: err.append(f"{where}: [#{i}] — 그런 id가 없다(재료 파일의 #id만 인용)")
            elif i in inv["dup"]: err.append(f"{where}: [#{i}] — 여러 Part에 있는 id라 병합 후 엉뚱한 곳으로 간다. 쪽으로 인용할 것")
            elif rng and inv["ids"][i].get("page") and not rng[0] <= inv["ids"][i]["page"] <= rng[1]: err.append(f"{where}: [#{i}] — 범위 밖")
            elif inv["ids"][i].get("page"): ps.add(inv["ids"][i]["page"])  # 중요도 판정용(그 박스가 있는 쪽)
        if re.search(r"\$[^$\n]+\$|\\(frac|alpha|beta|rightarrow|cdot|times)\b", str(s)): err.append(f"{where}: LaTeX 금지 — <sub>·<sup>·유니코드 기호를 쓸 것")
        return ps, ids

    summary = note.get("summary") if isinstance(note.get("summary"), list) else []
    if not summary: err.append("summary 가 비어 있다")
    out_sum = []
    for n, s in enumerate(summary, 1):
        if not isinstance(s, dict) or not str(s.get("title", "")).strip(): err.append(f"요약 {n}절: title 없음"); continue
        pts = strs(s.get("points"))
        if not pts: err.append(f"요약 {n}절 「{s['title']}」: points 없음"); continue
        if len(pts) > POINTS_MAX[S["detail"]]:
            warn.append(f"요약 {n}절: 요점 {len(pts)}개 > 상세도 {DETAIL[S['detail']]} 기준 {POINTS_MAX[S['detail']]}")
        sp = span(s["pages"]) if s.get("pages") else None
        for f_ in ("title", "easy", "exam"): check_cites(f"요약 {n}절 {f_}", s.get(f_, ""))
        for p in pts: check_cites(f"요약 {n}절 points", p)
        if sp: check_cites(f"요약 {n}절 pages", "", sp, count=False)
        if s.get("figure") is not None and s["figure"] not in inv["pages"]: err.append(f"요약 {n}절 figure {s['figure']} — 그 쪽 슬라이드가 없다")
        if not any(CITE.search(p) for p in pts): err.append(f"요약 {n}절 「{s['title']}」: 출처([p.N]·[#id])가 하나도 없다")
        out_sum.append({**s, "points": pts, "_span": sp})

    nfig = sum(1 for s in out_sum if s.get("figure") is not None)
    if nfig > 6: warn.append(f"요약 그림 {nfig}장 > 6 — 노트는 학습자료의 슬라이드를 대신하지 않는다")
    concepts = note.get("concepts") if isinstance(note.get("concepts"), list) else []
    seen, out_cc, dups = {}, [], []
    noid_p1 = {it["page"] for it in inv["items"] if it["kind"] in ("p1", "p1d") and not it.get("id") and it["page"]}
    for n, c in enumerate(concepts, 1):
        if not isinstance(c, dict) or not str(c.get("title", "")).strip(): err.append(f"개념 {n}: title 없음"); continue
        t = c["title"].strip(); key = norm_title(t)
        if key in seen: dups.append(f"「{t}」(= {seen[key]}번)"); continue
        seen[key] = n
        if not str(c.get("definition", "")).strip(): err.append(f"개념 「{t}」: definition 없음")
        sp = span(c.get("pages")) if c.get("pages") else None
        if not sp: err.append(f"개념 「{t}」: pages(출처 쪽) 없음")
        where = f"개념 「{t}」"
        ps, ids = set(), set()   # ps: 직접 인용한 쪽([p.N] · basis) — pages 칸의 범위는 아래에서 따로 더한다
        for f_ in ("title", "definition", "explanation", "examples", "pitfalls"):
            p_, i_ = check_cites(where, c.get(f_, "")); ps |= p_; ids |= i_
        for kp in strs(c.get("keyPoints")):
            p_, i_ = check_cites(where, kp); ps |= p_; ids |= i_
        basis = strs(c.get("basis"))
        for b in basis:
            p_, i_ = check_cites(where + " basis", b if b.startswith("[") else f"[{b}]"); ps |= p_; ids |= i_
        direct = set(ps)
        if sp:
            p_, _ = check_cites(where + " pages", "", sp, count=False); ps |= p_
        imp = c.get("importance") if c.get("importance") in IMP else None
        if imp is None: warn.append(f"{where}: importance 가 high·medium·low 가 아니다 → low"); imp = "low"
        kinds = {inv["ids"][i]["kind"] for i in ids if i in inv["ids"]}
        allowed = ("high" if kinds & {"p1", "p1d", "qsame"} or direct & noid_p1 else   # id 없는 1순위 박스는 그 쪽 인용으로 근거가 된다
                   "medium" if (kinds & MEDIUM_KINDS or ps & inv["marked"]) else "low")
        if RANK[imp] > RANK[allowed]:
            adj.append(f"「{t}」 {IMP[imp][1]} → {IMP[allowed][1]}"); imp = allowed
        out_cc.append({**c, "title": t, "importance": imp, "keyPoints": strs(c.get("keyPoints")), "basis": basis, "_span": sp})
    if len(out_cc) > CC_MAX: err.append(f"핵심 개념 {len(out_cc)}개 — 최대 {CC_MAX}개(범위를 나눠 노트를 따로 만들 것)")
    if out_cc and len(out_cc) < CC_MIN: warn.append(f"핵심 개념 {len(out_cc)}개 < {CC_MIN} — 자료에서 더 뽑을 게 없으면 그대로 둔다(채우지 않는다)")
    if dups: warn.append(f"중복 개념 {len(dups)}개 제외: " + ", ".join(dups[:8]))

    inr = lambda p: (not rng) or (p is not None and rng[0] <= p <= rng[1])
    p1 = [it for it in inv["items"] if it["kind"] in ("p1", "p1d") and inr(it["page"])]
    miss = [it for it in p1 if not ((it.get("id") and it["id"] in alli) or (not it.get("id") and it["page"] in allp))]
    for it in miss: err.append(f"1순위 누락: {it['label']} {('#' + it['id']) if it.get('id') else ''} p.{it['page']} 「{it.get('title', '')[:40]}」 — 요약이나 개념에서 인용할 것")
    qs = [it for it in inv["items"] if it["kind"] == "qsame" and inr(it["page"])]
    qmiss = [it for it in qs if not (it.get("id") and it["id"] in alli)]
    if qmiss: warn.append(f"동일 교수 기출 미인용 {len(qmiss)}: " + ", ".join("#" + (it.get("id") or "?") for it in qmiss[:12]))

    # ---- 학습팩(v2.2): 개념 연결 · 퀴즈 — 개념 이름은 위에서 남은 개념의 제목과 글자 그대로(정규화 후) 맞아야 한다
    cmap = {norm_title(c["title"]): k for k, c in enumerate(out_cc, 1)}
    links = note.get("links") if isinstance(note.get("links"), list) else []
    out_lk, seen_lk = [], set()
    for n, l in enumerate(links, 1):
        where = f"연결 {n}"
        if not isinstance(l, dict): err.append(f"{where}: 객체가 아니다"); continue
        a_, b_ = cmap.get(norm_title(str(l.get("from", "")))), cmap.get(norm_title(str(l.get("to", ""))))
        if not a_ or not b_: err.append(f"{where}: 「{l.get('from', '')}」→「{l.get('to', '')}」 — 핵심 개념에 없는 이름(개념 title을 글자 그대로)"); continue
        if a_ == b_: err.append(f"{where}: 같은 개념끼리 연결"); continue
        rel = str(l.get("rel", "")).strip()
        if not rel: err.append(f"{where}: rel(관계 한두 마디) 없음"); continue
        basis = strs(l.get("basis"))
        if not basis: err.append(f"{where}: basis(근거 쪽·id) 없음 — 연결도 Part에 있는 관계만"); continue
        for b in basis: check_cites(where + " basis", b if b.startswith("[") else f"[{b}]", count=False)
        if (a_, b_) in seen_lk: warn.append(f"{where}: 같은 연결 중복 — 버림"); continue
        seen_lk.add((a_, b_)); out_lk.append({"a": a_, "b": b_, "rel": rel, "basis": basis})
    if len(out_lk) > LK_MAX: err.append(f"개념 연결 {len(out_lk)}개 — 최대 {LK_MAX}개(지도가 읽히지 않는다)")

    quiz = note.get("quiz") if isinstance(note.get("quiz"), list) else []
    if not 0 <= S["quiz"] <= QZ_MAX: warn.append(f"settings.quiz {S['quiz']} → {max(0, min(QZ_MAX, S['quiz']))} (0~{QZ_MAX})"); S["quiz"] = max(0, min(QZ_MAX, S["quiz"]))
    out_qz, seen_q = [], {}
    for n, q in enumerate(quiz, 1):
        where = f"퀴즈 {n}"
        if not isinstance(q, dict): err.append(f"{where}: 객체가 아니다"); continue
        t = q.get("type") if q.get("type") in QTYPE else ("mc" if q.get("options") else "short")
        stem = str(q.get("stem", "")).strip()
        if not stem: err.append(f"{where}: stem(발문) 없음"); continue
        k = cmap.get(norm_title(str(q.get("concept", ""))))
        if not k: err.append(f"{where}: concept 「{q.get('concept', '')}」 — 핵심 개념에 없는 이름(틀리면 그 개념 카드로 보내야 한다)"); continue
        key = norm_title(stem)
        if key in seen_q: warn.append(f"{where}: 퀴즈 {seen_q[key]}번과 같은 발문 — 버림"); continue
        explain = str(q.get("explain", "")).strip()
        if not explain: err.append(f"{where}: explain(해설) 없음"); continue
        basis = strs(q.get("basis"))
        if not basis: err.append(f"{where}: basis(근거 쪽·id) 없음"); continue
        rec = {"type": t, "stem": stem, "cc": k, "explain": explain, "basis": basis}
        if t == "mc":
            opts = [re.sub(r"^\s*[①-⑩]\s*", "", o) for o in strs(q.get("options"))]
            if not 4 <= len(opts) <= 5: err.append(f"{where}: 객관식 선지 {len(opts)}개 — 4~5개"); continue
            ans = q.get("answer"); ans = ans if isinstance(ans, list) else [ans]
            if not ans or not all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= len(opts) for x in ans):
                err.append(f"{where}: answer {q.get('answer')} — 1~{len(opts)}의 번호(답이 둘이면 [2, 4])"); continue
            why = [re.sub(r"^\s*[①-⑩]\s*", "", w) for w in strs(q.get("why"))]
            if why and len(why) != len(opts): warn.append(f"{where}: 선지 {len(opts)}개인데 선지별 해설 {len(why)}개 — 선지별 해설을 뺐다"); why = []
            rec.update(options=opts, answer=sorted(set(ans)), why=why)
        else:
            a = str(q.get("answer", "")).strip()
            if not a or isinstance(q.get("answer"), (list, dict)): err.append(f"{where}: 단답 answer(글자) 없음"); continue
            rec.update(answer=a, accept=strs(q.get("accept")))
        for f_ in ("stem", "explain"): check_cites(where, q.get(f_, ""), count=False)
        for s_ in rec.get("options", []) + rec.get("why", []): check_cites(where, s_, count=False)
        for b in basis: check_cites(where + " basis", b if b.startswith("[") else f"[{b}]", count=False)
        seen_q[key] = n; out_qz.append(rec)
    if len(out_qz) > QZ_MAX: err.append(f"퀴즈 {len(out_qz)}문항 — 최대 {QZ_MAX}(더 풀 문제는 복습 프로젝트의 `퀴즈`가 만든다)")
    if S["quiz"] and not out_qz and not quiz: warn.append(f"퀴즈 없음(settings.quiz {S['quiz']}) — 노트에 퀴즈 칸이 생기지 않는다")
    elif out_qz and len(out_qz) != S["quiz"]: warn.append(f"퀴즈 {len(out_qz)}문항 ≠ settings.quiz {S['quiz']}")
    hi_cc = [k for k, c in enumerate(out_cc, 1) if c["importance"] == "high"]
    hit = {r["cc"] for r in out_qz}
    if out_qz and set(hi_cc) - hit:
        warn.append(f"퀴즈가 안 다룬 「핵심」 개념 {len(set(hi_cc) - hit)}: " + ", ".join(out_cc[k - 1]["title"] for k in sorted(set(hi_cc) - hit)[:8]))
    stats = {"p1": (len(p1) - len(miss), len(p1)), "q": (len(qs) - len(qmiss), len(qs)), "dups": len(dups), "adj": len(adj),
             "ext": json.dumps(note, ensure_ascii=False).count("[외부 지식]"), "cites": (len(allp), len(alli)),
             "hi_hit": (len(set(hi_cc) & hit), len(hi_cc))}
    return S, rng, out_sum, out_cc, err, warn, adj, stats, out_lk, out_qz


# ---------- 학습팩(v2.2): 마인드맵 · 퀴즈 ----------
def plain(s):  # 인용·서식을 뗀 글자(지도 마디 · 퀴즈 머리에 쓴다)
    s = CITE.sub("", str(s or "")); s = re.sub(r"\*\*|</?(?:sub|sup|b|i)>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def text_w(s, fs): return sum(fs * (1.0 if ord(ch) >= 0x1100 else 0.58) for ch in s)   # 한글·한자 1em · 그 밖 0.58em (어림)


def fit(s, fs, maxw):
    if text_w(s, fs) <= maxw: return s
    while s and text_w(s + "…", fs) > maxw: s = s[:-1]
    return s.rstrip() + "…"


def lines2(s, fs, maxw):  # 두 줄까지 — 둘째 줄이 넘치면 말줄임
    if text_w(s, fs) <= maxw: return [s]
    words, a = s.split(" "), ""
    for i, w in enumerate(words):
        if text_w((a + " " + w).strip(), fs) > maxw:
            if not a: break
            return [a, fit(" ".join(words[i:]), fs, maxw)]
        a = (a + " " + w).strip()
    return [fit(s, fs, maxw)]


def overlap(a, b): return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)


def mindmap(lecture, summ, ccs, links):
    """강의 → 요약 절 → 핵심 개념의 가로 나무(정적 SVG). 개념은 쪽 범위가 가장 많이 겹치는 절에(안 겹치면 가장 가까운 절) 단다.
    links 는 개념 칸 오른쪽의 점선 화살표 + 번호. id 를 쓰지 않는다(병합 때 접두어가 붙어도 깨지지 않게 — 화살촉도 path)."""
    E = H.escape
    groups = {n: [] for n in range(1, len(summ) + 1)}
    for k, c in enumerate(ccs, 1):
        best = None
        for n, s in enumerate(summ, 1):
            if not (c["_span"] and s["_span"]): continue
            ov = overlap(c["_span"], s["_span"])
            dist = 0 if ov else min(abs(c["_span"][0] - s["_span"][1]), abs(s["_span"][0] - c["_span"][1]))
            sc = (-ov, dist, n)
            if best is None or sc < best[0]: best = (sc, n)
        groups[best[1] if best else 1].append(k)
    ROW, GAP, TOP = 30, 10, 14
    XR, WR, XS, WS, XC, WC = 6, 124, 152, 224, 402, 248
    XE = XC + WC
    sl = {n: lines2(plain(s["title"]), 13, WS - 18) for n, s in enumerate(summ, 1)}   # 절 제목은 두 줄까지(굵은 12.5px ≈ 보통 13px 폭)
    y, sy, cy = TOP, {}, {}
    for n in groups:
        ks = groups[n]; rows = max(len(ks), 2 if len(sl[n]) > 1 else 1)
        off = (rows - len(ks)) / 2
        for i, k in enumerate(ks): cy[k] = y + (i + off + .5) * ROW
        sy[n] = y + rows * ROW / 2; y += rows * ROW + GAP
    Hh = y - GAP + TOP
    W = XE + (150 if links else 14)
    ry = (min(sy.values()) + max(sy.values())) / 2 if sy else TOP + 22
    curve = lambda x1, y1, x2, y2: f'M{x1:.0f} {y1:.1f}C{(x1 + x2) / 2:.0f} {y1:.1f} {(x1 + x2) / 2:.0f} {y2:.1f} {x2:.0f} {y2:.1f}'
    o = [f'<svg class="mm-svg" viewBox="0 0 {W} {Hh:.0f}" width="{W}" height="{Hh:.0f}" role="img" aria-label="마인드맵: {E(plain(lecture))}">']
    for n in groups: o.append(f'<path class="mm-e" d="{curve(XR + WR, ry, XS, sy[n])}"/>')
    for n, ks in groups.items():
        for k in ks: o.append(f'<path class="mm-e" d="{curve(XS + WS, sy[n], XC, cy[k])}"/>')
    rl = lines2(plain(lecture), 14, WR - 18)
    o.append(f'<g class="mm-n mm-r"><rect x="{XR}" y="{ry - 24:.1f}" width="{WR}" height="48" rx="10"/>'
             + "".join(f'<text x="{XR + WR / 2:.0f}" y="{ry + (i - (len(rl) - 1) / 2) * 17 + 5:.1f}" text-anchor="middle">{E(t)}</text>' for i, t in enumerate(rl))
             + "</g>")
    for n, s in enumerate(summ, 1):
        t, ls = plain(s["title"]), sl[n]; h = 28 if len(ls) == 1 else 44
        o.append(f'<a href="#nt-s{n}"><g class="mm-n mm-s"><title>{E(t)}</title><rect x="{XS}" y="{sy[n] - h / 2:.1f}" width="{WS}" height="{h}" rx="8"/>'
                 + "".join(f'<text x="{XS + 9}" y="{sy[n] + (i - (len(ls) - 1) / 2) * 16 + 4.4:.1f}">{E(x)}</text>' for i, x in enumerate(ls))
                 + "</g></a>")
    for k, c in enumerate(ccs, 1):
        t = plain(c["title"]); cls, lab = IMP[c["importance"]]
        o.append(f'<a href="#nt-c{k}"><g class="mm-n mm-c {cls}"><title>{E(t)} · {lab}</title><rect x="{XC}" y="{cy[k] - 12:.1f}" width="{WC}" height="24" rx="12"/>'
                 f'<text x="{XC + 12}" y="{cy[k] + 4.3:.1f}">{E(fit(t, 12.5, WC - 22))}</text></g></a>')
    for i, l in enumerate(links, 1):
        ya, yb = cy[l["a"]], cy[l["b"]]
        bx = XE + 26 + min(100, abs(ya - yb) * .45) + (i % 3) * 10   # 멀리 잇는 연결일수록 바깥으로 — 번호 원이 겹치지 않게
        kx = XE + (bx - XE) * .75
        o.append(f'<path class="mm-l" d="M{XE} {ya:.1f}C{bx:.0f} {ya:.1f} {bx:.0f} {yb:.1f} {XE + 6} {yb:.1f}"/>'
                 f'<path class="mm-a" d="M{XE + 1} {yb:.1f}l8 -4.5v9z"/>'
                 f'<g class="mm-k"><circle cx="{kx:.0f}" cy="{(ya + yb) / 2:.1f}" r="8"/>'
                 f'<text x="{kx:.0f}" y="{(ya + yb) / 2 + 3.6:.1f}" text-anchor="middle">{i}</text></g>')
    o.append("</svg>")
    return "".join(o)


def quiz_html(qz, ccs, R):
    o = ['<section id="nt-qz">', f'<h2>퀴즈 <span class="pg">{len(qz)}문항</span></h2>',
         '<p class="why">보기를 누르면(단답은 답을 적고 「확인」) 바로 채점되고 해설이 열린다. 틀렸으면 해설 끝의 개념 카드로 가서 헷갈린 개념을 '
         '확인한다. 위 막대의 「틀린 문제만」으로 다시 풀고, 더 풀 문제는 복습 프로젝트의 `퀴즈`가 이 문항들과 겹치지 않게 만든다. '
         '시험지 모드로 인쇄하면 답이 빠진다.</p>']
    for n, q in enumerate(qz, 1):
        c = ccs[q["cc"] - 1]; cls, lab = IMP[c["importance"]]; ct = H.escape(plain(c["title"]))
        if q["type"] == "mc": data = f' data-ans="{",".join(map(str, q["answer"]))}"'
        else: data = f' data-short="{H.escape(json.dumps([q["answer"]] + q["accept"], ensure_ascii=False))}"'
        o.append(f'<div class="q nq" id="nt-q{n}"{data}>')
        o.append(f'  <div class="qh">{n} / {len(qz)} · {QTYPE[q["type"]]}<span>개념: {ct} · {lab}</span></div>')
        o.append(f'  <div class="qb">\n    <p class="stem">{n}. {R(q["stem"])}</p>')
        if q["type"] == "mc": o.append('    <ol class="opt">' + "".join(f"<li>{CIRC[i]} {R(x)}</li>" for i, x in enumerate(q["options"])) + "</ol>")
        o.append("  </div>")
        key = (", ".join(CIRC[i - 1] for i in q["answer"]) if q["type"] == "mc"
               else H.escape(q["answer"]) + (f" (인정: {H.escape(' · '.join(q['accept']))})" if q["accept"] else ""))
        o.append(f'  <details class="ans"><summary>답 · 해설 보기</summary>\n    <p><span class="key">답: {key}</span></p>')
        o.append(f'    <h4>해설</h4>\n    <p>{R(q["explain"])}</p>')
        if q.get("why"):
            o.append('    <ul class="optx">' + "".join(f'<li{" class=\"ok\"" if i + 1 in q["answer"] else ""}>{CIRC[i]} {R(w)}</li>'
                                                    for i, w in enumerate(q["why"])) + "</ul>")
        bas = " ".join(R(b if b.startswith("[") else f"[{b}]") for b in q["basis"])
        o.append(f'    <p class="why">헷갈리면 → <a href="#nt-c{q["cc"]}">개념 카드: {ct}</a> · 근거: {bas}</p>\n  </details>\n</div>')
    o.append("</section>")
    return o


def render(note, inv, S, rng, summ, ccs, sigs, links=(), qz=()):
    ctx = {"inv": inv}; R = lambda s: rich(s, ctx)
    parts = inv["parts"]; lecture = note.get("lecture") or parts[0]["title"]
    allpages = sorted(inv["pages"]); a_, b_ = (rng if rng else (allpages[0], allpages[-1]) if allpages else (0, 0))
    meta = " · ".join(x for x in [note.get("subject", ""), note.get("professor", ""),
                                  f"강의자료 p.{a_}–{b_}" + (" (범위 노트)" if rng else ""),
                                  "Part " + ", ".join(p["part"] for p in parts) + " 기준", f"제작 {datetime.date.today()}", f"지침 {GUIDE_V}",
                                  f"노트 설정: 상세도 {DETAIL[S['detail']]} · {STYLE[S['style']]} · 쉬운 설명 {'포함' if S['easy'] else '없음'} · "
                                  f"개념 {len(ccs)}개({CDETAIL[S['conceptDetail']]})"] if x)
    o = [f"<!-- note v{NOTE_V} · parts: " + " ; ".join(f"{p['file']}={sigs[p['file']]}" for p in parts) + f" · made {datetime.date.today()} -->",
         f"<h1>{H.escape(lecture)} — 요약·핵심 개념 노트{f' (p.{rng[0]}–{rng[1]})' if rng else ''}</h1>",
         f'<p class="meta">{H.escape(meta)}</p>', "<!--LEGEND-->", "", '<div class="big">']
    if note.get("overview"): o.append(f"  <p><strong>이 강의가 답하는 질문:</strong> {R(note['overview'])}</p>")
    o.append("  <p>모든 요점 끝의 쪽·박스 표시를 누르면 학습자료의 그 자리로 간다. 핵심 개념의 중요도는 근거로만 정한다 — "
             '<span class="imp hi">핵심</span> 1순위 박스·동일 교수 기출 · <span class="imp md">중요</span> 강의자료 표기·비동일 기출·이해 보조 · '
             '<span class="imp lo">참고</span> 그 밖. 「모두 접기」를 누르면 개념 이름만 남아 보지 않고 떠올려 볼 수 있고, 위 막대의 '
             '「카드 복습」은 핵심 개념을 플래시카드로 한 장씩 넘겨 준다(모름·애매·앎 — 다음 복습일을 이 기기에 기억한다).</p>')
    if S["request"]: o.append(f"  <p><strong>이 노트의 요청:</strong> {H.escape(S['request'])}</p>")
    o += ["</div>", ""]
    if summ and ccs:
        o += ['<section id="nt-map">', f'<h2>마인드맵 <span class="pg">절 {len(summ)} · 개념 {len(ccs)}' + (f' · 연결 {len(links)}' if links else "") + "</span></h2>",
              '<p class="why">강의 → 요약 절 → 핵심 개념. 개념 색은 중요도(빨강 핵심 · 초록 중요 · 회색 참고)이고, 누르면 그 절·개념으로 간다.'
              + (" 오른쪽 점선 화살표는 개념 사이의 연결이다(번호 = 아래 목록)." if links else "") + "</p>",
              f'<div class="mm">{mindmap(note.get("lecture") or parts[0]["title"], summ, ccs, links)}</div>']
        if links:
            o.append('<ol class="mm-links">' + "".join(
                f'<li><a href="#nt-c{l["a"]}">{H.escape(plain(ccs[l["a"] - 1]["title"]))}</a> → <a href="#nt-c{l["b"]}">{H.escape(plain(ccs[l["b"] - 1]["title"]))}</a>'
                f' : {R(l["rel"])} ' + " ".join(R(b if b.startswith("[") else f"[{b}]") for b in l["basis"]) + "</li>" for l in links) + "</ol>")
        o += ["</section>", ""]
    o += ['<section id="nt-sum">', f'<h2>요약 <span class="pg">p.{a_}–{b_}</span></h2>']
    for n, s in enumerate(summ, 1):
        sp = s["_span"]
        pg = f' <a class="pg" href="#pg{sp[0]}" data-file="{H.escape(inv["pages"].get(sp[0], ""))}">p.{sp[0]}{"–" + str(sp[1]) if sp[1] != sp[0] else ""}</a>' if sp else ""
        o.append(f'<div class="ns" id="nt-s{n}">\n  <h3>{R(s["title"])}{pg}</h3>')
        if isinstance(s.get("figure"), int) and s["figure"] in inv["pages"]:
            o.append(f'  <figure class="slide"><img data-page="{s["figure"]}" alt="강의자료 p.{s["figure"]}" decoding="async">'
                     f'<figcaption>강의자료 p.{s["figure"]}</figcaption></figure>')
        if S["style"] == "outline": o.append("  <ul>" + "".join(f"<li>{R(p)}</li>" for p in s["points"]) + "</ul>")
        else: o.append("  <p>" + " ".join(R(p) for p in s["points"]) + "</p>")
        if S["easy"] and str(s.get("easy", "")).strip(): o.append(f'  <p class="easy"><strong>쉽게 말하면</strong> {R(s["easy"])}</p>')
        if str(s.get("exam", "")).strip(): o.append(f'  <p class="exam"><strong>시험에서는</strong> {R(s["exam"])}</p>')  # 글자로 넣는다 — core에도 남게
        o.append("</div>")
    o.append("</section>")
    if ccs:
        o += ["", '<section id="nt-cc">', f'<h2>핵심 개념 <span class="pg">{len(ccs)}개</span></h2>',
              '<div class="tw"><table class="cc-idx"><thead><tr><th>개념</th><th>중요도</th><th>쪽</th><th>근거</th></tr></thead><tbody>']
        for n, c in enumerate(ccs, 1):
            sp = c["_span"]; cls, lab = IMP[c["importance"]]
            bas = " ".join(R(b if b.startswith("[") else f"[{b}]") for b in c["basis"]) or "—"
            o.append(f'<tr><th><a href="#nt-c{n}">{R(c["title"])}</a></th><td><span class="imp {cls}">{lab}</span></td>'
                     f'<td>{R(f"[p.{sp[0]}-{sp[1]}]") if sp else "—"}</td><td>{bas}</td></tr>')
        o.append("</tbody></table></div>")
        for n, c in enumerate(ccs, 1):
            sp = c["_span"]; cls, lab = IMP[c["importance"]]
            en = f' <span class="en">{R(c["en"])}</span>' if str(c.get("en", "")).strip() else ""
            o.append(f'<div class="cc {cls}" id="nt-c{n}">\n  <p class="hd"><span class="imp {cls}">{lab}</span>{R(c["title"])}{en}'
                     + (f' {R(f"[p.{sp[0]}-{sp[1]}]")}' if sp else "") + "</p>")
            o.append('  <details class="cb" open><summary>정의 · 설명</summary>')
            o.append(f'  <p><strong>정의</strong> {R(c.get("definition", ""))}</p>')
            if S["conceptDetail"] != "concise" and str(c.get("explanation", "")).strip(): o.append(f'  <p><strong>설명</strong> {R(c["explanation"])}</p>')
            if c["keyPoints"]: o.append('  <ul class="kp">' + "".join(f"<li>{R(k)}</li>" for k in c["keyPoints"]) + "</ul>")
            if S["conceptDetail"] == "deep" and str(c.get("examples", "")).strip(): o.append(f'  <p><strong>예시</strong> {R(c["examples"])}</p>')
            if S["conceptDetail"] != "concise" and str(c.get("pitfalls", "")).strip(): o.append(f'  <p class="pit"><strong>자주 혼동되는 점</strong> {R(c["pitfalls"])}</p>')
            if c["basis"]: o.append('  <p class="basis">근거: ' + " · ".join(R(b if b.startswith("[") else f"[{b}]") for b in c["basis"]) + "</p>")
            o.append("  </details>\n</div>")
        o.append("</section>")
    if qz: o += [""] + quiz_html(qz, ccs, R)
    keep = {k: v for k, v in note.items()}
    o.append('<script type="application/json" id="note-data">' + json.dumps(keep, ensure_ascii=False, indent=1).replace("</", "<\\/") + "</script>")
    return "\n".join(o) + "\n"


def default_out(parts, rng):
    base = re.sub(r"_Part\d+[a-z]?_p[\d\-–]+\.html?$", "", parts[0]["file"])
    if base == parts[0]["file"]: base = re.sub(r"\.html?$", "", base)
    return os.path.join("work", "out", f"{base}_노트" + (f"_p{rng[0]}-{rng[1]}" if rng else "") + ".html")


def cmd_build(a):
    try:
        note = json.loads(read(a.note))
    except Exception as ex:
        print(f"✕ 노트 JSON을 읽을 수 없다: {ex}"); return 1
    if note.get("note") not in (None, NOTE_V): print(f"✕ 노트 형식 판 {note.get('note')} — 이 스크립트는 v{NOTE_V}"); return 1
    inv = load_parts(a.parts)
    S, rng, summ, ccs, err, warn, adj, st, lk, qz = validate(note, inv)
    hi = sum(1 for c in ccs if c["importance"] == "high"); md_ = sum(1 for c in ccs if c["importance"] == "medium")
    print(f"노트 검사: 요약 {len(summ)}절(요점 {sum(len(s['points']) for s in summ)}) · 핵심 개념 {len(ccs)}(핵심 {hi} · 중요 {md_} · 참고 {len(ccs) - hi - md_}) · "
          f"인용 쪽 {st['cites'][0]} · 박스/기출 {st['cites'][1]} · 1순위 반영 {st['p1'][0]}/{st['p1'][1]} · 동일 기출 반영 {st['q'][0]}/{st['q'][1]} · "
          f"중복 제외 {st['dups']} · 중요도 조정 {st['adj']} · [외부 지식] {st['ext']}")
    nmc = sum(1 for q in qz if q["type"] == "mc")
    print(f"학습팩: 마인드맵 절 {len(summ)} · 개념 {len(ccs)} · 연결 {len(lk)} · 플래시카드 {len(ccs)}장(개념 카드) · "
          f"퀴즈 {len(qz)}(객관식 {nmc} · 단답 {len(qz) - nmc}) · 퀴즈가 다룬 핵심 개념 {st['hi_hit'][0]}/{st['hi_hit'][1]}")
    for w in warn: print("  △ " + w)
    if adj: print("  △ 중요도 조정(근거 부족): " + ", ".join(adj[:12]))
    if err:
        for e in err[:40]: print("  ✕ " + e)
        if len(err) > 40: print(f"  ✕ … 외 {len(err) - 40}건")
        print(f"✕ 오류 {len(err)}건 — 노트를 쓰지 않았다. JSON을 고쳐 다시 build 할 것"); return 1
    out = a.out or default_out(inv["parts"], rng)
    write(out, render(note, inv, S, rng, summ, ccs, {p["file"]: p["sig"] for p in inv["parts"]}, lk, qz))
    bp = os.path.join(HERE, "build_part.py")
    if not os.path.exists(bp): print(f"노트 본문 → {out} (build_part.py 가 없어 테마·core 미적용)"); return 0
    cmd = [sys.executable, bp, out] + (["--pdf", a.pdf, "--first", str(a.first)] if a.pdf else []) + (["--theme", a.theme] if a.theme else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    return r.returncode


# ---------- check · extract ----------
def stored(note_html):
    m = re.search(r"<!-- note v(\d+) · parts: (.*?) · made ([\d-]+) -->", note_html)
    if not m: return None
    return int(m.group(1)), dict(x.split("=", 1) for x in m.group(2).split(" ; ") if "=" in x), m.group(3)


def cmd_check(a):
    st = stored(read(a.note))
    if not st: print("✕ 노트 표지(<!-- note v… -->)가 없다 — note_kit.py build 로 만든 노트가 아니다"); return 1
    v, sigs, made = st; changed, same = [], 0
    for f in a.parts:
        b = os.path.basename(f); now = signature(main_body(read(f)).encode("utf-8"))
        if b not in sigs: print(f"? {b}: 노트를 만들 때 쓰지 않은 Part"); changed.append(b)
        elif sigs[b] != now: print(f"✕ {b}: 노트({made}) 이후 본문이 바뀌었다"); changed.append(b)
        else: same += 1
    given = {os.path.basename(f) for f in a.parts}
    for b in sigs:
        if b not in given: print(f"· {b}: 노트에 쓰였지만 이번에 주지 않음(확인 안 함)")
    if v < NOTE_V: print(f"△ 구판 노트(v{v} < v{NOTE_V}) — extract 로 JSON을 꺼내 다시 build 할 것")
    print(f"확인: 같음 {same} · 바뀜/새 Part {len(changed)} → " + ("노트 최신" if not changed and v == NOTE_V else "노트를 다시 build 할 것(바뀐 Part를 scan → JSON 고침 → build)"))
    return 1 if changed else 0


def cmd_extract(a):
    m = re.search(r'<script type="application/json" id="[^"]*note-data">(.*?)</script>', read(a.note), re.S)
    if not m: print("✕ 노트 데이터(<script id=\"note-data\">)가 없다"); return 1
    data = json.loads(m.group(1).replace("<\\/", "</"))
    out = a.out or re.sub(r"\.html?$", "", a.note) + ".json"
    write(out, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"노트 JSON → {out} (요약 {len(data.get('summary') or [])}절 · 개념 {len(data.get('concepts') or [])}개 · "
          f"연결 {len(data.get('links') or [])} · 퀴즈 {len(data.get('quiz') or [])}문항)")
    return 0


# ---------- sheet (v2.3): 압축 시트 기계 초안 — 복습 지침 v1.9 `압축` ----------
# 입력은 build_part.py core() 가 쓴 글자 파일이다: 「## 1순위 — 교수님 강조」 「## 동일 교수 기출 (전문)」 「## [출제 제외 언급]」
# 「## 비동일 교수 기출 (발문·답만)」 「## Part 마무리 …」(### ⚠ 확인 필요 목록 · ### 혼동 쌍 …). 박스 머리는 **[라벨] 제목 쪽** 한 줄,
# 박스 끝에는 (§ 절 제목) 이 붙는다. 옛 판 core(지침 v1.7~)도 같은 모양이다.
SHEET_V = "v2.3"                # --pairs 없는 초안의 판(초안 글자가 v2.3과 같아야 한다)
PAIRS_V = "v2.4"                # --pairs 초안
P1_HEAD = re.compile(r"^\*\*\[(출제 언급|자세히 설명|반복 출제[^\]]*)\]\s*(.*?)\*\*\s*$")
SKIP_HEAD = re.compile(r"^\*\*\[출제 제외 언급\]\s*(.*?)\*\*\s*$")
Q_HEAD = re.compile(r"^\*\*\[([^\]]*?교수님\s*-\s*동일[^\]]*)\]\s*(.*?)\*\*\s*$")
QID = re.compile(r"(?<![\d-])(\d{2}-\d-(?:주[가-힣]?)?\d+)")
OPT = re.compile(r"^\d+\.\s+([①-⑩]|\d\)|[a-e]\)|\([A-E]\))\s*(.*)$")
MARK = re.compile(r"[①-⑩]|(?<![\w(])\d\)|(?<![\w(])[a-e]\)|\([A-E]\)")
STT_NOTE = re.compile(r"〔(?:\?원문|자료):[^〕]*〕")
FLAG_GROUPS = [  # ⑤ 종류 — 위에서부터 맞는 첫 줄. 판정은 항목 앞 40자(라벨 자리)로 한다
    ("C", "정답 재검토 필요", r"정답 재검토"),
    ("E", "복기 오류 의심 · 판독 불가", r"복기|판독"),
    ("A", "범위 · 확인 필요 · 자료 불일치", r"확인 필요|자료 불일치|자료 내 표현|필기"),
    ("B", "교과서와 차이 — 시험은 강의 기준", r"교과서"),
    ("F", "강의록 공백 · 근거 없음 · 쪽 매핑", r"강의록 (?:공백|근거)|녹음 누락|매핑"),
    ("G", "STT · 지시어 · 불명확", r"STT|불명확|지시어"),
    ("D", "외부 지식 — 강의자료 밖(출제 근거로 쓰지 않는다)", r"외부 지식"),
]
FLAG_ORDER = "ABCDEFGH"
QUIET = re.compile(r"영향 없|오류 아님|불일치 아님|플래그는 아니")   # core가 스스로 「영향 없음」이라 적은 항목 → H(그 밖의 기록)


def clip(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) <= n: return s
    cut = s[:n]; sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ,·—–-") + "…"


def cell(s): return re.sub(r"\s+", " ", str(s)).replace("|", "/").strip()   # 표 칸


def first_page(s):
    m = re.search(r"p\.\s?(\d+)", s or ""); return int(m.group(1)) if m else None


PG_TAIL = re.compile(r"p\.\s?\d+(?:\s*[–-]\s*\d+)?(?:\s*[·,]\s*(?:p\.\s?)?\d+(?:\s*[–-]\s*\d+)?)*(?:\s+\S+){0,2}")


def head_split(head):  # 「강조 · 제목 p.14 · p.31 뒤 발언」 → (제목, 쪽). 쪽 꼬리는 끝에서 쪽 모양으로 끝나는 가장 앞 자리
    for m in re.finditer(r"\sp\.\s?\d", head):
        if PG_TAIL.fullmatch(head[m.start() + 1:].strip()): return head[:m.start()].strip(), head[m.start() + 1:].strip()
    return head, ""


def sentences(s):  # 문장 나누기 — 「C.」「2.」「p.」처럼 한 글자·숫자 뒤의 점에서는 끊지 않는다
    out, start = [], 0
    for m in re.finditer(r"[.?!](?=\s)", s):
        tok = re.search(r"(\S+)$", s[start:m.start()])
        if not tok or re.fullmatch(r"[\dA-Za-z]|\d+|\(?[A-Za-z\d]\)?", tok.group(1)): continue
        out.append(s[start:m.end()].strip()); start = m.end()
    if s[start:].strip(): out.append(s[start:].strip())
    return out


def loc_split(text):  # 박스 끝의 「(§ 절 제목 p.a–b)」를 떼어 낸다 → (본문, 절)
    t = text.rstrip(); i = t.rfind("(§ ")
    if i < 0 or not t.endswith(")"): return t, ""
    return t[:i].rstrip(), t[i + 3:-1].strip()


def split_heads(lines, head):  # 머리 줄(head)마다 끊은 박스 목록 — 머리 앞의 줄은 버린다
    out = []
    for ln in lines:
        m = head.match(ln)
        if m: out.append({"m": m, "lines": []})
        elif out: out[-1]["lines"].append(ln)
    return out


def parse_core(path):
    t = read(path).replace("\r\n", "\n"); ls = t.split("\n")
    h1 = ls[0][2:].strip() if ls and ls[0].startswith("# ") else os.path.basename(path)
    c = {"path": path, "file": os.path.basename(path), "h1": h1, "meta": ls[1].strip() if len(ls) > 1 else "", "text": t,
         "note": "요약·핵심 개념 노트" in h1 or "\n## 요약 노트" in t,
         "lecture": re.sub(r"\s*—\s*(?:Part\s*\d.*|요약·핵심 개념 노트.*|core)$", "", h1).strip()}
    pm = re.search(r"Part\s*(\d+)([a-z]?)", h1) or re.search(r"_Part(\d+)([a-z]?)_", c["file"])
    c["part"] = (int(pm.group(1)), pm.group(2)) if pm else None
    c["pname"] = f"{pm.group(1)}{pm.group(2)}" if pm else "?"
    rm = re.search(r"강의자료 p\.\s?(\d+)\s*[–-]\s*(\d+)", c["meta"])
    c["span"] = (int(rm.group(1)), int(rm.group(2))) if rm else None
    c["secs"] = []
    for ln in ls[2:]:
        if ln.startswith("## "): c["secs"].append((ln[3:].strip(), []))
        elif c["secs"]: c["secs"][-1][1].append(ln)
    return c


def sec_lines(c, prefix): return [l for n, b in c["secs"] if n.startswith(prefix) for l in b]


def sub_lines(lines, prefix):  # 「### prefix…」 소절의 줄들
    out, on = [], False
    for l in lines:
        if l.startswith("### "): on = l[4:].strip().startswith(prefix); continue
        if on: out.append(l)
    return out


def p1_items(c):
    out = []
    for b in split_heads(sec_lines(c, "1순위"), P1_HEAD):
        lab, head = b["m"].group(1), b["m"].group(2).strip()
        body, loc = loc_split("\n".join(b["lines"]))
        title, pg = head_split(head)
        lines = body.split("\n")
        concl = next((re.sub(r"^\s*한 줄 결론\s*[:：]\s*", "", l).strip() for l in lines if re.match(r"^\s*한 줄 결론\s*[:：]", l)), "")
        qs = []  # 첫 인용 — 「“★”」「“눈에만 발생 ←★”」 같은 필기 옮김(글자 10자 미만)은 건너뛴다
        for l in lines:
            if not l.strip().startswith("“"): continue
            qm = re.match(r"“([^”]*)”", l.strip())
            qs.append(re.sub(r"\s+", " ", STT_NOTE.sub("", qm.group(1) if qm else l.strip().lstrip("“"))).strip())
        quote = next((q for q in qs if len(re.findall(r"[A-Za-z가-힣]", q)) >= 10), qs[0] if qs else "")
        basis = next((re.sub(r"^\s*(?:판단 )?근거\s*[:：]\s*", "", l).strip() for l in lines if re.match(r"^\s*(?:판단 )?근거\s*[:：]", l)), "")
        links = []
        for lm in re.finditer(r"기출 연계\s*→\s*([^\n]*)", body):
            links += [i for i in QID.findall(lm.group(1)) if i not in links]
        out.append({"part": c["pname"], "label": lab, "kind": "say" if lab == "출제 언급" else "detail" if lab == "자세히 설명" else "rep",
                    "title": title, "pg": pg, "page": first_page(pg) or first_page(loc), "loc": loc, "concl": concl, "quote": quote,
                    "basis": basis, "links": links})
    return out


def derive_ids(rest, init, guess, known):
    """기출 카드 머리(라벨 뒤 글자) → (ID 목록, 확인됨). 머리에 「(YY-R-…)」가 있으면 그것. 없으면 연도·차수·형식·번호로 만든다:
    객관식·문항 → YY-R-NN · 주관식·서술형 → YY-R-주{교수 첫 글자}N(동일) / YY-R-주N(동일 추정) — 같은 강의 core 어딘가에 적힌 ID(known)가
    있으면 그쪽(예: 2025 주관식 34 → 25-1-34). 주관식인데 교수 글자가 머리에 없고 known 에도 없으면 「확인 안 됨」."""
    m = re.search(r"\((\d{2}-\d-[^)\s·,]+)\)", rest)
    if m: return [m.group(1)], True
    m = re.match(r"\s*(\d{4})\s*(\d)\s*차\s*·\s*(객관식|문항|주관식|서술형|단답형)(?:/[^\s(]+)?\s*(?:\(([^)]*)\))?\s*(.*)$", rest)
    if not m: return [], False
    yr, rd, typ, ini = m.group(1)[2:], m.group(2), m.group(3), (m.group(4) or "")[:1]
    segs = [s.strip() for s in m.group(5).split(" · ")]
    sm = re.match(r"^(?:([가-힣]{1,3})\s*)?(\d+)", segs[0]) if segs else None
    if not sm: return [], False
    ini = (sm.group(1) or ini)[:1]
    nums = [int(sm.group(2))]
    for s in segs[1:]:  # 「서술형 박11 · 박12 · 박13」 — 한 카드에 여러 문항
        mm = re.fullmatch(r"[가-힣](\d+)", s)
        if not mm: break
        nums.append(int(mm.group(1)))
    ids, ok = [], True
    for n in nums:
        if typ in ("객관식", "문항"): ids.append(f"{yr}-{rd}-{n:02d}"); continue
        if ini: ids.append(f"{yr}-{rd}-주{ini}{n}"); continue
        cands = [f"{yr}-{rd}-주{n}", f"{yr}-{rd}-주{init}{n}"] if guess else [f"{yr}-{rd}-주{init}{n}", f"{yr}-{rd}-주{n}"]
        hit = next((x for x in cands + [f"{yr}-{rd}-{n:02d}"] if x in known), None)
        ids.append(hit or cands[0]); ok = ok and bool(hit)
    return ids, ok


def nkey(k):  # 선지 표시 맞추기: ③ = 3) = 3
    return str(CIRC.index(k) + 1) if k in CIRC else k.rstrip(")") if re.fullmatch(r"\d\)", k) else k


def gist(s, n=90):  # 발문 요지 — 짧으면 그대로, 길면 첫 문장 앞 + … + 묻는 문장
    s = re.sub(r"\s+", " ", re.sub(r"\s*\(원문 그대로[^)]*\)", "", s)).strip()   # 제작 쪽 메모는 뗀다
    if len(s) <= n: return s
    sents = sentences(s)
    while len(sents) > 1 and re.fullmatch(r"\([^)]*\)\.?|\[[^\]]*\]\.?", sents[-1]):   # 끝의 「(단답형)」「[표: …]」 같은 꼬리는 버린다
        sents.pop()
    if len(sents) > 1 and len(sents[-1]) >= 12: return clip(sents[0], 34) + " … " + clip(sents[-1], n - 30)
    return clip(" ".join(sents), n)


def q_cards(c, known):
    out = []
    for b in split_heads(sec_lines(c, "동일 교수 기출"), Q_HEAD):
        lab, rest = b["m"].group(1), b["m"].group(2).strip()
        pm = re.match(r"\s*(\S+?)\s*교수님", lab); guess = "추정" in lab
        ids, ok = derive_ids(rest, pm.group(1)[0] if pm else "", guess, known)
        body, _ = loc_split("\n".join(b["lines"]))
        ls = body.split("\n")
        stem, opts, ai, fig = [], {}, None, ""
        for k, l in enumerate(ls):
            s = l.strip()
            if s.startswith("〔기출 그림"):
                fm = re.findall(r"(\d+)\s*쪽", s); fig = f"〔그림 {fm[-1]}〕" if fm else "〔그림〕"; continue
            if not s: continue
            if re.match(r"^답\s*·", s): ai = k; break
            om = OPT.match(s)
            if om: opts[nkey(om.group(1))] = om.group(2).strip(); continue
            if s.startswith("####") or s.startswith("**["): break
            if not opts: stem.append(re.sub(r"^\d+\.\s+", "", s))
        ra = re.sub(r"^답\s*·[^→]*→\s*", "", ls[ai].strip()) if ai is not None else ""
        am = re.match(r"^(?:모범\s*답안|답\s*(?:\([^)]*\))?)\s*[:：]?\s*", ra)
        if am: ra = ra[am.end():]
        mm = re.search(r"\s*\((?:[^()]|\([^()]*\))*?기출 파일(?:[^()]|\([^()]*\))*\)", ra)
        main, meta, tail = (ra[:mm.start()], mm.group(0), ra[mm.end():]) if mm else (ra, "", "")
        main = main.strip().rstrip(".")
        if not main and ai is not None:  # 모범 답안 · 답(표) — 답이 다음 줄들에 있다
            seg = []
            for l in ls[ai + 1:]:
                s = l.strip()
                if s.startswith("####") or s.startswith("**["): break
                if s: seg.append(s)
            items = [re.sub(r"^(?:\d+\.|-)\s+", "", s) for s in seg if re.match(r"^(?:\d+\.|-)\s+", s)]
            rows = [[x.strip() for x in s.strip().strip("|").split("|")] for s in seg if s.startswith("|") and not re.fullmatch(r"\|[\s\-:|]+", s)]
            if items: main = " / ".join(clip(re.split(r"[:：]|\s—\s", x, maxsplit=1)[0], 40) for x in items)
            elif len(rows) > 1: main = " · ".join(" ".join(x for x in r if x) for r in rows[1:])
            elif seg: main = seg[0]
        if opts and re.fullmatch(r"(?:\s*(?:[①-⑩]|\d\)|[a-e]\)|\([A-E]\))\s*[,·]?\s*)+", main):
            ks = MARK.findall(main)
            if all(nkey(k) in opts for k in ks): main = " · ".join(f"{k} {clip(opts[nkey(k)], 38)}" for k in ks)
        why = ""
        for k, l in enumerate(ls):
            if l.strip().startswith("#### 근거"):
                nxt = next((x.strip() for x in ls[k + 1:] if x.strip()), "")
                if not nxt.startswith("####"): why = (sentences(re.sub(r"^(?:\d+\.|-)\s+", "", nxt)) or [""])[0]
                break
        reex = []
        for sg in rest.split(" · "):
            if "재출제" in sg:
                reex += [x.group(1) for x in QID.finditer(sg) if not sg[x.end():].startswith("(변형)")]
        same = re.search(r"(\d{2}-\d-(?:주[가-힣]?)?\d+)\s*(?:와|과)\s*같(?:다|은 문항)", ra)
        out.append({"part": c["pname"], "ids": [(i, guess) for i in ids], "ok": ok, "head": rest, "stem": gist(" ".join(stem)),
                    "ans": main, "nokey": bool(re.search(r"정답 (?:표기 )?없음", meta)), "why": why, "fig": fig,
                    "warn": "정답 재검토" in body or "판단 불가" in main, "reex": reex, "same": same.group(1) if same else ""})
    return out


def merge_reexam(cards):
    """재출제로 답이 같은 카드를 앞 카드의 한 줄로 묶는다: 뒤 카드의 답이 「X와 같다 · X과 같은 문항」이거나, 두 카드가 서로를 재출제로 적고
    (변형 제외) 답 글자가 같을 때. 한 문항짜리 카드끼리만 묶는다(문항 수는 그대로 센다)."""
    idx = {i: c for c in cards for i, _ in c["ids"]}
    pos = {id(c): k for k, c in enumerate(cards)}
    letters = lambda s: re.sub(r"[^A-Za-z가-힣]", "", s).lower() or re.sub(r"\s", "", s)
    n = 0
    for c in cards:
        if c.get("into") or len(c["ids"]) != 1: continue
        me = c["ids"][0][0]; o = idx.get(c["same"]) if c["same"] else None
        if o is None:
            o = next((idx[r] for r in c["reex"] if r in idx and me in idx[r]["reex"] and letters(idx[r]["ans"]) == letters(c["ans"])), None)
        if o is None or o is c or o.get("into") or len(o["ids"]) != 1 or o.get("rows"): continue
        a, b = (o, c) if pos[id(o)] < pos[id(c)] else (c, o)
        if b.get("rows"): continue
        a["rows"] = True; a["ids"] = a["ids"] + b["ids"]; a["warn"] = a["warn"] or b["warn"]; a["fig"] = a["fig"] or b["fig"]
        b["into"] = a; n += 1
    return [c for c in cards if not c.get("into")], n


def diff_lines(c, known):  # 「- [출제자 미상] 2022 1차 · 문항 16 · 대응 … · 발문 · 답: ②」
    out = []
    for l in sec_lines(c, "비동일 교수 기출"):
        if not l.startswith("- "): continue
        s = re.sub(r"^\[[^\]]*\]\s*", "", l[2:].strip())
        k = s.rfind(" · 답"); ans = re.sub(r"^[:：\s]+", "", s[k + 4:]) if k >= 0 else ""
        segs = (s[:k] if k >= 0 else s).split(" · ")
        i = 0
        while i < len(segs) and (re.match(r"^\(?(?:\d{4}\s*\d\s*차|문항|객관식|주관식|서술형|단답형|대응|재출제|추정|Part|p\.)", segs[i].strip())
                                 or re.fullmatch(r"\d+(?:\s*[–-]\s*\d+)?", segs[i].strip())): i += 1   # 「대응 p.33 · 37」의 이어진 쪽
        ids, _ = derive_ids(" · ".join(segs[:i]), "", True, known)
        stem = re.sub(r"^\d+\.\s*", "", " · ".join(segs[i:]))
        out.append({"part": c["pname"], "id": " · ".join(ids) or clip(" · ".join(segs[:2]), 20), "stem": gist(stem, 60), "ans": ans})
    return out


def flag_items(c):
    """⑤ 재료: Part 마무리의 「### ⚠ 확인 필요 목록」 항목(줄바꿈 이어 붙임). 없으면 본문의 「⚠ 라벨 …」 문단 첫 문장."""
    items = []
    for l in sub_lines(sec_lines(c, "Part 마무리"), "⚠ 확인 필요"):
        m = re.match(r"^(?:\d+\.|-)\s+(.*)$", l)
        if m: items.append(m.group(1).strip())
        elif items and l.strip() and l.startswith(" "): items[-1] += " " + l.strip()
    src = "목록"
    if not items:
        src = "본문"
        for l in c["text"].split("\n"):
            if l.startswith("⚠ "): items.append(clip(loc_split((sentences(l[2:].strip()) or [""])[0])[0], 160))
    return items, src


def flag_group(s):
    if QUIET.search(s): return "H"
    z = s[:40]
    return next((g for g, _, pat in FLAG_GROUPS if re.search(pat, z)), "H")


def note_flow(n):  # 노트 core 「## 요약 노트」의 절 → ⓪ 강의 흐름
    out = []
    for b in split_heads(sec_lines(n, "요약 노트"), re.compile(r"^###\s+(.*)$")):
        h = b["m"].group(1).strip()
        m = re.search(r"\s(p\.\s?\d+(?:\s*[–-]\s*\d+)?)\s*$", h)
        title, pg = (h[:m.start()].strip(), m.group(1)) if m else (h, "")
        pt = next((l.strip()[2:] for l in b["lines"] if l.strip().startswith("- ")), "")
        pt = re.sub(r"(?:\s+(?:\[[^\]]+\]\s*)?(?:p\.\s?\d+(?:\s*[–-]\s*\d+)?|기출\s+\d{2}-\d-\S+))+\s*$", "", pt)
        out.append({"title": title, "pg": pg, "span": span(pg) if pg else None, "point": pt})
    return out


# ---- ③ 후보 표 (v2.4 --pairs)
NOTHING = ("", "–", "-", "—")
SIDE_JUNK = re.compile(r"[\s\-–—_·,.:;'\"“”‘’/]+")


def md_tables(lines):
    """마크다운 표 → [{"head": 머리 칸, "rows": 행 칸 목록, "read": 「읽는 법:」 첫 문장}]. 빈 줄이 표를 끊는다.
    표 바로 다음 문단이 「읽는 법:」이면 그 첫 문장을 그 표에 붙인다(비교표의 가르는 기준)."""
    tabs, in_tab, after = [], False, False   # after: 마지막 글 있는 줄이 표였다
    for l in lines:
        s = l.strip()
        if s.startswith("|"):
            if not re.fullmatch(r"\|[\s\-:|]+", s):
                cells = [x.strip() for x in (s[1:-1] if len(s) > 1 and s.endswith("|") else s[1:]).split("|")]
                if in_tab: tabs[-1]["rows"].append(cells)
                else: tabs.append({"head": cells, "rows": [], "read": ""})
            in_tab = after = True; continue
        in_tab = False
        if not s: continue
        if after and tabs and s.startswith("읽는 법"):
            tabs[-1]["read"] = (sentences(re.sub(r"^읽는 법\s*[:：]\s*", "", s)) or [""])[0]
        after = False
    return tabs


def pair_rows(c):
    """Part 마무리 「### 혼동 쌍…」 소절의 표 → (쌍 목록, 목록 표). 쌍 표(머리 「쌍|빈칸 · A · B (· 기준)」)는 행마다 한 쌍,
    비교표(머리 첫 칸이 빈 「속성 × 항목」 표)는 표 하나를 한 쌍으로 접는다 — 「속성: 값」을 ; 로 잇고, 첫 항목 칸에만 값이 있는 행(합친 칸)은
    「공통」으로, 표 뒤 「읽는 법:」 첫 문장과 함께 기준 칸에. 셋 이상이면 B 칸에 「항목 — …」을 / 로 잇는다.
    머리 첫 칸에 이름이 있는 그 밖의 표는 목록 표(후보 줄)."""
    pairs, lists = [], []
    for t in md_tables(sub_lines(sec_lines(c, "Part 마무리"), "혼동 쌍")):
        h = t["head"]; w = len(h)
        rows = [(r + [""] * w)[:w] for r in t["rows"] if any(r)]
        if w >= 3 and h[1] == "A" and h[2] == "B":
            pairs += [{"part": c["pname"], "name": r[0], "a": r[1], "b": r[2], "key": r[3] if w > 3 else "", "note": ""} for r in rows]
        elif w >= 3 and not h[0]:
            common = [f"{r[0]}: {r[1]}" for r in rows if r[1] and not any(r[2:])]
            body = [r for r in rows if any(r[2:])]
            side = lambda k: "; ".join(f"{r[0]}: {r[k]}" for r in body if r[k] not in NOTHING)
            b = side(2) if w == 3 else " / ".join(f"{e} — {side(k)}" for k, e in enumerate(h[2:], 2))
            key = " / ".join(x for x in ["공통 — " + "; ".join(common) if common else "", "읽는 법 — " + t["read"] if t["read"] else ""] if x)
            pairs.append({"part": c["pname"], "name": " vs ".join(h[1:]), "a": side(1), "b": b, "key": key, "note": f"비교표 {len(rows)}행"})
        else:
            lists.append({"part": c["pname"], "head": h, "rows": len(rows), "first": [r[0] for r in rows if r[0]]})
    return pairs, lists


def pair_sides(name):  # 쌍 이름 → 정규화한 양쪽(괄호 · 띄어쓰기 · 문장부호 · 대소문자 무시, ↑↓ ′ 같은 기호는 남긴다)
    s = re.sub(r"\([^()]*\)", " ", unicodedata.normalize("NFKC", name).lower())
    return [x for x in (SIDE_JUNK.sub("", y) for y in re.split(r"\s+vs\.?\s+", s)) if x]


def merge_pairs(pairs):
    """쌍 이름이 같은 행(양쪽 집합이 같으면 A/B 순서가 달라도)을 첫 행 자리에 한 줄로. 뒤집힌 행은 A·B를 바꿔 맞추고 출처에 ⇄.
    칸 글이 Part마다 다르면 ‖ 로 잇는다(같은 글은 한 번)."""
    out, idx = [], {}
    for k, p in enumerate(pairs):
        sides = pair_sides(p["name"])
        key = tuple(sorted(sides)) or ("#", k)
        g = idx.get(key)
        if g is None:
            g = idx[key] = {"name": p["name"], "sides": sides, "a": [], "b": [], "key": [], "src": [], "n": 0}; out.append(g)
        flip = len(sides) == 2 and sides != g["sides"]
        g["n"] += 1
        for f, v in (("a", p["b"] if flip else p["a"]), ("b", p["a"] if flip else p["b"]), ("key", p["key"])):
            if v and v not in g[f]: g[f].append(v)
        s = f"P{p['part']}" + ("⇄" if flip else "") + (f" {p['note']}" if p["note"] else "")
        if s not in g["src"]: g["src"].append(s)
    return out


def note_pits(n):  # 노트 core 「## 핵심 개념」 카드의 「자주 혼동되는 점」 → 중요도 · 개념 · 쪽 · 글
    out = []
    for b in split_heads(sec_lines(n, "핵심 개념"), re.compile(r"^###\s+(.*)$")):
        t = next((re.sub(r"^자주 혼동되는 점\s*", "", l).strip() for l in b["lines"] if l.startswith("자주 혼동되는 점")), "")
        if not t: continue
        m = re.match(r"(핵심|중요|참고)\s*(.*)$", b["m"].group(1).strip())
        title, pg = head_split(m.group(2).strip() if m else b["m"].group(1).strip())
        out.append({"imp": m.group(1) if m else "", "title": title, "pg": pg, "text": t})
    return out


def pairs_section(cores, notes):
    """③ 후보 표 단락(줄 목록)과 끝 줄용 수."""
    prs, lists, bare = [], [], []
    for c in cores:
        p, l = pair_rows(c); prs += p; lists += l
        if not p and not l: bare.append(c["pname"])
    groups = merge_pairs(prs)
    npr = sum(1 for p in prs if not p["note"]); ntb = len(prs) - npr
    pits = [x for n in notes for x in note_pits(n)]
    pk = [x for x in pits if x["imp"] in ("핵심", "중요")]
    o = [f"## ③ 혼동 쌍 — 후보 표 (Part core 「혼동 쌍」 쌍 표 {npr}행" + (f" · 비교표 {ntb}개" if ntb else "") + f" → {len(groups)}쌍)", "",
         "> ✎ **후보**다 — Part core 「혼동 쌍」 표를 글자 그대로 모았다(쌍 이름이 같으면 한 줄: ‖ = Part마다 다른 칸 · ⇄ = A·B를 바꿔 맞춤 · "
         "비교표는 「속성: 값」을 ; 로 이어 한 쌍으로 접음). 검토: 고르고 칸 줄이기 · 비슷한 쌍 합치기 · 표에 없는 쌍 더하기(아래 후보 줄 · "
         "표 없는 Part의 본문 · ⑤) — 끝나면 「출처」 열과 이 단락을 지운다.", ""]
    if groups:
        hk = any(g["key"] for g in groups)
        o += ["| 쌍 | A | B |" + (" 기준 |" if hk else "") + " 출처 |", "|---|---|---|" + ("---|" if hk else "") + "---|"]
        for g in groups:
            o.append(f"| {cell(g['name'])} | {cell(' ‖ '.join(g['a']))} | {cell(' ‖ '.join(g['b']))} |"
                     + (f" {cell(' ‖ '.join(g['key']))} |" if hk else "") + f" {cell(' · '.join(g['src']))} |")
        o.append("")
    if bare:
        o += [f"**「혼동 쌍」 표 없는 Part {len(bare)}개**: Part {', '.join(bare)} — 이 Part의 쌍은 본문(1순위 · [필수 이해] · [놓치기 쉬운 포인트])에서 찾는다", ""]
    if lists:
        o.append(f"**쌍 표가 아닌 표 {len(lists)}개 (후보 줄)**")
        o += [f"- P{t['part']} · 「{' · '.join(t['head'])}」 {t['rows']}행: {clip(' · '.join(t['first']), 120)}" for t in lists]
        o.append("")
    if notes:
        o.append(f"**노트 core 「자주 혼동되는 점」 — 「핵심」「중요」 {len(pk)}개 (후보 줄"
                 + (f" · 「참고」 {len(pits) - len(pk)}개는 뺌" if len(pits) > len(pk) else "") + ")**")
        for x in pk:
            z = SIDE_JUNK.sub("", unicodedata.normalize("NFKC", x["text"]).lower())
            hits = [g["name"] for g in groups if len(g["sides"]) >= 2 and all(len(s) >= 2 and s in z for s in g["sides"])]
            o.append(f"- [{x['imp']}] {x['title']}" + (f" ({x['pg']})" if x["pg"] else "") + f" — {x['text']}"
                     + (f" ≈ 표 「{'」 「'.join(hits)}」" if hits else ""))
        o.append("")
    return o, {"rows": npr, "tabs": ntb, "pairs": len(groups), "merged": len(prs) - len(groups), "lists": len(lists),
               "bare": bare, "pits": len(pk)}


def cmd_sheet(a):
    cores = [parse_core(f) for f in a.cores]
    notes = [parse_core(f) for f in (a.note or [])]
    moved = [c for c in cores if c["note"]]; back = [n for n in notes if not n["note"]]   # 자리를 바꿔 준 파일은 알아서 옮긴다
    if moved: print("· 노트 core가 Part core 자리에 있어 --note 로 읽는다: " + ", ".join(c["file"] for c in moved))
    if back: print("· --note 뒤에 Part core가 있어 Part core로 읽는다: " + ", ".join(n["file"] for n in back))
    cores = [c for c in cores if not c["note"]] + back; notes = [n for n in notes if n["note"]] + moved
    err, warn = [], []
    if not cores: err.append("Part core가 없다 — `압축`은 Part core로 만든다(노트 core만으로는 ①의 개수를 맞출 수 없다)")
    if len({norm_title(c["lecture"]) for c in cores}) > 1:
        err.append("강의가 섞였다: " + " / ".join(sorted({c["lecture"] for c in cores})) + " — 압축은 강의 하나씩")
    seen = {}
    for c in cores:
        if c["part"] is None: err.append(f"{c['file']}: Part 번호를 찾지 못했다(첫 줄이 「# … — Part n — core」인 Part core인지)")
        elif c["part"] in seen: err.append(f"Part {c['pname']}이 두 번: {seen[c['part']]} · {c['file']}")
        else: seen[c["part"]] = c["file"]
    if err:
        for e in err: print("✕ " + e)
        print(f"✕ 오류 {len(err)}건 — 초안을 쓰지 않았다"); return 1
    cores.sort(key=lambda c: c["part"])
    nums = {c["part"][0] for c in cores}
    gaps = [n for n in range(1, max(nums) + 1) if n not in nums]
    if gaps: warn.append(f"Part {', '.join(map(str, gaps))} core가 없다 — ①②의 개수는 받은 Part 기준이다(강의 전체가 아니다)")
    for n in notes:
        if norm_title(n["lecture"]) != norm_title(cores[0]["lecture"]): warn.append(f"노트 core 「{n['lecture']}」 ≠ Part core 「{cores[0]['lecture']}」 — 같은 강의인지 확인")

    known = {i for c in cores + notes for i in QID.findall(c["text"])}   # core·노트에 적힌 기출 ID — 머리에 ID가 없는 카드의 ID 확인용
    p1 = [it for c in cores for it in p1_items(c)]
    for c in cores:  # 1순위 절 밖에 같은 라벨 박스가 있으면(core 형식이 바뀐 경우) 알린다 — 개수는 1순위 절 기준
        raw = len(re.findall(r"^\*\*\[(?:출제 언급|반복 출제[^\]]*)\]", c["text"], re.M))
        got = sum(1 for it in p1 if it["part"] == c["pname"] and it["kind"] != "detail")
        if raw != got: warn.append(f"Part {c['pname']}: 「## 1순위」 절 밖에 [출제 언급]·[반복 출제] 머리 {raw - got}개 — core를 직접 확인")
    say = [it for it in p1 if it["kind"] != "detail"]; det = [it for it in p1 if it["kind"] == "detail"]
    nrep = sum(1 for it in say if it["kind"] == "rep")
    cards = [q for c in cores for q in q_cards(c, known)]
    allq = [i for q in cards for i, _ in q["ids"]]
    rows, nmerge = merge_reexam([dict(q) for q in cards])
    diffs = [d for c in cores for d in diff_lines(c, known)]
    skips = []
    for c in cores:
        for b in split_heads(sec_lines(c, "[출제 제외 언급]"), SKIP_HEAD):
            _, loc = loc_split("\n".join(b["lines"]))
            skips.append({"part": c["pname"], "title": b["m"].group(1).strip(), "loc": loc})
    flags, fsrc = [], {}
    for c in cores:
        its, src = flag_items(c); fsrc[c["pname"]] = src
        flags += [{"part": c["pname"], "text": t, "g": flag_group(t)} for t in its]
    flow = [f for n in notes for f in note_flow(n)]

    # ---- 쓰기
    lec = cores[0]["lecture"]; meta = [x.strip() for x in cores[0]["meta"].split(" · ")]
    subj = meta[0] if meta else ""
    prof = next((x for x in meta if "교수님" in x), ""); week = next((x for x in meta if "주차" in x), "")
    spans = [c["span"] for c in cores if c["span"]]
    rng = f"p.{min(s[0] for s in spans)}–{max(s[1] for s in spans)}" if spans else "쪽 범위 미상"
    plist = ", ".join(c["pname"] for c in cores)
    years = {}
    for i in allq: years[i[:4]] = years.get(i[:4], 0) + 1
    ytxt = " · ".join(f"{y} {n}" for y, n in sorted(years.items()))
    o = [f"# 압축 초안 — {subj} · {lec}".replace("—  ·", "—"),
         " · ".join(x for x in [prof, week, f"**반영 범위: {rng} (Part {plist} core {len(cores)}개"
                                + (f" + 노트 core {len(notes)}개" if notes else "") + ")**", f"초안 {datetime.date.today()}",
                                f"note_kit.py sheet {PAIRS_V} --pairs" if a.pairs else f"note_kit.py sheet {SHEET_V}"] if x), "",
         f"**[출제 언급] {len(say) - nrep}건 · [반복 출제] {nrep}건** (Part core 박스 {len(say)} = 초안 {len(say)}) · "
         f"참고 [자세히 설명] {len(det)}건 · [출제 제외 언급] {len(skips)}건 · 동일 교수 기출 {len(allq)}문항"
         + (f"({ytxt})" if ytxt else "") + (f" · 비동일 {len(diffs)}문항" if diffs else ""), "",
         "> **초안**: ①②⑤는 Part core에서 스크립트가 그대로 옮긴 것이다(요약·합치기 없음). 검토할 것 — ✎ 칸 채우기 · ① 개수가 Part core 박스 수와 "
         "같은지 · ② 같은 문항 묶음과 「근거」 칸 · ⑤에서 이미 풀린 항목 지우기 · "
         + ("③ 후보 표 다듬기 · " if a.pairs else "③ 혼동 쌍 · ") + "④ 통암기 쓰기 · (선택) 시험장 규칙 한 단락(03 출제 프로필 + ② 형식). "
         "끝나면 이 인용 단락을 지우고 제목의 「초안」을 뗀다.", "", "---", ""]
    if flow:
        o += [f"## ⓪ 강의 흐름 (노트 core 요약 {len(flow)}절)", ""]
        o += [f"- **{f['title']}**" + (f" ({f['pg']})" if f["pg"] else "") + (f" — {clip(f['point'], 80)}" if f["point"] else "") for f in flow]
        o += ["", "---", ""]

    def p1_line(n, it):
        pg = it["pg"]
        if not pg:
            lm = re.search(r"p\.\s?\d+(?:\s*[–-]\s*\d+)?", it["loc"]); pg = (lm.group(0) + " 절") if lm else ""
        lab = f"[{it['label']}] " if it["kind"] == "rep" else ""
        s = f"{n}. **{lab}{it['title']}**" + (f" ({pg})" if pg else "") + " — "
        s += it["concl"] or f"✎ 한 줄 결론 없음 — Part {it['part']} core의 이 박스에서 한 줄"
        s += (f" 인용: “{clip(it['quote'], 90)}”" if it["quote"] else
              f" (인용 없음 — 근거: {clip(it['basis'], 70)})" if it["basis"] else " (인용 없음)")
        return s + (f" → {' · '.join(it['links'])}" if it["links"] else "")

    o += [f"## ① 1순위 — [출제 언급] {len(say) - nrep}건 · [반복 출제] {nrep}건", ""]
    # 묶음 [시작 쪽, 제목, 항목, 쪽 범위] — 노트가 있으면 요약 절(쪽 범위에 든 항목)로, 절 밖이거나 노트가 없으면 Part로. 쪽 순서로 놓는다
    fgs = [[f["span"][0], f"{f['title']} ({f['pg']})", [], f["span"]] for f in flow if f["span"]]
    pgs, part_of = {}, {c["pname"]: c for c in cores}
    for it in say:
        g = next((x for x in fgs if it["page"] and x[3][0] <= it["page"] <= x[3][1]), None)
        if g is None:
            sp = part_of[it["part"]]["span"]
            g = pgs.setdefault(it["part"], [sp[0] if sp else 0, f"Part {it['part']}" + (f" · p.{sp[0]}–{sp[1]}" if sp else ""), [], sp])
            if fgs and it["page"]: g[0] = min(g[0] if g[2] else it["page"], it["page"])   # 노트가 있으면 절 사이 쪽 순서로
        g[2].append(it)
    groups = sorted([g for g in fgs + list(pgs.values()) if g[2]], key=lambda g: g[0])
    n = 0
    for _, title, its, _ in groups:
        o.append(f"**{title}**")
        for it in its: n += 1; o.append(p1_line(n, it))
        o.append("")
    if det:
        o.append(f"**참고 · [자세히 설명] {len(det)}건 (한 줄씩)**")
        for it in det:
            o.append(f"- {it['pg'] or 'p.?'} **{it['title']}** — " + (it["concl"] or f"✎ 한 줄 결론 없음 — Part {it['part']} core의 이 박스에서 한 줄"))
        o.append("")
    o += ["---", "", "## ② 동일 교수 기출 — 발문 요지 → 답 → 근거", "",
          f"({len(cards)}카드 = {len(allq)}문항 · 「추정」 = 동일(추정), 동일로 다룬다 · ⚠ = 카드에 정답 재검토 · 「표기 없음」 = 기출 파일에 정답이 없어 자료로 푼 답"
          + (f" · 재출제로 답이 같은 {nmerge}쌍은 한 줄" if nmerge else "") + ")", ""]
    for c in cores:
        rs = [r for r in rows if r["part"] == c["pname"]]
        if not rs: continue
        o += [f"**Part {c['pname']}" + (f" · p.{c['span'][0]}–{c['span'][1]}" if c["span"] else "") + "**", "",
              "| ID | 발문 요지 | 답 | 근거 |", "|---|---|---|---|"]
        for r in rs:
            idt = " · ".join(i + (" (추정)" if g else "") for i, g in r["ids"]) or clip(r["head"], 24)
            ans = (r["ans"] or "✎ 답 줄 없음") + (" · 표기 없음" if r["nokey"] else "") + (" ⚠" if r["warn"] else "")
            o.append(f"| {cell(idt)} | {cell((r['fig'] + ' ' if r['fig'] else '') + r['stem'])} | {cell(clip(ans, 110))} | {cell(clip(r['why'], 80)) or '—'} |")
        o.append("")
    if diffs:
        o.append(f"참고 · 비동일(출제자 미상) 기출 {len(diffs)}문항(답만)")
        o += [f"- {d['id']} {d['stem']} → {d['ans']}" for d in diffs]
        o.append("")
    cp = sum(max(0, len([l for l in sub_lines(sec_lines(c, "Part 마무리"), "혼동 쌍") if l.startswith("|")]) - 2) for c in cores)
    mn = len(re.findall(r"^\*\*\[암기 주문 후보\]", "\n".join(c["text"] for c in cores), re.M))
    pit = sum(len(re.findall(r"^자주 혼동되는 점", n["text"], re.M)) for n in notes)
    if a.pairs: p3, ps = pairs_section(cores, notes)
    else: p3 = ["## ③ 혼동 쌍", "", f"✎ Claude가 쓴다 — 후보: Part core 「혼동 쌍」 표 {cp}행"
                + (f" · 노트 core 「자주 혼동되는 점」 {pit}개(「핵심」「중요」 개념 것)" if notes else "") + ". 같은 쌍은 하나로(표: 쌍 · A · B).", ""]
    o += ["---", ""] + p3 + [
          "---", "", "## ④ 통암기 목록", "", f"✎ Claude가 쓴다 — 숫자 · 목록 · 암기 주문(후보: Part core [암기 주문 후보] {mn}개"
          + (" · 노트 「핵심」 개념의 핵심 포인트 — 문장은 Part core에서 확인한 것으로" if notes else "") + ").", "", "---", ""]
    o += [f"## ⑤ ⚠ 미해결 플래그 (Part core 「⚠ 확인 필요 목록」 {len(flags)}항목 · [출제 제외 언급] {len(skips)}건)", ""]
    names = {g: t for g, t, _ in FLAG_GROUPS}; names["H"] = "그 밖의 기록(core가 영향 없음·해결이라고 적은 것 포함)"
    for g in FLAG_ORDER:
        fs = [f for f in flags if f["g"] == g]
        if not fs and not (g == "A" and skips): continue
        o.append(f"**{g}. {names[g]}**")
        if g == "A":
            o += [f"- P{s['part']} · [출제 제외 언급] {s['title']}" + (f" (§ {clip(s['loc'], 40)})" if s["loc"] else "") for s in skips]
        o += [f"- P{f['part']} · " + (clip(f["text"], 160) if g in "DH" else f["text"]) for f in fs]
        o.append("")
    md = "\n".join(o).rstrip() + "\n"
    out = a.out or os.path.join("work", "out", "압축_초안_" + re.sub(r"[\\/:*?\"<>|\s]+", "_", lec).strip("_") + ".md")
    write(out, md)

    nc = sum(1 for it in say if it["concl"]); ndc = sum(1 for it in det if it["concl"])
    print(f"압축 초안: Part core {len(cores)}개(Part {plist} · {rng})" + (f" + 노트 core {len(notes)}개(⓪ {len(flow)}절)" if notes else "")
          + f" · ① [출제 언급] {len(say) - nrep} · [반복 출제] {nrep} · 한 줄 결론 {nc}/{len(say)} · 참고 [자세히 설명] {len(det)}(결론 {ndc}/{len(det)})"
          f" · ② 동일 기출 {len(cards)}카드 = {len(allq)}문항" + (f"({ytxt})" if ytxt else "") + f" → 표 {len(rows)}행(재출제 묶음 {nmerge})"
          f" · 비동일 {len(diffs)} · ⑤ ⚠ {len(flags)} + 제외 언급 {len(skips)} · "
          + (f"③ 후보 {ps['pairs']}쌍(쌍 표 {ps['rows']}행" + (f" + 비교표 {ps['tabs']}" if ps["tabs"] else "") + f" · 같은 쌍 묶음 {ps['merged']})"
             + (f" + 후보 줄(목록 표 {ps['lists']}" + (f" · 노트 {ps['pits']}" if notes else "") + ")" if ps["lists"] or notes else "")
             + " · ④ ✎" if a.pairs else "③④ ✎") + f" · 글자 {len(md):,} → {out}")
    if a.pairs and ps["bare"]: print(f"  · Part {', '.join(ps['bare'])}: 「혼동 쌍」 표가 없다 — 이 Part의 쌍은 검토 때 본문에서")
    miss = [it for it in p1 if not it["concl"]]
    if miss:
        print(f"  ✎ 한 줄 결론 없는 1순위 {len(miss)}건 — 초안에 ✎로 남겼다(검토 때 그 박스에서 한 줄): "
              + " · ".join(f"Part {it['part']} [{it['label']}] {clip(it['title'], 30)} {it['pg']}".rstrip() for it in miss))
    unk = [i for q in cards if not q["ok"] for i, _ in q["ids"]]
    if unk: print(f"  · 머리 글자로 만든 ID {len(unk)}개(core 다른 곳에서 확인 못 함 — 기출 파일 표기와 맞는지 볼 것): " + ", ".join(unk))
    noans = [q for q in cards if not q["ans"]]
    if noans: print(f"  △ 답 줄을 못 찾은 카드 {len(noans)}: " + ", ".join(clip(q["head"], 30) for q in noans))
    body = [p for p, s in fsrc.items() if s == "본문"]
    if body: print(f"  · Part {', '.join(body)}: 「⚠ 확인 필요 목록」이 없어 본문 ⚠ 문단 첫 문장으로 채웠다")
    for w in warn: print("  △ " + w)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="요약·핵심 개념 노트 = 학습팩 (Univ AI 요약·핵심 개념·퀴즈·플래시카드·마인드맵 이식)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan"); p.add_argument("files", nargs="+"); p.add_argument("--pages"); p.add_argument("--out")
    p = sub.add_parser("build"); p.add_argument("note"); p.add_argument("--parts", nargs="+", required=True); p.add_argument("--out")
    p.add_argument("--pdf"); p.add_argument("--first", type=int, default=1); p.add_argument("--theme")
    p = sub.add_parser("check"); p.add_argument("note"); p.add_argument("parts", nargs="+")
    p = sub.add_parser("extract"); p.add_argument("note"); p.add_argument("--out")
    p = sub.add_parser("sheet"); p.add_argument("cores", nargs="*"); p.add_argument("--note", nargs="+"); p.add_argument("--out")
    p.add_argument("--pairs", action="store_true", help="③에 Part core 「혼동 쌍」 표의 후보 표를 넣는다(v2.4)")
    a = ap.parse_args()
    sys.exit({"scan": cmd_scan, "build": cmd_build, "check": cmd_check, "extract": cmd_extract, "sheet": cmd_sheet}[a.cmd](a))
