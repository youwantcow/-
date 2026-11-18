#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recall_kit.py v1.1 · 지침 v2.9 — 학습자료 HTML(지침 v2.7+) → Obsidian 인출 노트

읽기용 사본은 만들지 않는다. 학습자료에 이미 들어 있는 「꺼내게 만드는 것」만 골라
① 노트 안에서는 가림(형광펜 = 빈칸, 답은 접힘) ② Spaced Repetition 플러그인에는 카드가 되게 옮긴다.

  python3 recall_kit.py build 전체.html --pdf 강의자료.pdf --lecture Intro1-1 --subject 분자생물학 -o OUT/분자생물학 \
          [--canvas 뼈대.canvas] [--outline 뼈대.md]
  python3 recall_kit.py pack OUT/분자생물학/Intro1-1 -o 인출_분자생물학_Intro1-1.zip [--first-time]

강의 하나 = 폴더 하나(OUT/과목/강의/ 안에 노트 · 뼈대 · 첨부/). 보관함의 과목 폴더에 그 폴더만 끌어다 놓으면 된다.

노트 넷 + 길잡이
  1 흐름  강의 전체 → Part → 절 순서 → 방향 사슬                         (덱 …/1-흐름)
  2 개념  대표 질문 · ★ · 개념 카드 · 함정 · 표의 줄 · 인출 연습            (덱 …/2-개념)
  3 기출  기출(동일 교수 먼저) · 변형 예측 · 퀴즈                         (덱 …/3-기출)
  4 표와 쪽  빈칸 인출 표 · 혼동 쌍 표 · 쪽 제목만 보고 내용 말하기 — 가림만, 카드 아님

카드 문법(플러그인 기본 설정 그대로)
  · 질문 줄들 / ? / 답 줄들  — 빈 줄 없이 붙어 있어야 한 장
  · 태그가 붙은 노트에서 ==빈칸== 이 든 문단 — 빈칸 하나가 한 장 (이 변환기는 만들지 않는다. 사용자가 더할 때 쓰는 길)
  표는 한 줄 = 한 장으로 쪼개 묻는다(표째로 빈칸 카드를 만들면 다른 칸이 답을 알려 준다).
새 사실은 만들지 않는다 — 질문 문장(「정의는?」 같은 틀)만 덧붙인다.
"""
import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter, OrderedDict

from bs4 import BeautifulSoup, NavigableString, Tag

O, C, E = "", "", ""
HAIR = " "
PAGE_RE = re.compile(r"(?<![A-Za-z0-9])p\.(\d{1,3})((?:[–\-]\d{1,3})?)")
SUBS = str.maketrans("0123456789+-−", "₀₁₂₃₄₅₆₇₈₉₊₋₋")
SUPS = str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")


def is_punct(ch):
    return bool(ch) and unicodedata.category(ch)[0] in "PS"


def plab(pno):
    """Part 번호 → 머리글 이름. 강의 틀(지침 v2.7 Step 4의 3)은 Part가 아니라 「강의 틀」."""
    return "강의 틀" if pno == "틀" else f"Part {pno}"


def classes(el):
    return el.get("class") or []


def kids(el):
    return [k for k in el.children if isinstance(k, Tag)]


class R:
    def __init__(self, lecture, subject, pdf_name, npages, first=1):
        self.lecture, self.subject, self.pdf, self.npages, self.first = lecture, subject, pdf_name, npages, first
        self.N = {k: f"{lecture} {v}" for k, v in
                  {"flow": "1 흐름", "con": "2 개념", "exam": "3 기출", "page": "4 표와 쪽", "hub": "길잡이"}.items()}
        self.targets = {}            # html id → ("h", note, heading) | ("p", page)
        self.used = Counter()        # 머리글 중복 방지 (note, heading)
        self.stats = Counter()
        self.warn = []
        self.figs = OrderedDict()    # 기출 그림 번호 → 파일 이름

    # ───────── 글자 ─────────
    def esc(self, s, table=False):
        s = s.replace("\\", "\\\\")
        s = re.sub(r"([*_`~$])", r"\\\1", s)
        s = re.sub(r"<(/?su[bp])>", "\ue010\\1\ue011", s)
        s = s.replace("<", "\\<").replace("\ue010", "<").replace("\ue011", ">")
        s = s.replace("[[", "\\[\\[").replace("](", "]\\(").replace("[^", "\\[^")
        s = s.replace("==", "\\=\\=").replace("%%", "\\%\\%")
        s = s.replace("::", ":​:").replace(";;", ";​;")      # 플러그인 구분자와 겹치지 않게
        s = re.sub(r"#(?=[^\s\d#])", r"\\#", s)
        if table:
            s = s.replace("|", "\\|")
        return s

    def pdf_link(self, page, label, table=False):
        return f"[[{self.pdf}#page={page - self.first + 1}{'\\|' if table else '|'}{label}]]"

    def text(self, s, ctx):
        s = re.sub(r"\s+", " ", s)
        table = ctx.get("table", False)
        if not ctx.get("link", True) or ctx.get("inmark"):
            return self.esc(s, table)
        out, pos = [], 0
        for m in PAGE_RE.finditer(s):
            n = int(m.group(1))
            if not (self.first <= n < self.first + self.npages) or n in ctx.get("cur", ()):
                continue
            out.append(self.esc(s[pos:m.start()], table))
            out.append(self.pdf_link(n, m.group(0), table))
            self.stats["쪽 링크"] += 1
            pos = m.end()
        out.append(self.esc(s[pos:], table))
        return "".join(out)

    def plain(self, el, drop=()):
        parts = []
        for n in el.descendants:
            if isinstance(n, NavigableString):
                skip = False
                for anc in n.parents:
                    if anc is el:
                        break
                    c = classes(anc)
                    if anc.name == "span" and ("lb" in c or "imp" in c or any(d in c for d in drop)):
                        skip = True
                    if anc.name in drop:
                        skip = True
                if skip:
                    continue
                t = str(n)
                if n.parent.name == "sub":
                    t = t.translate(SUBS)
                elif n.parent.name == "sup":
                    t = t.translate(SUPS)
                parts.append(t)
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    @staticmethod
    def heading(s):
        return re.sub(r"\s+", " ", re.sub(r"[#^|\[\]]", " ", s)).strip()

    def uniq(self, note, head):
        self.used[(note, head)] += 1
        n = self.used[(note, head)]
        return head if n == 1 else f"{head} ({n})"

    # ───────── 인라인 ─────────
    def inl(self, el, ctx=None):
        return self._resolve(self._inl(el, ctx or {})).strip()

    def _inl(self, el, ctx):
        if isinstance(el, NavigableString):
            return self.text(str(el), ctx)
        out = []
        for ch in el.children:
            if isinstance(ch, NavigableString):
                out.append(self.text(str(ch), ctx))
                continue
            name, cls = ch.name, classes(ch)
            if name == "span" and "bk" in cls:                       # 빈칸 인출의 칸
                out.append(self.mark_tok(ch, ctx))
            elif name == "b" and "bd" in cls:                        # 슬라이드의 굵은 글씨
                out.append(self.mark_tok(ch, ctx) if ctx.get("mark_slide") else f"{O}b{E}{self._inl(ch, ctx)}{C}b{E}")
            elif name == "mark":                                     # 형광펜
                out.append(self.mark_tok(ch, ctx) if ctx.get("mark_slide") else f"{O}b{E}{self._inl(ch, ctx)}{C}b{E}")
            elif name in ("strong", "b"):
                out.append(f"{O}b{E}{self._inl(ch, ctx)}{C}b{E}")
            elif name in ("em", "i"):
                out.append(f"{O}i{E}{self._inl(ch, ctx)}{C}i{E}")
            elif name == "u":
                out.append(f"<u>{self._inl(ch, ctx)}</u>")
            elif name in ("sub", "sup"):
                out.append(f"<{name}>{self._inl(ch, dict(ctx, link=False))}</{name}>")
            elif name == "br":
                out.append("<br>")
            elif name == "span" and ("lb" in cls or "imp" in cls):
                if "판독 불가" in ch.get_text():
                    out.append(" (판독 불가)")
            elif name == "span" and "hand" in cls:
                out.append(f'<span class="hand">✎ {self._inl(ch, dict(ctx, link=False)).strip()}</span>')
            elif name == "span" and "pg" in cls:
                out.append(f"({self._inl(ch, ctx).strip()})")
            elif name == "span" and "en" in cls:
                out.append(f" ({self._inl(ch, dict(ctx, link=False)).strip()})")
            elif name == "span" and "key" in cls:
                out.append(f"{O}b{E}{self._inl(ch, ctx)}{C}b{E}")
            elif name == "a":
                out.append(self.anchor(ch, ctx))
            elif name in ("details", "ul", "ol", "table", "div", "figure"):
                continue
            else:
                out.append(self._inl(ch, ctx))
        return "".join(out)

    def mark_tok(self, el, ctx):
        if ctx.get("inmark"):
            return self._inl(el, ctx)
        self.stats["빈칸(원본 표시)"] += 1
        return f"{O}k{E}{self._inl(el, dict(ctx, inmark=True))}{C}k{E}"

    def _resolve(self, s):
        pat = re.compile(f"{O}([bik]){E}((?:(?![{O}{C}]).)*?){C}\\1{E}", re.S)
        while True:
            m = pat.search(s)
            if not m:
                break
            kind, inner = m.group(1), m.group(2)
            core = inner.strip()
            if not core:
                s = s[:m.start()] + inner + s[m.end():]
                continue
            lead, trail = inner[:len(inner) - len(inner.lstrip())], inner[len(inner.rstrip()):]
            prev = " " if lead else (s[m.start() - 1] if m.start() > 0 else "")
            nxt = " " if trail else (s[m.end()] if m.end() < len(s) else "")
            edge = lambda c: c == "" or c.isspace() or is_punct(c) or c in (O, C, E)
            if kind == "k":
                rep = self.mark(core, prev, nxt)
            else:
                ok = (not is_punct(core[0]) or edge(prev)) and (not is_punct(core[-1]) or edge(nxt))
                md, tag = ("**", "strong") if kind == "b" else ("*", "em")
                if (kind == "i" and "*" in core) or (kind == "b" and "**" in core) or "<br>" in core:
                    ok = False
                rep = f"{md}{core}{md}" if ok else f"<{tag}>{core}</{tag}>"
            s = s[:m.start()] + lead + rep + trail + s[m.end():]
        return s.replace(O, "").replace(C, "").replace(E, "")

    def mark(self, core, prev="", nxt=""):
        """==빈칸==. 문장부호와 글자가 맞닿아 형광펜 문법이 깨질 수 있는 자리에는 아주 좁은 공백을 끼운다."""
        core = core.strip().replace("==", "= =")
        edge = lambda c: c == "" or c.isspace() or is_punct(c) or c in (O, C, E)
        pre = HAIR if (is_punct(core[0]) and not edge(prev)) else ""
        post = HAIR if (is_punct(core[-1]) and not edge(nxt)) else ""
        if pre or post:
            self.stats["좁은 공백"] += 1
        self.stats["빈칸"] += 1
        return f"{pre}=={core}=={post}"

    def hide(self, md):
        """이미 변환된 문장 전체를 가린다(답 한 줄)."""
        md = md.strip()
        if not md:
            return ""
        if "==" in md:                       # 이미 빈칸이 든 문장은 그대로
            return md
        return self.mark(md)

    def anchor(self, a, ctx):
        label = self.esc(re.sub(r"\s+", " ", re.sub(r"[\[\]]", " ", self.plain(a))).strip() or "링크", ctx.get("table", False))
        href = a.get("href", "")
        t = self.targets.get(href[1:]) if href.startswith("#") else None
        if ctx.get("inmark"):
            return label
        if not t:
            self.warn.append(f"링크 대상 없음: {href}")
            return label
        bar = "\\|" if ctx.get("table") else "|"
        if t[0] == "p":
            self.stats["쪽 링크"] += 1
            return self.pdf_link(t[1], label, ctx.get("table", False))
        self.stats["노트 링크"] += 1
        return f"[[{t[1]}#{t[2]}{bar}{label}]]"

    # ───────── 블록 조각 ─────────
    @staticmethod
    def guard(line):
        """줄 첫머리가 목록 · 인용 · 머리글로 읽히지 않게."""
        line = re.sub(r"^(\d+)([.)]) ", r"\1\\\2 ", line)
        line = re.sub(r"^([-+]) ", r"\\\1 ", line)
        line = re.sub(r"^>", r"\\>", line)
        line = re.sub(r"^#", r"\\#", line)
        line = re.sub(r"^\?$", "？", line)
        return line

    def para(self, el, ctx=None):
        return self.guard(self.inl(el, ctx))

    def lead_split(self, p, ctx=None):
        """<p><strong>라벨:</strong> 내용</p> → (라벨 md, 내용 md). 라벨이 없으면 ("", 전체)."""
        st = p.find(["strong", "b"])
        if st and p.contents and p.contents[0] is st and st.get_text(strip=True).endswith(":") and "bd" not in classes(st):
            clone = BeautifulSoup(str(p), "html.parser").find(p.name)
            lab = clone.find(["strong", "b"])
            label = lab.get_text(" ", strip=True)
            lab.extract()
            return f"**{self.esc(label)}**", self.inl(clone, ctx)
        return "", self.inl(p, ctx)

    def hidden_lines(self, el, ctx=None):
        """요소 하나를 「답 줄」들로 — 문단은 통째로, 목록은 항목마다 가린다."""
        ctx = dict(ctx or {}, inmark=True)
        name, cls = el.name, classes(el)
        if name == "p":
            lab, body = self.lead_split(el, ctx)
            body = self.hide(body)
            return [f"{lab} {body}".strip()] if body else []
        if name in ("ul", "ol"):
            if "chain" in cls:
                return [" → ".join(self.hide(self.inl(li, ctx)) for li in el.find_all("li", recursive=False))]
            out = []
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                mk = f"{i}." if name == "ol" else "-"
                out.append(f"{mk} {self.hide(self.inl(li, ctx))}")
            return out
        return []

    def qa(self, front, back):
        """질문 줄들 / ? / 답 줄들. 빈 줄이 끼면 플러그인이 카드를 끊으므로 걸러 낸다."""
        f = [ln for part in front for ln in part.split("\n") if ln.strip()]
        b = [ln for part in back for ln in part.split("\n") if ln.strip()]
        if not f or not b:
            self.warn.append(f"빈 카드: {' / '.join(f)[:60]}")
            return ""
        f = [self.guard(x) if i else x for i, x in enumerate(f)]
        self.stats["질문 카드"] += 1
        return "\n".join(f + ["?"] + b)

    def callout(self, kind, title, blocks, fold=""):
        blocks = [b for b in blocks if b and b.strip()]
        lines = [f"> [!{kind}]{fold} {title}".rstrip()]
        if blocks and re.match(r"[|>]", blocks[0]):
            lines.append(">")
        for ln in "\n\n".join(blocks).split("\n") if blocks else []:
            lines.append("> " + ln if ln else ">")
        return "\n".join(lines)

    def lst(self, el, ctx=None, depth=0):
        if "opt" in classes(el):
            return "\n".join(self.guard(self.inl(li, ctx)) for li in el.find_all("li", recursive=False))
        if "chain" in classes(el):
            return " → ".join(self.inl(li, ctx) for li in el.find_all("li", recursive=False))
        lines = []
        for i, li in enumerate(el.find_all("li", recursive=False), 1):
            mk = f"{i}." if el.name == "ol" else "-"
            t = self.inl(li, ctx)
            if "ok" in classes(li):
                t = "✔ " + t
            lines.append(f"{'    ' * depth}{mk} {t}")
            for sub in li.find_all(["ul", "ol"], recursive=False):
                lines.append(self.lst(sub, ctx, depth + 1))
        return "\n".join(lines)

    def table(self, tb, ctx=None, dif="bold"):
        tctx = dict(ctx or {}, table=True)

        def cell_md(cell):
            t = self.inl(cell, tctx)
            if "dif" in classes(cell) and t:
                if dif == "mark" and "==" not in t:
                    t = self.mark(t)
                elif dif == "bold":
                    t = self.boldc(t)
            return t

        def expand(rows):
            grid, carry = [], {}
            for r, tr in enumerate(rows):
                row, c, it = [], 0, iter(tr.find_all(["td", "th"], recursive=False))
                while True:
                    if (r, c) in carry:
                        row.append(carry.pop((r, c)))
                        c += 1
                        continue
                    cell = next(it, None)
                    if cell is None:
                        if any(k[0] == r and k[1] >= c for k in carry):
                            row.append(("", False))
                            c += 1
                            continue
                        break
                    t, th = cell_md(cell), cell.name == "th"
                    rs, cs = int(cell.get("rowspan", 1) or 1), int(cell.get("colspan", 1) or 1)
                    for dc in range(cs):
                        row.append((t if dc == 0 else "", th))
                        for dr in range(1, rs):
                            carry[(r + dr, c + dc)] = ("〃" if th else t, th)
                        c += 1
                grid.append(row)
            return grid

        head = expand(tb.find("thead").find_all("tr")) if tb.find("thead") else []
        body = expand(tb.find("tbody").find_all("tr") if tb.find("tbody") else tb.find_all("tr"))
        ncol = max(len(r) for r in head + body)
        hdr = []
        for c in range(ncol):
            seen = []
            for r in head:
                t = r[c][0] if c < len(r) else ""
                if t and t != "〃" and t not in seen:
                    seen.append(t)
            hdr.append(" — ".join(seen) or " ")
        lines = ["| " + " | ".join(hdr) + " |", "|" + "|".join([" --- "] * ncol) + "|"]
        for r in body:
            cells = []
            for c in range(ncol):
                t, th = r[c] if c < len(r) else ("", False)
                if th and t and t != "〃":
                    t = self.boldc(t)
                cells.append(t or " ")
            lines.append("| " + " | ".join(cells) + " |")
        self.stats["표"] += 1
        return "\n".join(lines)

    @staticmethod
    def boldc(t):
        if "**" in t or "==" in t or "<br>" in t or is_punct(t[0]) or is_punct(t[-1]):
            return f"<strong>{t}</strong>"
        return f"**{t}**"

    def blocks(self, el, ctx=None):
        """접힌 답 · 쪽별 콜아웃 안에 들어갈 보통 블록(가리지 않음)."""
        name, cls = el.name, classes(el)
        if name == "p":
            if "ask" in cls:
                t = self.para(el, ctx)
                return [t if t.startswith("시험에서는") else "**시험에서는** " + t]
            t = self.para(el, ctx)
            return [t] if t else []
        if name in ("ul", "ol"):
            return [self.lst(el, ctx)]
        if name == "div" and "tw" in cls:
            return [self.table(el.find("table"), ctx, dif="mark" if (ctx or {}).get("mark_slide") else "bold")]
        if name == "table":
            return [self.table(el, ctx)]
        if name == "h4":
            return [f"**{self.esc(self.plain(el))}**"]
        if name == "div" and "box" in cls and "flag" in cls:
            lb = el.find("span", class_="lb")
            body = [b for k in kids(el) for b in self.blocks(k, ctx)]
            return [self.callout("todo", self.esc(lb.get_text(strip=True) if lb else "⚠ 확인 필요"), body, "-")]
        if name == "div" and "box" in cls:
            out = []
            for k in kids(el):
                if k.name == "p" and "hd" in classes(k):
                    out.append(f"**{self.esc(self.plain(k, drop=('pg',)))}**")
                elif k.name == "p" and "why" in classes(k):
                    continue
                else:
                    out.extend(self.blocks(k, ctx))
            return out
        if name in ("details", "figure", "summary", "hr"):
            return []
        t = self.para(el, ctx)
        return [t] if t else []

    # ───────── 머리글 이름(1차 등록과 2차 생성이 같은 함수를 쓴다) ─────────
    def box_parts(self, box):
        hd = box.find("p", class_="hd", recursive=False)
        lb = hd.find("span", class_="lb") if hd else None
        label = lb.get_text(strip=True).strip("[]") if lb else ""
        pg = hd.find("span", class_="pg") if hd else None
        title = self.plain(hd, drop=("pg",)) if hd else ""
        subject = re.split(r"\s+—\s+", title)[0] if title else ""
        return label, title, subject, (self.plain(pg) if pg else ""), hd

    def qid(self, q):
        hid = q.get("id") or ""
        m = re.search(r"-q(\d.*)$", hid)
        return m.group(1) if m else hid

    def register(self, parts):
        for pno, nodes in parts:
            for el in nodes:
                for t in [el] + el.find_all(id=True):
                    hid = t.get("id")
                    if not hid:
                        continue
                    cls = classes(t)
                    if t.name == "figure":
                        img = t.find("img")
                        if img is not None and img.get("data-page"):
                            self.targets[hid] = ("p", int(img["data-page"]))
                    elif t.name == "section":
                        pg = t.find("h2").find("span", class_="pg") if t.find("h2") else None
                        m = re.search(r"p\.(\d+)", self.plain(pg)) if pg else None
                        if "pack" in cls:
                            self.targets[hid] = ("h", self.N["con"], plab(pno))
                        elif m:
                            self.targets[hid] = ("p", int(m.group(1)))
                        else:
                            self.targets[hid] = ("h", self.N["con"], plab(pno))
                    elif "box" in cls and ("p1" in cls or "p1d" in cls):
                        label, title, subject, pg, _ = self.box_parts(t)
                        self.targets[hid] = ("h", self.N["con"], self.uniq(self.N["con"], self.heading(f"★ {subject} · {label}")))
                    elif "cc" in cls:
                        hd = t.find("p", class_="hd")
                        ttl = self.plain(hd, drop=("en", "a"))
                        imp = hd.find("span", class_="imp")
                        if imp:
                            ttl += " · " + imp.get_text(strip=True)
                        self.targets[hid] = ("h", self.N["con"], self.uniq(self.N["con"], self.heading(ttl)))
                    elif "drill" in cls:
                        _, title, _, _, _ = self.box_parts(t)
                        self.targets[hid] = ("h", self.N["page"], self.uniq(self.N["page"], self.heading("빈칸 · " + title)))
                    elif "q" in cls and "pq" in cls:
                        sp = t.find("div", class_="qh").find("span")
                        con = re.sub(r"^개념:\s*", "", self.plain(sp).split(" · ")[0]) if sp else ""
                        k = re.search(r"-q(\d+)$", hid)
                        self.targets[hid] = ("h", self.N["exam"], self.uniq(self.N["exam"], self.heading(f"퀴즈 {pno}-{k.group(1) if k else ''} · {con}")))
                    elif "q" in cls:
                        self.targets[hid] = ("h", self.N["exam"], self.uniq(self.N["exam"], self.heading(f"기출 {self.qid(t)}")))

    # ───────── 문항(기출 · 변형 · 퀴즈) ─────────
    def mcq(self, q, kind, pno):
        qh, qb, ans = q.find("div", class_="qh"), q.find("div", class_="qb"), q.find("details", class_="ans", recursive=False)
        span = qh.find("span")
        clone = BeautifulSoup(str(qh), "html.parser").div
        if clone.find("span"):
            clone.find("span").extract()
        who = clone.get_text(" ", strip=True)
        meta = [x.strip() for x in self.plain(span).split(" · ")] if span else []
        back_meta = ""
        if kind == "기출":
            who = who.strip("[]").replace(" - ", " · ")
            keep = [m for m in meta if not re.match(r"(대응|추정 근거|재출제|\(|p\.)", m)]
            rest = [m for m in meta if m not in keep]
            front = f"**기출 {' · '.join(keep)}** — {self.esc(who)}"
            if rest:
                rc = BeautifulSoup("<p></p>", "html.parser").p
                rc.string = " · ".join(rest)
                back_meta = self.inl(rc)
        elif kind == "변형":
            how = re.sub(r"^\[변형 출제 예측\]\s*", "", who)
            src = next((m for m in meta if m.startswith("원 기출")), "")
            front = f"**변형 예측 (AI 추정)** — {self.esc(src)} · {self.esc(how)}"
            rest = [m for m in meta if m.startswith("대응")]
            if rest:
                rc = BeautifulSoup("<p></p>", "html.parser").p
                rc.string = " · ".join(rest)
                back_meta = self.inl(rc)
        else:
            con = meta[0] if meta else ""
            front = f"**퀴즈 · {self.esc(who)}** — {self.esc(con)}"
        fl = [front]
        for k in kids(qb):
            if k.name == "figure":
                img = k.find("img")
                n = img.get("data-fig") if img else None
                if n:
                    fn = f"{self.lecture}_기출그림_{int(n):02d}.jpg"
                    self.figs[int(n)] = fn
                    fl.append(f"![[{fn}]]")
                    cap = k.find("figcaption")
                    if cap is not None:
                        fl.append(f"*{self.esc(self.plain(cap))}*")
            elif k.name == "ol" and "opt" in classes(k):
                fl.append(self.lst(k, {"link": False}))
            elif k.name in ("p", "ul", "ol"):
                fl.extend(self.blocks(k, {"link": False}))
        body = []
        summ = "답 · 해설"
        if ans is not None:
            for k in kids(ans):
                if k.name == "summary":
                    summ = re.sub(r"\s*보기$", "", self.plain(k)) or summ
                elif k.name == "div" and "q" in classes(k):
                    continue                                  # 변형 예측은 따로 한 장씩
                elif k.name == "p" and "why" in classes(k):
                    body.append(self.para(k))
                else:
                    body.extend(self.blocks(k))
        if back_meta:
            body.append(back_meta)
        self.stats[kind] += 1
        return self.qa(fl, [self.callout("success", self.esc(summ), body, "-")])

    def exam_section(self, sec, pno, out, same):
        for q in sec.find_all("div", class_="q", recursive=False):
            cls = classes(q)
            if "pq" in cls or "vq" in cls or ("same" in cls) != same:
                continue
            head = self.targets[q["id"]][2]
            out.append(f"#### {head}")
            out.append(self.mcq(q, "기출", pno))
            ans = q.find("details", class_="ans", recursive=False)
            for v in (ans.find_all("div", class_="vq", recursive=False) if ans else []):
                out.append(self.mcq(v, "변형", pno))

    # ───────── 개념 노트의 조각들 ─────────
    def recall_cards(self, div):
        out = []
        for li in div.find_all("li"):
            det = li.find("details", recursive=False)
            if det is None:
                continue
            qc = BeautifulSoup(str(li), "html.parser").li
            qc.find("details").extract()
            question = self.inl(qc, {"link": False})
            ac = BeautifulSoup(str(det), "html.parser").details
            if ac.find("summary"):
                ac.find("summary").extract()
            pointer = ""
            links = ac.find_all("a")
            if links:
                last = links[-1]
                tail = "".join(str(x) for x in last.next_siblings).strip()
                prev = last.previous_sibling
                if not tail and isinstance(prev, NavigableString) and str(prev).rstrip().endswith("→"):
                    real = det.find_all("a")[-1]
                    pointer = " → " + self.anchor(real, {})
                    prev.replace_with(str(prev).rstrip()[:-1])
                    last.extract()
            answer = self.hide(self.inl(ac, {"inmark": True}))
            out.append(self.qa([question], [answer + pointer]))
            self.stats["묻고 답하기"] += 1
        return out

    def star_cards(self, box, cur):
        label, title, subject, pg, hd = self.box_parts(box)
        head = self.targets[box["id"]][2] if box.get("id") in self.targets else self.heading(f"★ {subject} · {label}")
        m = re.search(r"p\.(\d+)", pg)
        plink = " " + self.pdf_link(int(m.group(1)), pg) if m else ""
        main, ask, extra, tables = [], [], [], []
        for k in kids(box):
            c = classes(k)
            if k is hd or (k.name == "p" and ("why" in c or "qt" in c)):
                continue
            if k.name == "p" and "ask" in c:
                ask.append(self.hide(self.inl(k, {"inmark": True})))
            elif k.name == "div" and "tw" in c:
                tables.append(self.callout("cover", "표 — 첫 칸만 보고 나머지를 말해 봐", [self.table(k.find("table"))]))
            elif k.name == "p":
                (extra if any(x.startswith(("1.", "-")) for x in main) else main).extend(self.hidden_lines(k))
            elif k.name in ("ol", "ul"):
                main.extend(self.hidden_lines(k))
        extra = ["- " + x for x in extra]
        rest = title[len(subject):].strip(" —")
        if rest:
            main.insert(0, "**요지:** " + self.hide(self.esc(rest)))
        out = [f"#### {head}"]
        out.append(self.qa([f"★ **{self.esc(subject)}** — 한 줄 결론과 그 이유는?{plink}"], main + extra))
        if ask:
            out.append(self.qa([f"★ **{self.esc(subject)}** — 시험에서는 어떻게 묻나?"], ask))
        out.extend(tables)
        self.stats["★"] += 1
        return out

    def concept_cards(self, cc):
        hd = cc.find("p", class_="hd")
        head = self.targets[cc["id"]][2]
        imp = hd.find("span", class_="imp")
        en = hd.find("span", class_="en")
        ref = hd.find("a")
        name = self.plain(hd, drop=("en", "a"))
        tail = (f" ({self.esc(self.plain(en))})" if en else "")
        plink = " " + self.anchor(ref, {}) if ref else ""
        out = [f"#### {head}"]
        body = cc.find("details", class_="cb") or cc

        def split_refs(el):
            c = BeautifulSoup(str(el), "html.parser").find(el.name)
            refs = []
            orig = [a for a in el.find_all("a")]
            for i, a in enumerate(c.find_all("a")):
                refs.append(self.anchor(orig[i], {}))
                a.extract()
            for st in c.find_all("strong"):
                if st.get_text(strip=True) in ("정의", "자주 혼동되는 점"):
                    st.extract()
            return self.hide(self.inl(c, {"inmark": True})), (" " + " ".join(refs) if refs else "")

        for k in kids(body):
            c = classes(k)
            if k.name == "p" and "basis" in c:
                continue
            if k.name == "p" and "pit" in c:
                h, r = split_refs(k)
                out.append(self.qa([f"**{self.esc(name)}** — 자주 혼동되는 점은?"], [h + r]))
            elif k.name == "p":
                h, r = split_refs(k)
                out.append(self.qa([f"**{self.esc(name)}**{tail} — 정의는?{plink}"], [h + r]))
            elif k.name == "ul":
                items = []
                for li in k.find_all("li", recursive=False):
                    h, r = split_refs(li)
                    items.append(f"- {h}{r}")
                out.append(self.qa([f"**{self.esc(name)}** — 요점 {len(items)}가지는?"], items))
        self.stats["개념"] += 1
        return out

    def drill_rows(self, d):
        """빈칸 인출 표의 한 줄 = 카드 한 장. 가려지지 않은 칸이 단서, 가려진 칸이 답."""
        _, title, _, pg, hd = self.box_parts(d)
        out = []
        for k in kids(d):
            if k is hd:
                continue
            if k.name == "div" and "tw" in classes(k):
                tb = k.find("table")
                heads = [self.inl(th, {"link": False}) for th in (tb.find("thead").find_all("th") if tb.find("thead") else [])]
                for ri, tr in enumerate(tb.find("tbody").find_all("tr"), 1):
                    cue, ask, back = [], [], []
                    for ci, cell in enumerate(tr.find_all(["td", "th"], recursive=False)):
                        h = heads[ci] if ci < len(heads) and heads[ci].strip() else ""
                        md = self.inl(cell, {"link": False})
                        if cell.find("span", class_="bk"):
                            ask.append(h or f"{ci + 1}번째 칸")
                            back.append(f"- {h + ': ' if h else ''}{md}")
                        elif md and md not in ("—", "–", "-"):
                            cue.append(f"{h}: {md}" if h else md)
                    if not back:
                        continue
                    q = (" · ".join(cue) if cue else f"{ri}번째 줄") + f" → {' · '.join(ask)}?"
                    out.append(self.qa([f"빈칸 · {self.esc(title)}", q], back))
                    self.stats["표의 줄"] += 1
            elif k.name in ("ol", "ul") and k.find("span", class_="bk"):
                out.append(self.qa([f"빈칸 · {self.esc(title)} — 사슬을 이어 봐."], [self.lst(k, {"link": False})]))
                self.stats["표의 줄"] += 1
        if out and d.get("id") in self.targets:
            t = self.targets[d["id"]]
            out.insert(0, f"표로 보기 → [[{t[1]}#{t[2]}|{self.esc(title)}]]")
        return out

    def drill(self, d):
        _, title, _, pg, hd = self.box_parts(d)
        head = self.targets[d["id"]][2] if d.get("id") in self.targets else self.heading("빈칸 · " + title)
        body = []
        for k in kids(d):
            if k is hd:
                continue
            if k.name == "div" and "tw" in classes(k):
                body.append(self.table(k.find("table"), {"link": False}))
            elif k.name in ("ol", "ul"):
                body.append(self.lst(k, {"link": False}))
            elif k.name == "p":
                body.append(self.para(k, {"link": False}))
        n = len(d.find_all("span", class_="bk"))
        self.stats["빈칸 인출 표"] += 1
        self.stats["빈칸 인출 칸"] += n
        m = re.search(r"p\.(\d+)", pg)
        link = self.pdf_link(int(m.group(1)), "📄 " + pg) if m else ""
        return [f"#### {head}", link, self.callout("drill", f"빈칸 인출 · {self.esc(title)}", body)]

    # ───────── 노트 넷 ─────────
    def build_notes(self, parts, metas):
        N, lec = self.N, self.lecture
        deck = f"flashcards/{self.subject}/{lec}"

        def fm(tag=None, recall=True):
            L = ["---"]
            if recall:
                L += ["cssclasses:", "  - recall"]
            if tag:
                L += ["tags:", f"  - {deck}/{tag}"]
            L += [f"과목: {self.subject}", f'강의: "{metas[0]["title"]}"', f'길잡이: "[[{N["hub"]}]]"', "---", ""]
            return "\n".join(L)

        flow, con, exam, page = [], [], [], []

        # 1 흐름 ─ 강의 전체
        qs = [m["question"] for m in metas if m["question"]]
        flow.append("## 강의 전체")
        if qs:
            npart = sum(1 for m in metas if m["pno"] != "틀")
            if npart < len(metas):
                ask = f"이 강의는 Part {npart}개와 강의 틀로 간다. 각 Part와 강의 틀이 답하는 질문을 순서대로 말해 봐."
            else:
                ask = f"이 강의는 Part {npart}개로 간다. 각 Part가 답하는 질문을 순서대로 말해 봐."
            qlab = [("강의 틀 — " if m["pno"] == "틀" else "") for m in metas if m["question"]]
            flow.append(self.qa([ask], [f"{i}. {lb}{self.hide(q)}" for i, (lb, q) in enumerate(zip(qlab, qs), 1)]))
        for (pno, nodes), mt in zip(parts, metas):
            ph = f"{plab(pno)} (p.{mt['pages']})"
            flow.append(f"## {ph}")
            if mt["flow"]:
                flow.append(self.qa([f"{plab(pno)} — 흐름을 처음부터 끝까지 말해 봐."],
                                    [" → ".join(self.hide(x) for x in mt["flow"])]))
            if mt["link"]:
                flow.append(self.qa([f"{plab(pno)} — 앞뒤 Part와 어떻게 이어지나?"], [self.hide(mt["link"])]))
            secs = [(h, p) for h, p in mt["sections"]]
            if secs:
                flow.append(self.qa([f"{plab(pno)} — 절 {len(secs)}개를 순서대로 말해 봐. (주제 — 부제)"],
                                    [f"{i}. {self.hide(h)}" + (f" {p}" if p else "") for i, (h, p) in enumerate(secs, 1)]))
            for el in nodes:
                if el.name != "section" or "pack" in classes(el):
                    continue
                for ch in el.find_all("ol", class_="chain", recursive=False):
                    subj = re.split(r"\s+—\s+", re.sub(r"^\d+\.\s*", "", self.plain(el.find("h2"), drop=("pg",))))[0]
                    items = [self.inl(li, {"inmark": True}) for li in ch.find_all("li", recursive=False)]
                    line = " → ".join([items[0]] + [self.hide(x) for x in items[1:]])
                    flow.append(self.qa([f"「{self.esc(subj)}」 방향 사슬 — 첫 칸에서 끝까지 이어 봐."], [line]))
                    self.stats["방향 사슬"] += 1

            # 2 개념
            con.append(f"## {ph}")
            for el in nodes:
                if el.name == "div" and "pre" in classes(el):
                    con.append("### 대표 질문")
                    con.extend(self.recall_cards(el))
            stars = [b for el in nodes if el.name == "section" for b in el.find_all("div", class_="box", recursive=False)
                     if "p1" in classes(b) or "p1d" in classes(b)]
            if stars:
                con.append("### ★ 교수님 강조 · 반복 출제")
                for b in stars:
                    con.extend(self.star_cards(b, None))
            ccs = [c for el in nodes if el.name == "section" for c in el.find_all("div", class_="cc")]
            if ccs:
                con.append("### 개념 카드")
                for c in ccs:
                    con.extend(self.concept_cards(c))
            traps = [b for el in nodes if el.name == "section" for b in el.find_all("div", class_="trap", recursive=False)]
            if traps:
                con.append("### 함정")
                for b in traps:
                    _, title, _, _, hd = self.box_parts(b)
                    back = [x for k in kids(b) if k is not hd for x in self.hidden_lines(k)]
                    con.append(self.qa([f"함정 · {self.esc(title)} — 무엇을 조심하라는 거지?"], back))
                    self.stats["함정"] += 1
            ais = [b for el in nodes if el.name == "section" for b in el.find_all("div", class_="ai", recursive=False)]
            if ais:
                con.append("### 예상 출제 (AI 추정)")
                for b in ais:
                    label, title, _, _, hd = self.box_parts(b)
                    back = [x for k in kids(b) if k is not hd and "why" not in classes(k) for x in self.hidden_lines(k)]
                    con.append(self.qa([f"{self.esc(label)} (AI 추정) · {self.esc(title)} — 어떤 모양으로 나올 수 있지?"], back))
                    self.stats["예상 출제"] += 1
            drills = [d for el in nodes if el.name == "section" for d in el.find_all("div", class_="drill", recursive=False)]
            if drills:
                con.append("### 표의 줄 (빈칸 인출)")
                for d in drills:
                    con.extend(self.drill_rows(d))
            for el in nodes:
                if el.name != "section":
                    continue
                for r in el.find_all("div", class_="recall", recursive=False):
                    con.append("### 인출 연습")
                    con.extend(self.recall_cards(r))

            # 3 기출
            exam.append(f"## {ph}")
            for want in (True, False):
                for el in nodes:
                    if el.name == "section" and "pack" not in classes(el):
                        self.exam_section(el, pno, exam, want)
            for el in nodes:
                if el.name == "section" and "pack" in classes(el):
                    for q in el.find_all("div", class_="pq"):
                        exam.append(f"#### {self.targets[q['id']][2]}")
                        exam.append(self.mcq(q, "퀴즈", pno))

            # 4 표와 쪽 — 가림만
            page.append(f"## {ph}")
            if drills:
                page.append("### 표 — 빈칸 인출")
                for d in drills:
                    page.extend(self.drill(d))
            covers = [b for el in nodes if el.name == "section" and (el.get("id") or "").endswith("end")
                      for b in el.find_all("div", class_="tbl", recursive=False)]
            if covers:
                page.append("### 표 — 혼동 쌍")
                for b in covers:
                    _, title, _, _, _ = self.box_parts(b)
                    for tw in b.find_all("div", class_="tw", recursive=False):
                        page.append(self.callout("cover", f"{self.esc(title)} — 첫 칸만 보고 나머지를 말해 봐", [self.table(tw.find("table"))]))
                        self.stats["혼동 쌍 표"] += 1
            page.append("### 쪽")
            for el in nodes:
                if el.name != "section" or "pack" in classes(el) or (el.get("id") or "").endswith("end"):
                    continue
                cur, buf, headline = None, [], None

                def flush():
                    if headline:
                        page.append(headline[0])
                        page.append(headline[1])
                        page.append(self.callout("page", "떠올린 뒤 열기", buf, "-") if buf else "*(이 쪽은 글 없이 그림만 있어)*")
                        self.stats["쪽"] += 1
                for ch in kids(el):
                    c = classes(ch)
                    if ch.name == "figure" and "exam" not in c:
                        flush()
                        img = ch.find("img")
                        n = int(img["data-page"])
                        cap = re.sub(r"^강의자료\s*", "", self.plain(ch.find("figcaption")))
                        m = re.match(r"p\.(\d+)[–\-](\d+)", cap)
                        cur = set(range(int(m.group(1)), int(m.group(2)) + 1)) if m else {n}
                        cur.add(n)
                        headline = ("#### " + self.heading(cap), self.pdf_link(n, f"📄 강의자료 p.{n} 열기"))
                        buf = []
                    elif headline is None:
                        continue
                    elif ch.name in ("p", "ul", "ol") and "chain" not in c:
                        buf.extend(self.blocks(ch, {"mark_slide": True, "cur": cur}))
                    elif ch.name == "div" and "box" in c and ("fig" in c or "tbl" in c):
                        buf.extend(self.blocks(ch, {"mark_slide": True, "cur": cur}))
                flush()

        J = lambda L: "\n\n".join(x for x in L if x and x.strip()) + "\n"
        notes = OrderedDict()
        notes[N["flow"]] = fm("1-흐름") + f"[[{N['hub']}]] · 위에서 아래로 — 강의 전체 → Part → 절 → 방향 사슬\n\n" + J(flow)
        notes[N["con"]] = fm("2-개념") + f"[[{N['hub']}]] · 대표 질문 → ★ → 개념 카드 → 함정 → 표의 줄 → 인출 연습\n\n" + J(con) + "\n## 내가 더한 것\n\n틀린 것을 한 문장으로 적고, 가릴 말에 형광펜을 쳐. 이 노트에서는 그게 빈칸이자 카드가 돼.\n"
        notes[N["exam"]] = fm("3-기출") + f"[[{N['hub']}]] · 동일 교수 기출 → 그 밖의 기출 → 퀴즈. 답을 정한 뒤에 「답 · 해설」을 열어.\n\n" + J(exam)
        notes[N["page"]] = fm(None) + f"[[{N['hub']}]] · 카드가 아니라 가림만 있는 노트야. 표는 가려진 칸을, 쪽은 제목만 보고 내용을 말해 본 뒤 열어. 쪽을 열어도 슬라이드의 굵은 글씨 · 표의 차이 칸은 한 번 더 가려져 있어.\n\n" + J(page)
        return notes


def split_parts(main):
    parts, cur = [], None
    for el in main.children:
        if isinstance(el, Tag) and el.name == "h1":
            cur = {"h1": el, "nodes": []}
            parts.append(cur)
        elif cur is not None and isinstance(el, Tag):
            cur["nodes"].append(el)
    return parts


def count_cards(md):
    """플러그인 기본 규칙으로 카드 수를 센다(빈 줄 = 카드 끝, ? 줄 = 묻고 답하기, == == = 빈칸마다 한 장)."""
    body = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    qa = cloze = 0
    for blk in re.split(r"\n\s*\n", body):
        lines = [ln for ln in blk.split("\n") if ln.strip()]
        if not lines:
            continue
        if any(ln.strip() == "?" for ln in lines[1:]):
            qa += 1
        elif "==" in blk:
            cloze += len(re.findall(r"==(?!=)(.+?)==", blk))
    return qa, cloze


def build(a):
    raw = open(a.html, encoding="utf-8").read()
    figsrc = {int(n): b for n, b in re.findall(r'<img[^>]*data-fig="(\d+)"[^>]*src="data:image/[a-z]+;base64,([^"]+)"', raw)}
    figsrc.update({int(n): b for b, n in re.findall(r'<img[^>]*src="data:image/[a-z]+;base64,([^"]+)"[^>]*data-fig="(\d+)"', raw)})
    soup = BeautifulSoup(re.sub(r'src="data:image/[^"]+"', 'src=""', raw), "html.parser")
    main = soup.find("main") or soup
    rp = split_parts(main)
    if not rp:
        sys.exit("✕ <main> 안에 <h1>이 없다 — 빌드된 Part 또는 병합본을 줘야 한다")
    npages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", a.pdf], capture_output=True, text=True).stdout).group(1))
    pdf_name = f"{a.lecture}_강의자료.pdf"
    r = R(a.lecture, a.subject, pdf_name, npages, a.first)
    parts, metas = [], []
    for p in rp:
        m = re.search(r"Part\s*(\d+[a-z]?)", p["h1"].get_text())
        if m:
            pno = m.group(1)
        elif "강의 틀" in p["h1"].get_text():
            pno = "틀"
        else:
            pno = str(len(parts) + 1)
        parts.append((pno, p["nodes"]))
    r.register(parts)
    for (pno, nodes), p in zip(parts, rp):
        meta = next((el.get_text(" ", strip=True) for el in nodes if el.name == "p" and "meta" in classes(el)), "")
        f = [x.strip() for x in meta.split("·")]
        mt = {"pno": pno, "title": re.sub(r"\s*—\s*Part.*$", "", p["h1"].get_text(" ", strip=True)),
              "prof": re.sub(r"\s*교수님$", "", f[2]) if len(f) > 2 else "",
              "pages": re.sub(r"^강의자료\s*p\.", "", f[3]) if len(f) > 3 else "",
              "question": "", "flow": [], "link": "", "sections": []}
        big = next((el for el in nodes if el.name == "div" and "big" in classes(el)), None)
        if big is not None:
            ps = big.find_all("p", recursive=False)
            if ps:
                _, q = r.lead_split(ps[0], {"inmark": True})
                mt["question"] = q
            rest = " ".join(r.inl(x, {"inmark": True}) for x in ps[1:])
            if "→" in rest:
                last = rest.rfind("→")
                end = re.search(r"\.\s", rest[last:])
                cut = last + end.start() if end else len(rest)
                chain = re.sub(r"^.*?(?:흐름은 이래|흐름)\s*[—:\-]\s*", "", rest[:cut], count=1)
                segs, buf, depth = [], "", 0
                for chx in chain:
                    depth += chx in "(（[「"
                    depth -= chx in ")）]」"
                    if chx == "→" and depth <= 0:
                        segs.append(buf)
                        buf = ""
                    else:
                        buf += chx
                segs.append(buf)
                mt["flow"] = [x.strip() for x in segs if x.strip()]
                mt["link"] = rest[cut + 1:].strip() if end else ""
            else:
                mt["link"] = rest
        for el in nodes:
            if el.name == "section" and "pack" not in classes(el) and not (el.get("id") or "").endswith("end"):
                h2 = el.find("h2")
                pg = h2.find("span", class_="pg")
                t = re.sub(r"^\d+\.\s*", "", r.plain(h2, drop=("pg",)))
                pm = re.search(r"p\.(\d+)", r.plain(pg)) if pg else None
                mt["sections"].append((r.esc(t), r.pdf_link(int(pm.group(1)), r.plain(pg)) if pm else ""))
        metas.append(mt)

    notes = r.build_notes(parts, metas)
    counts = {k: count_cards(v) for k, v in notes.items()}
    N, s = r.N, r.stats
    tot = sum(q + c for k, (q, c) in counts.items() if k != N["page"])
    hub = ["---", f"과목: {a.subject}", f'강의: "{metas[0]["title"]}"', f"교수: {metas[0]['prof']}", f'강의자료: "[[{pdf_name}]]"', "---", "",
           f"[[{pdf_name}|📄 강의자료 PDF 열기]] · {npages}쪽 · {metas[0]['prof']} 교수님", "",
           "학습자료(HTML)로 이해한 **다음에** 여는 노트야. 여기서는 읽지 말고 꺼내. 답하기 전에는 열지 않는 게 규칙의 전부야.", "",
           "## 순서 — 위에서 아래로", "",
           f"1. **[[{N['flow']}]]** — 강의 전체 → Part → 절 → 방향 사슬 · 카드 {sum(counts[N['flow']])}장",
           f"2. **[[{N['con']}]]** — 대표 질문 · 인출 연습 {s['묻고 답하기']} · ★ {s['★']} · 개념 {s['개념']} · 함정 {s['함정']} · 표의 줄 {s['표의 줄']} · 카드 {sum(counts[N['con']])}장",
           f"3. **[[{N['exam']}]]** — 기출 {s['기출']} · 변형 예측 {s['변형']} · 퀴즈 {s['퀴즈']} · 카드 {sum(counts[N['exam']])}장",
           f"4. **[[{N['page']}]]** — 빈칸 인출 {s['빈칸 인출 표']}표({s['빈칸 인출 칸']}칸) · 혼동 쌍 {s['혼동 쌍 표']}표 · 쪽 {s['쪽']}개 · 가림만(카드 아님)", "",
           "## Part", ""]
    extras = []
    if a.canvas:
        extras.append(f"[[{a.lecture} 뼈대.canvas|뼈대 지도(캔버스)]]")
    if a.outline:
        extras.append(f"[[{a.lecture} 뼈대|뼈대 아웃라인]]")
    if extras:
        hub[9:9] = ["한눈에 → " + " · ".join(extras), ""]
    for mt in metas:
        hub.append(f"- **{plab(mt['pno'])}** (p.{mt['pages']}) — {mt['question']}")
        hub.append("    - " + " · ".join(f"[[{N[k]}#{plab(mt['pno'])} (p.{mt['pages']})|{lab}]]" for k, lab in (("flow", "흐름"), ("con", "개념"), ("exam", "기출"), ("page", "표와 쪽"))))
    notes[N["hub"]] = "\n".join(hub) + "\n"

    out_dir = os.path.join(a.out, a.lecture)
    att = os.path.join(out_dir, "첨부")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(att, exist_ok=True)
    for name, md in notes.items():
        open(os.path.join(out_dir, name + ".md"), "w", encoding="utf-8").write(md)
    shutil.copyfile(a.pdf, os.path.join(att, pdf_name))
    if a.canvas:
        shutil.copyfile(a.canvas, os.path.join(out_dir, f"{a.lecture} 뼈대.canvas"))
    if a.outline:
        shutil.copyfile(a.outline, os.path.join(out_dir, f"{a.lecture} 뼈대.md"))
    nfig = 0
    for n, fn in r.figs.items():
        if n in figsrc:
            open(os.path.join(att, fn), "wb").write(base64.b64decode(figsrc[n]))
            nfig += 1
        else:
            r.warn.append(f"기출 그림 {n} — HTML에 그림이 없다(미삽입본)")

    print(f"인출 노트: 흐름 {sum(counts[N['flow']])}장 · 개념 {sum(counts[N['con']])}장 · 기출 {sum(counts[N['exam']])}장 · 합 {tot}장 "
          f"(묻고 답하기 {sum(q for k, (q, c) in counts.items() if k != N['page'])} · 빈칸 {sum(c for k, (q, c) in counts.items() if k != N['page'])}) · 표와 쪽: {s['쪽']}쪽 · 가림 {counts[N['page']][1]}칸(카드 아님)")
    print(f"재료: 대표 질문 · 인출 연습 {s['묻고 답하기']} · ★ {s['★']} · 개념 {s['개념']} · 함정 {s['함정']} · 예상 출제 {s['예상 출제']} · 방향 사슬 {s['방향 사슬']} · "
          f"표의 줄 {s['표의 줄']}(빈칸 인출 {s['빈칸 인출 표']}표 · {s['빈칸 인출 칸']}칸) · 혼동 쌍 {s['혼동 쌍 표']}표 · 기출 {s['기출']} · 변형 {s['변형']} · 퀴즈 {s['퀴즈']} · 기출 그림 {nfig}/{len(r.figs)}")
    print(f"링크: PDF 쪽 {s['쪽 링크']} · 노트 {s['노트 링크']} · 좁은 공백 {s['좁은 공백']}")
    for w in sorted(set(r.warn)):
        print("△", w)


def pack(a):
    """강의 폴더 하나를 zip으로. 한글 파일 이름은 NFC · UTF-8 표시로 넣는다."""
    import zipfile
    folder = os.path.normpath(a.folder)
    base = os.path.dirname(folder)
    here = os.path.dirname(os.path.abspath(__file__))
    n = 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fns in os.walk(folder):
            dn.sort()
            for fn in sorted(fns):
                full = os.path.join(dp, fn)
                arc = unicodedata.normalize("NFC", os.path.relpath(full, base))
                z.write(full, arc, compress_type=zipfile.ZIP_STORED if fn.lower().endswith((".jpg", ".png", ".pdf")) else zipfile.ZIP_DEFLATED)
                n += 1
        if a.first_time:
            for src, arc in ((os.path.join(here, "recall.css"), "recall.css"),
                             (os.path.join(here, "docs", "인출_시작하기.md"), "00 인출 노트 시작하기.md")):
                if os.path.exists(src):
                    z.write(src, arc)
                    n += 1
                else:
                    print("△ 없음:", src)
    print(f"묶음: {n}개 → {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("html")
    b.add_argument("--pdf", required=True)
    b.add_argument("--lecture", required=True)
    b.add_argument("--subject", required=True)
    b.add_argument("--first", type=int, default=1)
    b.add_argument("--canvas", default="", help="map_kit.py canvas 로 만든 뼈대 캔버스(있으면 강의 폴더에 함께)")
    b.add_argument("--outline", default="", help="map_kit.py outline 으로 만든 뼈대 아웃라인(.md)")
    b.add_argument("-o", "--out", required=True, help="과목 폴더(예: OUT/분자생물학)")
    k = sub.add_parser("pack")
    k.add_argument("folder", help="강의 폴더(OUT/과목/강의)")
    k.add_argument("-o", "--out", required=True)
    k.add_argument("--first-time", action="store_true", help="스니펫 recall.css 와 「00 인출 노트 시작하기」를 함께 넣는다")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a)
    else:
        pack(a)
