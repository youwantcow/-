#!/usr/bin/env python3
"""ctx_edit.py — 과목 컨텍스트(03) 파일을 표 단위로 안전하게 고치는 도구 (지침 v1.9 · v1.1)

파일 전체를 다시 쓰지 않는다. 지정한 절의 표에서 지정한 행만 바꾸거나 더하고, 나머지 줄은 글자 그대로 둔다.
쓰기 명령은 끝에 「최종 수정:」 날짜를 오늘로 바꾸고, 무엇이 바뀌었는지 한 줄로 보고한다.
(Claude가 파일을 통째로 다시 타이핑하다 다른 행을 바꾸거나 지우는 일을 막기 위한 도구다.)

  show     파일 [--section 2|2-1|2-2|3|4|5]       절의 표(또는 3절의 교수 블록)를 읽은 대로 보여 준다
  check    파일                                     구조 검사(절·표 머리·열 수). 문제가 있으면 종료 코드 1
  prof     파일 --date 09-03 --prof 김OO [--week 1] [--lecture ..] [--topic ..] [--material 완료|미완] [--sheet 있음|없음] [--note ..] [--new]
           §2 강의별 담당 교수표 한 행 갱신·추가. 대응 행은 --lecture → --date → --week 순으로 찾고 없으면 빈 행에 넣거나 덧붙인다
  prof-bulk 파일 rows.tsv                           §2 여러 행. 첫 줄 머리: 주차 수업일 담당교수 강의명 대응기출주제 학습자료 압축시트 비고 (있는 열만)
  alias    파일 --mark 김T --prof 김OO [--note ..]  §2-1 기출 교수 표기 사전 (표기 기준 갱신·추가)
  history  파일 --topic 주제 [--prev 이전명칭] [--year 2025=김OO ...] [--exam-file 기출파일.md]
           §2-2 주제별 담당 이력 (주제 기준 갱신·추가. 연도 열이 없으면 「이전 명칭」 뒤에 만든다)
  history-bulk 파일 rows.tsv                        §2-2 여러 행. 머리: 주제 이전명칭 2025 2024 2023 이전 기출파일 (있는 열만)
  glossary 파일 --pair "STT표기=올바른표기" ...     §4 용어집 추가. 같은 쌍은 건너뛰고, 같은 STT 표기에 다른 표기가 있으면 충돌로 보고(--force 면 덮어씀)
  glossary-bulk 파일 pairs.tsv                      §4 여러 쌍 (두 열: STT표기  올바른표기)
  glossary-log 파일 보정로그.md                      §4 ← 보정로그의 「3. 용어집 추가 후보」(표 또는 "A → B" 목록)를 그대로 넣는다 (2차병합 마무리용)
  profile  파일 --prof 김OO [--field 항목 --value 값]... [--line 문장]... [--tag "강의명 · 날짜"]
           §3 교수별 출제 프로필. 블록이 없으면 OOO 틀을 복사해 만든다. --field 는 빈 항목이면 채우고 있으면 뒤에 잇는다. --line 은 블록 끝에 「- [tag] 문장」
  weak     파일 --date .. --lecture .. --wrong .. --confused .. [--recheck ..]   §5 약점 로그 행 추가
  touch    파일                                     최종 수정일만 오늘로

공통: --out 다른파일  (기본은 제자리 저장) · --date-today YYYY-MM-DD (최종 수정일에 쓸 날짜, 기본 오늘)
"""
import argparse, datetime, os, re, sys

SEC_HEAD = {"1": r"^## 1\.", "2": r"^## 2\.", "2-1": r"^### 2-1\.", "2-2": r"^### 2-2\.",
            "3": r"^## 3\.", "4": r"^## 4\.", "5": r"^## 5\."}
PLACEHOLDER = {"완료·미완", "있음·없음", "완료/미완", "있음/없음"}
PROFILE_FIELDS = ["강조할 때의 말버릇", "즐겨 내는 문제 유형", "기출 재활용 정도", "자주 출제하는 부위", "적중률 기록"]  # 03 틀의 3절 항목(틀 블록이 없을 때)
COLKEY = {  # 명령 인자 → 표 머리에서 찾을 글자
    "week": "주차", "date": "수업일", "prof": "담당 교수", "lecture": "강의명", "topic": "대응 기출 주제",
    "material": "학습자료", "sheet": "압축 시트", "note": "비고",
}
PROF_TSV = {"주차": "week", "수업일": "date", "담당교수": "prof", "담당 교수": "prof", "강의명": "lecture",
            "대응기출주제": "topic", "대응 기출 주제": "topic", "학습자료": "material", "압축시트": "sheet",
            "압축 시트": "sheet", "비고": "note"}


# ---------- 파일 ----------
class Doc:
    def __init__(self, path):
        raw = open(path, encoding="utf-8", newline="").read()
        self.nl = "\r\n" if "\r\n" in raw else "\n"
        self.lines = raw.replace("\r\n", "\n").split("\n")
        self.path = path
        self.changes = []

    def save(self, out=None):
        open(out or self.path, "w", encoding="utf-8", newline="").write(self.nl.join(self.lines))

    def section(self, key):
        """(머리 줄 번호, 끝 줄 번호[미포함]) — 끝은 다음 어떤 제목(##·###)이든 그 앞"""
        pat = re.compile(SEC_HEAD[key])
        start = next((i for i, l in enumerate(self.lines) if pat.match(l)), None)
        if start is None:
            sys.exit(f"{key}절 제목을 찾지 못했다 (예: '## 2.' / '### 2-2.'). 03 틀의 제목을 그대로 둘 것")
        end = next((i for i in range(start + 1, len(self.lines)) if re.match(r"^#{2,3} ", self.lines[i])), len(self.lines))
        return start, end

    def table(self, key):
        """절 안의 첫 표 → Table"""
        s, e = self.section(key)
        for i in range(s, e):
            if self.lines[i].lstrip().startswith("|") and i + 1 < e and re.match(r"^\s*\|?\s*:?-{2,}", self.lines[i + 1]):
                j = i + 2
                while j < e and self.lines[j].lstrip().startswith("|"):
                    j += 1
                return Table(self, i, i + 1, list(range(i + 2, j)), key)
        sys.exit(f"{key}절에서 표를 찾지 못했다")


def cells(line):
    s = line.strip()
    if s.startswith("|"): s = s[1:]
    if s.endswith("|"): s = s[:-1]
    return [c.strip() for c in s.split("|")]


def render(cs):
    return "| " + " | ".join(c.replace("|", "／").replace("\n", " ").strip() for c in cs) + " |"


def is_example(cs):
    return bool(cs) and cs[0].startswith("(예")


def is_blank(cs, skip=()):
    return all((not c) or (c in PLACEHOLDER) or (c.startswith("(예")) for k, c in enumerate(cs) if k not in skip)


class Table:
    def __init__(self, doc, hdr, sep, rows, key):
        self.doc, self.hdr, self.sep, self.rows, self.key = doc, hdr, sep, rows, key
        self.h = cells(doc.lines[hdr])

    def col(self, keyword, required=True):
        for i, c in enumerate(self.h):  # 정확히 같은 열이 있으면 그것(「이전」이 「이전 명칭」에 걸리지 않게)
            if c.strip() == keyword:
                return i
        for i, c in enumerate(self.h):
            if keyword in c:
                return i
        if required:
            sys.exit(f"{self.key}절 표 머리에 「{keyword}」 열이 없다: {self.h}")
        return None

    def get(self, i):
        cs = cells(self.doc.lines[i])
        return cs + [""] * (len(self.h) - len(cs))

    def set(self, i, cs):
        self.doc.lines[i] = render(cs)

    def add_col(self, after_idx, name):
        """표에 열을 끼워 넣는다 (머리·구분선·모든 행)"""
        for i in self.rows:  # 머리를 바꾸기 전에(옛 열 수 기준으로) 행을 먼저 늘린다
            cs = self.get(i); cs.insert(after_idx + 1, ""); self.set(i, cs)
        self.h.insert(after_idx + 1, name)
        self.doc.lines[self.hdr] = render(self.h)
        sep = cells(self.doc.lines[self.sep]); sep.insert(after_idx + 1, "---"); self.doc.lines[self.sep] = render(sep)

    def append_row(self, cs, sort_key=None):
        """빈 틀 행이 있으면 거기에, 없으면 정렬 위치(sort_key가 있으면) 또는 마지막 행 뒤에. 예시 행은 지운다. 반환: 줄 번호"""
        # 예시 행 제거
        for i in [r for r in self.rows if is_example(self.get(r))]:
            del self.doc.lines[i]
            self.rows = [r - 1 if r > i else r for r in self.rows if r != i]
        for i in self.rows:
            if is_blank(self.get(i)):
                self.set(i, cs); return i
        pos = (self.rows[-1] if self.rows else self.sep) + 1
        if sort_key is not None:
            k = sort_key(cs)
            for i in self.rows:
                if sort_key(self.get(i)) > k:
                    pos = i; break
        self.doc.lines.insert(pos, render(cs))
        self.rows = [r + 1 if r >= pos else r for r in self.rows] + [pos]
        self.rows.sort()
        return pos

    def find(self, idx, value, extra=None):
        for i in self.rows:
            cs = self.get(i)
            if cs[idx].strip() == value.strip() and (extra is None or extra(cs)):
                return i
        return None


# ---------- 공통 쓰기 마무리 ----------
def finish(doc, args, msg):
    today = args.date_today or datetime.date.today().isoformat()
    for i, l in enumerate(doc.lines[:15]):
        if "최종 수정:" in l:
            doc.lines[i] = re.sub(r"최종 수정:\s*\S*", f"최종 수정: {today}", l); break
    doc.save(getattr(args, "out", None))
    print(msg + f" · 최종 수정 {today} → {getattr(args, 'out', None) or doc.path}")


def read_tsv(path):
    rows = [l.rstrip("\n").split("\t") for l in open(path, encoding="utf-8") if l.strip()]
    hdr = [c.strip().replace(" ", "") for c in rows[0]]
    return hdr, [[c.strip() for c in r] + [""] * (len(hdr) - len(r)) for r in rows[1:]]


# ---------- §2 교수표 ----------
def prof_upsert(t, vals, new=False):
    """vals: {week,date,prof,lecture,topic,material,sheet,note}(있는 것만). 반환: ('갱신'|'추가', 줄)"""
    ci = {k: t.col(v, required=False) for k, v in COLKEY.items()}

    def same_lecture(cs):  # 기존 행의 수업일·강의명이 비어 있거나 새 값과 같아야 같은 강의로 본다
        for k in ("date", "lecture"):
            if vals.get(k) and ci[k] is not None and cs[ci[k]] and cs[ci[k]] != vals[k]:
                return False
        return True
    tgt = None
    if not new:
        if vals.get("lecture") and ci["lecture"] is not None:
            tgt = t.find(ci["lecture"], vals["lecture"], same_lecture)
        if tgt is None and vals.get("date") and ci["date"] is not None:
            tgt = t.find(ci["date"], vals["date"], same_lecture)
        if tgt is None and vals.get("week") and ci["week"] is not None:
            tgt = t.find(ci["week"], str(vals["week"]), same_lecture)
    cs = t.get(tgt) if tgt is not None else [""] * len(t.h)
    for k, v in vals.items():
        if v is None or ci.get(k) is None: continue
        cs[ci[k]] = str(v)
    for k, default in (("material", "미완"), ("sheet", "없음")):
        if ci[k] is not None and (not cs[ci[k]] or cs[ci[k]] in PLACEHOLDER):
            cs[ci[k]] = default
    if tgt is not None:
        t.set(tgt, cs); return "갱신", tgt

    def key(row):  # 주차(숫자) → 수업일 순. 비어 있으면 맨 뒤
        w = row[ci["week"]] if ci["week"] is not None else ""
        d = row[ci["date"]] if ci["date"] is not None else ""
        return (int(w) if w.isdigit() else 10**6, d or "~")
    return "추가", t.append_row(cs, sort_key=key)


def cmd_prof(doc, a):
    t = doc.table("2")
    vals = {k: getattr(a, k) for k in COLKEY if getattr(a, k, None) is not None}
    if not vals: sys.exit("바꿀 값이 없다")
    how, i = prof_upsert(t, vals, a.new)
    finish(doc, a, f"§2 교수표 {how} 1행 ({doc.lines[i]})")


def cmd_prof_bulk(doc, a):
    t = doc.table("2"); hdr, rows = read_tsv(a.tsv)
    keys = [PROF_TSV.get(h) for h in hdr]
    if None in keys: sys.exit(f"TSV 머리에 모르는 열: {[h for h, k in zip(hdr, keys) if k is None]} (쓸 수 있는 열: {sorted(set(PROF_TSV))})")
    n = {"갱신": 0, "추가": 0}
    for r in rows:
        vals = {k: v for k, v in zip(keys, r) if v != ""}
        how, _ = prof_upsert(t, vals); n[how] += 1
    finish(doc, a, f"§2 교수표 갱신 {n['갱신']} · 추가 {n['추가']} (TSV {len(rows)}행)")


# ---------- §2-1 표기 사전 ----------
def cmd_alias(doc, a):
    t = doc.table("2-1"); cm, cp, cn = t.col("표기"), t.col("실제 교수"), t.col("비고", required=False)
    i = t.find(cm, a.mark)
    cs = t.get(i) if i is not None else [""] * len(t.h)
    cs[cm], cs[cp] = a.mark, a.prof
    if a.note is not None and cn is not None: cs[cn] = a.note
    if i is not None: t.set(i, cs); how = "갱신"
    else: t.append_row(cs); how = "추가"
    finish(doc, a, f"§2-1 표기 사전 {how}: {a.mark} → {a.prof}")


# ---------- §2-2 담당 이력 ----------
def history_upsert(t, topic, prev=None, years=None, file=None):
    ct = t.col("주제"); cp = t.col("이전 명칭", required=False); cf = t.col("기출 파일", required=False)
    for y in (years or {}):
        if y not in t.h:
            after = cp if cp is not None else ct
            # 연도 열은 내림차순 유지: 기존 연도 열 중 y보다 작은 첫 열 앞, 없으면 가장 뒤 연도 열 뒤
            ycols = [(i, int(h)) for i, h in enumerate(t.h) if re.fullmatch(r"\d{4}", h)]
            pos = next((i - 1 for i, v in ycols if v < int(y)), (ycols[-1][0] if ycols else after))
            t.add_col(pos, y)
            cp = t.col("이전 명칭", required=False); cf = t.col("기출 파일", required=False)
    i = t.find(ct, topic)
    cs = t.get(i) if i is not None else [""] * len(t.h)
    cs[ct] = topic
    if prev is not None and cp is not None: cs[cp] = prev
    for y, v in (years or {}).items(): cs[t.col(y)] = v
    if file is not None and cf is not None: cs[cf] = file
    if i is not None: t.set(i, cs); return "갱신"
    t.append_row(cs); return "추가"


def parse_years(items):
    out = {}
    for s in items or []:
        if "=" not in s: sys.exit(f"--year 는 '2025=김OO' 꼴: {s}")
        y, v = s.split("=", 1); y = y.strip()
        if not re.fullmatch(r"\d{4}", y) and y != "이전": sys.exit(f"연도가 아니다: {y}")
        out[y] = v.strip()
    return out


def cmd_history(doc, a):
    t = doc.table("2-2")
    how = history_upsert(t, a.topic, a.prev, parse_years(a.year), a.exam_file)
    finish(doc, a, f"§2-2 담당 이력 {how}: {a.topic}")


def cmd_history_bulk(doc, a):
    t = doc.table("2-2"); hdr, rows = read_tsv(a.tsv)
    ct = next((i for i, h in enumerate(hdr) if h.startswith("주제")), None)
    if ct is None: sys.exit("TSV 머리에 「주제」 열이 없다")
    cp = next((i for i, h in enumerate(hdr) if h.startswith("이전명칭")), None)
    cf = next((i for i, h in enumerate(hdr) if h.startswith("기출")), None)
    ys = [(i, h) for i, h in enumerate(hdr) if re.fullmatch(r"\d{4}", h) or h == "이전"]
    n = {"갱신": 0, "추가": 0}
    for r in rows:
        if not r[ct]: continue
        years = {h: r[i] for i, h in ys if r[i]}
        how = history_upsert(t, r[ct], r[cp] if cp is not None and r[cp] else None, years, r[cf] if cf is not None and r[cf] else None)
        n[how] += 1
    finish(doc, a, f"§2-2 담당 이력 갱신 {n['갱신']} · 추가 {n['추가']} (TSV {len(rows)}행)")


# ---------- §4 용어집 ----------
def norm(s): return re.sub(r"\s+", "", s).lower()


def glossary_add(t, pairs, force=False):
    cs_, cr = t.col("STT"), t.col("올바른")
    have = {}
    for i in t.rows:
        cs = t.get(i)
        if cs[cs_]: have[norm(cs[cs_])] = (i, cs[cr])
    added, skipped, conflict = 0, 0, []
    for stt, right in pairs:
        stt, right = stt.strip(), right.strip()
        if not stt or not right: continue
        k = norm(stt)
        if k in have:
            i, cur = have[k]
            if norm(cur) == norm(right): skipped += 1
            elif force:
                cs = t.get(i); cs[cr] = right; t.set(i, cs); added += 1; have[k] = (i, right)
            else: conflict.append(f"{stt}: 기존 '{cur}' ≠ 새 '{right}'")
            continue
        cs = [""] * len(t.h); cs[cs_], cs[cr] = stt, right
        have[k] = (t.append_row(cs), right); added += 1
    return added, skipped, conflict


def cmd_glossary(doc, a):
    pairs = []
    for p in a.pair:
        if "=" not in p: sys.exit(f"--pair 는 'STT표기=올바른표기' 꼴: {p}")
        pairs.append(tuple(p.split("=", 1)))
    added, skipped, conflict = glossary_add(doc.table("4"), pairs, a.force)
    for c in conflict: print("  충돌(안 바꿈):", c)
    finish(doc, a, f"§4 용어집 추가 {added} · 이미 있음 {skipped} · 충돌 {len(conflict)}")
    if conflict: sys.exit(2)


def cmd_glossary_bulk(doc, a):
    hdr, rows = read_tsv(a.tsv)
    pairs = [(r[0], r[1]) for r in rows if len(r) >= 2]
    added, skipped, conflict = glossary_add(doc.table("4"), pairs, a.force)
    for c in conflict: print("  충돌(안 바꿈):", c)
    finish(doc, a, f"§4 용어집 추가 {added} · 이미 있음 {skipped} · 충돌 {len(conflict)} (TSV {len(rows)}행)")
    if conflict: sys.exit(2)


def glossary_pairs_from_log(path):
    """보정로그에서 「용어집 추가 후보」 절을 찾아 (STT 표기, 올바른 표기) 쌍을 뽑는다.
    표(| STT 표기 | 올바른 표기 |, 앞에 구간 열이 있어도 됨)와 목록("- A → B", "A → B", "A→B") 둘 다 읽는다."""
    lines = open(path, encoding="utf-8").read().splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^#{1,4}\s*", l) and "용어집" in l), None)
    if start is None: sys.exit("보정로그에서 「용어집 추가 후보」 절(제목에 '용어집')을 찾지 못했다")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^#{1,4}\s+\S", lines[i])), len(lines))
    pairs, hdr = [], None
    for l in lines[start + 1:end]:
        s = l.strip()
        if not s: continue
        if s.startswith("|"):
            cs = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cs if c): continue
            if hdr is None:
                hdr = cs
                si = next((i for i, h in enumerate(hdr) if "STT" in h or "잘못" in h), None)
                ri = next((i for i, h in enumerate(hdr) if "올바른" in h or "정확" in h), None)
                if si is None or ri is None:  # 머리에 이름이 없으면: 구간 열이 있으면 2·3열, 없으면 1·2열
                    si, ri = (1, 2) if hdr and hdr[0].startswith("구간") else (0, 1)
                continue
            if len(cs) > max(si, ri) and cs[si] and cs[ri] and cs[si] not in ("없음", "-", "—"):
                pairs.append((cs[si], cs[ri]))
            continue
        m = re.match(r"^(?:[-*•]\s*|\d+[.)]\s*)?(.+?)\s*(?:→|->|⇒)\s*(.+?)\s*$", s)
        if m and not s.startswith("#"):
            a_, b_ = m.group(1).strip("`\"' "), m.group(2).strip("`\"' ")
            if a_ and b_ and len(a_) < 80: pairs.append((a_, b_))
    return pairs


def cmd_glossary_log(doc, a):
    pairs = glossary_pairs_from_log(a.log)
    if not pairs: sys.exit("용어집 추가 후보가 비어 있다")
    added, skipped, conflict = glossary_add(doc.table("4"), pairs, a.force)
    for c in conflict: print("  충돌(안 바꿈):", c)
    finish(doc, a, f"§4 용어집 ← 보정로그 {os.path.basename(a.log)}: 후보 {len(pairs)} = 추가 {added} · 이미 있음 {skipped} · 충돌 {len(conflict)}")
    if conflict: sys.exit(2)


# ---------- §3 교수 프로필 ----------
def prof_blocks(doc):
    s, e = doc.section("3")
    # 3절의 끝은 다음 '## ' 제목 (### 교수 블록은 안에 포함)
    e = next((i for i in range(s + 1, len(doc.lines)) if doc.lines[i].startswith("## ")), len(doc.lines))
    heads = [i for i in range(s, e) if re.match(r"^### .+ 교수님", doc.lines[i])]
    blocks = []
    for k, h in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else e
        name = re.match(r"^### (.+?) 교수님", doc.lines[h]).group(1).strip()
        blocks.append((name, h, end))
    return s, e, blocks


def unfilled(v):
    """항목 값이 틀 그대로인가: 비었거나 '(…)' 힌트이거나 '__%' 같은 빈칸"""
    v = v.strip()
    return (not v) or v.startswith("(") or "__" in v


def cmd_profile(doc, a):
    s, e, blocks = prof_blocks(doc)
    tag = a.tag or datetime.date.today().isoformat()
    tpl = next((b for b in blocks if b[0] == "OOO"), None)
    blk = next((b for b in blocks if b[0] == a.prof), None)
    if blk is None:
        if tpl is not None:
            body = [l.replace("OOO", a.prof, 1) if i == 0 else l for i, l in enumerate(doc.lines[tpl[1]:tpl[2]])]
            while body and not body[-1].strip(): body.pop()
            ins = tpl[1]  # 새 블록은 OOO 틀 바로 앞에 둔다(틀은 항상 맨 뒤에 남는다)
        else:  # 틀 블록이 없으면 03 틀의 기본 항목으로 만든다
            body = [f"### {a.prof} 교수님"] + [f"- {f}:" for f in PROFILE_FIELDS]
            ins = e
        while ins > s + 1 and not doc.lines[ins - 1].strip(): ins -= 1
        doc.lines[ins:ins] = [""] + body + [""]
        s, e, blocks = prof_blocks(doc)
        blk = next(b for b in blocks if b[0] == a.prof)
        made = "블록 생성 · "
    else:
        made = ""
    name, h, end = blk
    nf = nl = 0
    for f, v in zip(a.field or [], a.value or []):
        for i in range(h + 1, end):
            m = re.match(r"^(- " + re.escape(f) + r"\s*:)\s*(.*)$", doc.lines[i])
            if m:
                cur = m.group(2).strip()
                if unfilled(cur):
                    doc.lines[i] = f"{m.group(1)} {v} ({tag})"
                else:
                    doc.lines[i] = f"{m.group(1)} {cur} / {v} ({tag})"
                nf += 1; break
        else:
            doc.lines.insert(end, f"- {f}: {v} ({tag})"); end += 1; nf += 1
    for l in a.line or []:
        ins = end
        while ins > h + 1 and not doc.lines[ins - 1].strip(): ins -= 1
        doc.lines.insert(ins, f"- [{tag}] {l}"); end += 1; nl += 1
    finish(doc, a, f"§3 {a.prof} 교수님 프로필: {made}항목 {nf} · 메모 줄 {nl}")


# ---------- §5 약점 로그 ----------
def cmd_weak(doc, a):
    t = doc.table("5")
    cs = [""] * len(t.h)
    for key, val in (("날짜", a.date), ("강의", a.lecture), ("틀린", a.wrong), ("헷갈", a.confused), ("재확인", a.recheck)):
        c = t.col(key, required=False)
        if c is not None and val is not None: cs[c] = val
    t.append_row(cs)
    finish(doc, a, "§5 약점 로그 추가 1행")


# ---------- show · check ----------
def cmd_show(doc, a):
    keys = [a.section] if a.section else ["2", "2-1", "2-2", "4", "5"]
    for k in keys:
        if k == "3":
            s, e, blocks = prof_blocks(doc)
            for name, h, end in blocks:
                print(f"[§3 {name} 교수님]"); print("\n".join(doc.lines[h + 1:end]).rstrip()); print()
            continue
        t = doc.table(k)
        print(f"[§{k}] 열: " + " | ".join(t.h))
        for i in t.rows:
            cs = t.get(i)
            if is_blank(cs) and not a.all: continue
            print("  " + " | ".join(cs))
        print()
    if not a.section:
        s, e, blocks = prof_blocks(doc)
        print("[§3] 교수 블록: " + ", ".join(b[0] for b in blocks))


def cmd_check(doc, a):
    bad = 0
    for k in ("1", "2", "2-1", "2-2", "3", "4", "5"):
        try: doc.section(k)
        except SystemExit as ex: print("✗", ex); bad += 1
    for k in ("2", "2-1", "2-2", "4", "5"):
        try: t = doc.table(k)
        except SystemExit as ex: print("✗", ex); bad += 1; continue
        n = len(t.h); filled = 0
        for i in t.rows:
            cs = cells(doc.lines[i])
            if len(cs) != n:
                print(f"✗ §{k} {i + 1}행 열 수 {len(cs)} ≠ 머리 {n}: {doc.lines[i]}"); bad += 1
            if not is_blank(cs): filled += 1
        print(f"§{k}: 열 {n} · 채워진 행 {filled} / {len(t.rows)}")
    s, e, blocks = prof_blocks(doc)
    print("§3: 교수 블록 " + (", ".join(b[0] for b in blocks) or "없음"))
    m = next((l for l in doc.lines[:15] if "최종 수정:" in l), None)
    print("머리: " + (m.strip() if m else "✗ 「최종 수정:」 줄 없음"))
    print("구조 검사 " + ("통과" if not bad else f"실패 {bad}건"))
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("file"); p.add_argument("--out"); p.add_argument("--date-today")
        return p
    p = common(sp.add_parser("show")); p.add_argument("--section"); p.add_argument("--all", action="store_true", help="빈 행도 보인다")
    common(sp.add_parser("check"))
    p = common(sp.add_parser("prof"))
    for k in COLKEY: p.add_argument("--" + k)
    p.add_argument("--new", action="store_true", help="대응 행을 찾지 않고 무조건 새 행")
    p = common(sp.add_parser("prof-bulk")); p.add_argument("tsv")
    p = common(sp.add_parser("alias")); p.add_argument("--mark", required=True); p.add_argument("--prof", required=True); p.add_argument("--note")
    p = common(sp.add_parser("history")); p.add_argument("--topic", required=True); p.add_argument("--prev"); p.add_argument("--year", action="append"); p.add_argument("--exam-file")
    p = common(sp.add_parser("history-bulk")); p.add_argument("tsv")
    p = common(sp.add_parser("glossary")); p.add_argument("--pair", action="append", required=True); p.add_argument("--force", action="store_true")
    p = common(sp.add_parser("glossary-bulk")); p.add_argument("tsv"); p.add_argument("--force", action="store_true")
    p = common(sp.add_parser("glossary-log")); p.add_argument("log"); p.add_argument("--force", action="store_true")
    p = common(sp.add_parser("profile")); p.add_argument("--prof", required=True); p.add_argument("--field", action="append"); p.add_argument("--value", action="append"); p.add_argument("--line", action="append"); p.add_argument("--tag")
    p = common(sp.add_parser("weak")); p.add_argument("--date"); p.add_argument("--lecture"); p.add_argument("--wrong"); p.add_argument("--confused"); p.add_argument("--recheck")
    common(sp.add_parser("touch"))
    a = ap.parse_args()
    if a.cmd == "profile" and len(a.field or []) != len(a.value or []):
        sys.exit("--field 와 --value 의 개수가 다르다")
    doc = Doc(a.file)
    {"show": cmd_show, "check": cmd_check, "prof": cmd_prof, "prof-bulk": cmd_prof_bulk, "alias": cmd_alias,
     "history": cmd_history, "history-bulk": cmd_history_bulk, "glossary": cmd_glossary, "glossary-bulk": cmd_glossary_bulk,
     "glossary-log": cmd_glossary_log,
     "profile": cmd_profile, "weak": cmd_weak, "touch": lambda d, a: finish(d, a, "날짜만 갱신")}[a.cmd](doc, a)


if __name__ == "__main__":
    main()
