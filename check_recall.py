#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_recall.py v1.0 · 지침 v2.9 — recall_kit.py가 만든 인출 노트를 원본 HTML과 대조한다.

  python3 check_recall.py 전체.html OUT/분자생물학 --lecture Intro1-1 --pages 38

① 링크: 노트 · 머리글 · PDF 쪽 · 그림 파일이 실제로 있는가
② 본문 대조: 옮기기로 한 재료의 글자 조각이 노트에 전부 있는가(새로 만든 사실이 없는지는 반대로 본다 — ③)
③ 노트에만 있는 글자: 질문 틀로 덧붙인 문장 말고 원본에 없는 줄이 있는가
④ 카드 모양: 빈 줄이 낀 카드 · 뜻하지 않은 :: · ;; · 태그 없는 노트의 카드
"""
import argparse
import os
import re
import sys
import unicodedata

from bs4 import BeautifulSoup, NavigableString

FRAMES = ["요지", "정의는", "요점", "가지는", "자주 혼동되는 점은", "한 줄 결론과 그 이유는", "시험에서는 어떻게 묻나", "무엇을 조심하라는 거지",
          "어떤 모양으로 나올 수 있지", "흐름을 처음부터 끝까지 말해 봐", "앞뒤 Part와 어떻게 이어지나", "절", "개를 순서대로 말해 봐", "주제", "부제",
          "방향 사슬", "첫 칸에서 끝까지 이어 봐", "이 강의는 Part", "개로 간다", "각 Part가 답하는 질문을 순서대로 말해 봐", "사슬을 이어 봐",
          "표로 보기", "번째 줄", "번째 칸", "빈칸", "함정", "기출", "변형 예측", "AI 추정", "퀴즈", "원 기출", "답", "해설", "근거",
          "떠올린 뒤 열기", "첫 칸만 보고 나머지를 말해 봐", "빈칸 인출", "강의자료", "열기", "이 쪽은 글 없이 그림만 있어"]


def alnum(s):
    return "".join(ch for ch in unicodedata.normalize("NFKC", s) if unicodedata.category(ch)[0] in "LN")


def md_plain(md):
    md = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    md = re.sub(r"!\[\[[^\]]*\]\]", "", md)
    md = re.sub(r"\[\[[^\]|\\]*(?:\\?\|([^\]]*))?\]\]", lambda m: m.group(1) or "", md)
    md = md.replace("\\<", "\ue020")
    return re.sub(r"<[^>]+>", "", md).replace("\ue020", "<")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("root")
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--pages", type=int, required=True)
    a = ap.parse_args()
    bad = 0
    notes, files = {}, set()
    for dp, _, fns in os.walk(a.root):
        for fn in fns:
            files.add(fn)
            if fn.endswith(".md"):
                notes[fn[:-3]] = open(os.path.join(dp, fn), encoding="utf-8").read()
    lec = {k: v for k, v in notes.items() if k.startswith(a.lecture)}
    heads = {k: [h.strip() for h in re.findall(r"^#{1,6} (.+)$", v, flags=re.M)] for k, v in notes.items()}

    # ① 링크
    n = dict(link=0, pdf=0, img=0, head=0, note=0)
    for k, v in lec.items():
        for m in re.finditer(r"(!?)\[\[([^\]]+?)\]\]", v):
            n["link"] += 1
            target = re.split(r"\\?\|", m.group(2))[0]
            fpart, _, sub = target.partition("#")
            if m.group(1):
                n["img"] += 1
                if fpart not in files:
                    bad += 1
                    print(f"✕ 그림 없음 — {k}: {fpart}")
            elif fpart.endswith(".pdf"):
                n["pdf"] += 1
                pm = re.fullmatch(r"page=(\d+)", sub) if sub else None
                if fpart not in files or (sub and (not pm or not 1 <= int(pm.group(1)) <= a.pages)):
                    bad += 1
                    print(f"✕ PDF 링크 — {k}: {target}")
            elif fpart in files:
                n["note"] += 1
            elif fpart not in notes:
                bad += 1
                print(f"✕ 노트 없음 — {k}: {fpart}")
            elif sub:
                n["head"] += 1
                if sub not in heads[fpart]:
                    bad += 1
                    print(f"✕ 머리글 없음 — {k}: {target}")
                elif heads[fpart].count(sub) > 1:
                    bad += 1
                    print(f"✕ 링크 대상 머리글이 둘 — {k}: {target}")
            else:
                n["note"] += 1
    print(f"링크 {n['link']}: PDF 쪽 {n['pdf']} · 머리글 {n['head']} · 노트 {n['note']} · 그림 {n['img']}")

    # ② 원본 → 노트
    soup = BeautifulSoup(re.sub(r'src="data:image/[^"]+"', 'src=""', open(a.html, encoding="utf-8").read()), "html.parser")
    main_el = soup.find("main") or soup
    drop = lambda sel: [e.decompose() for e in main_el.select(sel)]
    for sel in ("h1", "script", "style", "p.meta", "div.legend", "span.lb", "summary", "details.easy", "p.basis", "h3",
                "section > div.box.flag", "div.box.p1 > p.why", "div.box.p1d > p.why", "div.box.ai > p.why",
                "div.box.p1 > p.qt", "div.box.p1d > p.qt", "section.pack > h2", "section.pack > p.why", "section[id$=end] > h2"):
        drop(sel)
    for st in main_el.select("div.cc strong"):
        if st.get_text(strip=True) in ("정의", "자주 혼동되는 점"):
            st.decompose()
    corpus = alnum("".join(md_plain(v) for v in lec.values()))
    total = miss = 0
    for t in main_el.find_all(string=True):
        if not isinstance(t, NavigableString):
            continue
        s = re.sub(r"<(/?su[bp])>", "", str(t))
        if t.parent.name == "strong" and s.strip() == "이 Part가 답하는 질문:":
            continue
        if t.parent.name == "figcaption":
            s = re.sub(r"^\s*강의자료", "", s)
        pieces = [s]
        if t.find_parent("div", class_="qh") is not None or t.find_parent("div", class_="big") is not None:
            pieces = re.split(r"\s+·\s+|→|\.\s|흐름은 이래\s*—", re.sub(r"^\s*\[[^\]]*\]", "", s))
        if t.parent.name == "p" and "hd" in (t.parent.get("class") or []):
            pieces = re.split(r"\s+—\s+", s)
        if t.find_parent("section", class_="pack") is not None and t.find_parent("div", class_="qh") is None:
            pieces = re.split(r"\[[^\]]*\]", s)
        for pc in pieces:
            key = alnum(pc)
            if len(key) < 4:
                continue
            total += 1
            if key not in corpus:
                miss += 1
                bad += 1
                print(f"✕ 노트에 없는 글자 — <{t.parent.name} {t.parent.get('class')}>: {pc.strip()[:90]}")
    print(f"원본 → 노트: 글자 조각 {total - miss}/{total}")

    # ③ 노트 → 원본 (새 사실이 없는지)
    raw_html = re.sub(r'src="data:image/[^"]+"', 'src=""', open(a.html, encoding="utf-8").read()).split("<main", 1)[-1]
    raw_html = re.sub(r"&lt;(/?su[bp])&gt;", "", raw_html)
    src_soup = BeautifulSoup(raw_html, "html.parser")
    src_segs = set()
    src_all = ""
    for t in src_soup.find_all(string=True):
        src_all += " " + str(t)
    for seg in re.split(r"\s*[·→—|:;,.?!()「」『』/]\s*|\s{2,}", src_all):
        k2 = alnum(seg)
        if k2:
            src_segs.add(k2)
    src = " ".join(src_segs) + " " + alnum(src_all)
    frames = sorted((alnum(f) for f in FRAMES), key=len, reverse=True)
    extra = lines = 0
    for k, v in lec.items():
        if k.endswith("길잡이"):
            continue
        body = re.sub(r"\A---\n.*?\n---\n", "", v, flags=re.S)
        body = body.split("\n## 내가 더한 것")[0]
        for ln in body.split("\n")[2:]:
            raw = re.sub(r"^(> ?)+", "", ln).strip()
            raw = re.sub(r"^\[!\w+\][+-]?\s*", "", raw)
            if not raw or raw == "?" or raw.startswith(("[!", "|")) and "---" in raw:
                continue
            raw = re.sub(r"^#{1,6}\s+|^(\d+\\?[.)]|[-+*])\s+", "", raw)
            raw = re.sub(r"Part \d+ \(p\.[\d–\-]+\)", " ", raw)
            for seg in re.split(r"\s*[·→—|:;,.?!()「」『』/]\s*|==|\*\*|~|\s{2,}", md_plain(raw)):
                key = alnum(seg)
                for f in frames:
                    key = key.replace(f, " ")
                for piece in key.split():
                    if len(piece) < 6:
                        continue
                    lines += 1
                    if piece not in src:
                        extra += 1
                        bad += 1
                        print(f"✕ 원본에 없는 글자 — {k}: {seg.strip()[:90]}")
    print(f"노트 → 원본: 글자 조각 {lines - extra}/{lines} (질문 틀 제외)")

    # ④ 카드 모양
    cards = 0
    for k, v in lec.items():
        tagged = bool(re.search(r"^tags:\n(?:  - .*\n)*  - flashcards", v, flags=re.M))
        body = re.sub(r"\A---\n.*?\n---\n", "", v, flags=re.S)
        for blk in re.split(r"\n\s*\n", body):
            ls = blk.split("\n")
            qa = any(x.strip() == "?" for x in ls)
            if qa:
                cards += 1
                i = [x.strip() for x in ls].index("?")
                if i == 0 or i == len(ls) - 1 or [x.strip() for x in ls].count("?") > 1:
                    bad += 1
                    print(f"✕ 카드 모양 — {k}: {ls[0][:60]}")
                if not tagged:
                    bad += 1
                    print(f"✕ 태그 없는 노트의 카드 — {k}: {ls[0][:60]}")
            if "::" in blk or ";;" in blk:
                bad += 1
                print(f"✕ 플러그인 구분자와 겹침 — {k}: {blk[:60]}")
            if tagged and not qa and "==" in blk and not blk.lstrip().startswith("틀린 것을"):
                bad += 1
                print(f"✕ 뜻하지 않은 빈칸 카드 — {k}: {blk[:60]}")
            if qa and any(x.endswith("  ") for x in ls):
                bad += 1
                print(f"✕ 줄 끝 공백 — {k}: {ls[0][:60]}")
    print(f"카드 모양: 묻고 답하기 {cards}장")
    print("검사 통과" if bad == 0 else f"✕ 문제 {bad}건")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
