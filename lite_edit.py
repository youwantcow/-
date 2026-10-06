#!/usr/bin/env python3
"""lite_edit.py — 이미지가 든 학습자료 HTML을 안전하게 고치는 도구 (후공개 지침 v1.0)

이미지까지 넣은 Part 파일은 base64 때문에 2~4 MB라 통째로 읽거나 고칠 수 없다.
이 도구가 이미지를 떼어 낸 작업 사본을 만들고, 고친 뒤 이미지를 되붙이면서
「기존 글자를 바꾸거나 지우지 않았는지」를 센다. 작업 파일은 원본 옆의 _lite/ 폴더에 둔다
(그래서 `…_Part*.html` 같은 글롭에 걸리지 않는다).

  strip    Part.html [...]   이미지를 뗀 작업 사본 _lite/Part.lite.html 을 만들고 절 목록을 보여 준다.
                             Claude는 이 사본만 Read·Edit 한다.
                             (사본이 원본보다 새것이면 고치던 중이므로 덮어쓰지 않는다 → --force)
  restore  Part.html [...]   _lite/Part.lite.html 에 원본의 이미지를 되붙여 Part.html 을 다시 쓴다.
                             (사본 경로 _lite/Part.lite.html 을 줘도 된다)
                             처음 restore 할 때의 원본은 _lite/Part.before.html 로 보관하고,
                             변경 검사는 늘 이 처음 원본과 비교한다(여러 번 고쳐도 누적 변경이 보인다).
                             검사: 이미지 n/n · 줄 추가 · 줄 안 끼워 넣기 · 기존 글자 바뀐 줄(예상/그 밖)
                                   · 지운 줄 · 중복 id · 끊긴 링크 · 기출 카드(처음 → 지금, 새 id)
                             「예상」= meta 줄과 「기출 장부:」 문장(기출 반영 때 바꾸게 되어 있는 곳).
                             문제가 있으면 파일은 쓰되 종료 코드 1로 알린다 → 사본을 고쳐 다시 restore.
  outline  Part.html [...]   절 목록만 본다(파일을 바꾸지 않는다).

원리: <img ... data-page="N" src="data:..."> 의 src 를 src="lite:N" 으로 바꿔 떼고,
      되붙일 때 원본에서 같은 쪽(N)의 이미지로 채운다. 이미지가 없는 파일에도 그대로 쓸 수 있다.
"""
import argparse, os, re, shutil, sys
from difflib import SequenceMatcher

IMG = re.compile(r"<img\b[^>]*>")
PAGE = re.compile(r'\bdata-page="(\d+)"')
SRC = re.compile(r'\ssrc="([^"]*)"')
CARD = re.compile(r'<div class="q (?:same|diff)"[^>]*\bid="([^"]+)"')


def read(p): return open(p, encoding="utf-8").read()
def write(p, s): open(p, "w", encoding="utf-8").write(s)
def mb(n): return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{n / 1e3:.0f} KB"
def plain(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def paths(f):
    """Part.html 이나 _lite/Part.lite.html 어느 쪽을 받아도 (원본, 사본, 처음 원본) 경로를 돌려준다."""
    f = os.path.abspath(f)
    if f.endswith(".lite.html"):
        stem = os.path.basename(f)[: -len(".lite.html")]
        orig = os.path.join(os.path.dirname(os.path.dirname(f)), stem + ".html")
    else:
        stem = re.sub(r"\.html?$", "", os.path.basename(f)); orig = f
    work = os.path.join(os.path.dirname(orig), "_lite")
    return orig, os.path.join(work, stem + ".lite.html"), os.path.join(work, stem + ".before.html")


def strip_images(html):
    """data URI 이미지를 src="lite:N" 으로 바꾼다. 반환: (사본, {쪽: src}, 뗀 수)"""
    store, n = {}, [0]

    def sub(m):
        tag = m.group(0); pg = PAGE.search(tag); src = SRC.search(tag)
        if not pg or not src or not src.group(1).startswith("data:"):
            return tag
        store[pg.group(1)] = src.group(1); n[0] += 1
        return tag[:src.start(1)] + "lite:" + pg.group(1) + tag[src.end(1):]
    return IMG.sub(sub, html), store, n[0]


def filled(html):
    return sum(1 for t in IMG.findall(html) if PAGE.search(t) and 'src="data:' in t)


def main_part(html):
    m = re.search(r"<main>(.*?)</main>", html, re.S)
    return m.group(1) if m else html


def outline(html):
    body = main_part(html); out = []
    meta = re.search(r'<p class="meta">(.*?)</p>', body, re.S)
    if meta: out.append("  meta: " + plain(meta.group(1)))
    led = re.search(r"기출 장부:[^<]*", body)
    out.append("  기출 장부: " + (led.group(0)[len("기출 장부:"):].strip() if led else "(문장 없음)"))
    for m in re.finditer(r'<section\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</section>', body, re.S):
        sid, s = m.group(1), m.group(2)
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", s, re.S)
        pages = PAGE.findall(s); cards = CARD.findall(s)
        out.append(f"  절 {sid} 「{plain(h2.group(1)) if h2 else ''}」"
                   + (f" · 쪽 {','.join(pages)}" if pages else "")
                   + f" · 기출 카드 {len(cards)}" + (f" ({', '.join(cards)})" if cards else ""))
    return "\n".join(out)


def checks(html):
    body = main_part(html)
    ids = re.findall(r'\sid="([^"]+)"', body)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    broken = sorted({h for h in re.findall(r'href="#([^"]+)"', body) if h not in set(ids)})
    return dup, broken, CARD.findall(body)


def show(ops, old, new, width=60):
    """바뀐 곳을 짧게: -지운 글자 / +넣은 글자"""
    parts = []
    for t, i1, i2, j1, j2 in ops:
        if t in ("replace", "delete"): parts.append("- " + repr(old[i1:i2][:width]))
        if t in ("replace", "insert"): parts.append("+ " + repr(new[j1:j2][:width]))
    return " / ".join(parts[:6])


def diff_report(old, new):
    a, b = old.splitlines(), new.splitlines()
    added = inline = 0; changed, deleted = [], []
    for t, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if t == "equal": continue
        if t == "insert": added += j2 - j1; continue
        if t == "delete":
            deleted += [(i1 + k + 1, a[i1 + k]) for k in range(i2 - i1)]; continue
        o, n = "\n".join(a[i1:i2]), "\n".join(b[j1:j2])
        ops = SequenceMatcher(None, o, n, autojunk=False).get_opcodes()
        if all(op in ("equal", "insert") for op, *_ in ops):  # 기존 글자는 그대로 두고 끼워 넣기만 했다
            inline += i2 - i1; added += max(0, (j2 - j1) - (i2 - i1))
        else:  # meta 줄과 「기출 장부:」 문장은 반영 때 바꾸게 되어 있는 곳(예상된 변경)
            expected = 'class="meta"' in o or "기출 장부:" in o
            changed.append((i1 + 1, plain(o)[:80], show(ops, o, n), expected))
    return added, inline, changed, deleted


def cmd_strip(files, force):
    for f in files:
        orig, lite, _ = paths(f)
        if f.endswith(".lite.html"):
            print(f"{os.path.basename(f)}: 이미 작업 사본이다 — 원본(.html)을 줄 것"); continue
        if not os.path.exists(orig):
            print(f"{orig}: 파일이 없다"); continue
        if os.path.exists(lite) and os.path.getmtime(lite) > os.path.getmtime(orig) and not force:
            print(f"{os.path.basename(orig)}: 고치던 사본 _lite/{os.path.basename(lite)} 이 원본보다 새것이라 "
                  f"덮어쓰지 않았다 (먼저 restore 하거나, 버려도 되면 --force)"); continue
        os.makedirs(os.path.dirname(lite), exist_ok=True)
        html = read(orig); s, _, n = strip_images(html); write(lite, s)
        print(f"{os.path.basename(orig)} → {lite} · 이미지 {n}개 분리 "
              f"({mb(os.path.getsize(orig))} → {mb(len(s.encode()))})")
        print(outline(s))


def cmd_restore(files):
    bad = False
    for f in files:
        orig, lite, bak = paths(f)
        if not os.path.exists(lite) or not os.path.exists(orig):
            print(f"{os.path.basename(orig)}: 원본 또는 사본(_lite/{os.path.basename(lite)})이 없다 — 먼저 strip"); bad = True; continue
        o_html = read(orig); e_lite = read(lite)
        _, store, n_before = strip_images(o_html)
        # 변경 검사는 처음 원본(.before.html)과 비교한다 — 여러 번 고쳐도 반영 전 상태 기준의 누적 변경이 보인다
        ref_html = read(bak) if os.path.exists(bak) else o_html
        ref_lite = strip_images(ref_html)[0]
        missing = []

        def put(m):
            tag = m.group(0); src = SRC.search(tag)
            if not src or not src.group(1).startswith("lite:"): return tag
            pg = src.group(1)[5:]
            if pg not in store: missing.append(pg); return tag
            return tag[:src.start(1)] + store[pg] + tag[src.end(1):]
        new = IMG.sub(put, e_lite)
        if missing:
            print(f"{os.path.basename(orig)}: 원본에 없는 쪽 이미지 {sorted(set(missing))} — 되붙이지 않았다(파일 안 씀)")
            bad = True; continue
        n_after = filled(new)
        added, inline, changed, deleted = diff_report(ref_lite, e_lite)
        _, _, cards_before = checks(ref_html); dup, broken, cards_after = checks(new)
        if not os.path.exists(bak): shutil.copy2(orig, bak)
        write(orig, new)
        newc = [c for c in cards_after if c not in cards_before]
        exp = sum(1 for c in changed if c[3]); unexp = len(changed) - exp
        print(f"{os.path.basename(orig)}: 복원 완료 · {mb(os.path.getsize(orig))} · 이미지 {n_after}/{n_before}"
              + ("" if n_after == n_before else "  ⚠ 이미지 수가 다르다"))
        print(f"  변경 검사 (기준: 처음 원본): 줄 추가 {added} · 줄 안 끼워 넣기 {inline}"
              f" · 기존 글자 바뀐 줄 {len(changed)} (예상 {exp} · 그 밖 {unexp}) · 지운 줄 {len(deleted)}"
              + ("" if not unexp and not deleted else "  ⚠ 기존 본문이 바뀌었다 — 사본을 고쳐 다시 restore"))
        for ln, o, d, e in changed:
            print(f"    {'바뀜(예상)' if e else '바뀜 ⚠'} {ln}행 「{o}」  {d}")
        for ln, o in deleted[:20]:
            print(f"    지움 ⚠ {ln}행 「{plain(o)[:80]}」")
        print(f"  기출 카드 {len(cards_before)} → {len(cards_after)}" + (f" (새: {', '.join(newc)})" if newc else "")
              + f" · 중복 id {len(dup)}{' ' + str(dup[:10]) if dup else ''}"
              + f" · 끊긴 링크 {len(broken)}{' ' + str(broken[:10]) if broken else ''}")
        if n_after != n_before or dup or broken or unexp or deleted: bad = True
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="이미지가 든 학습자료 HTML 고치기 (strip → Edit → restore)")
    ap.add_argument("cmd", choices=["strip", "restore", "outline"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--force", action="store_true", help="strip: 고치던 사본이 있어도 덮어쓴다")
    a = ap.parse_args()
    if a.cmd == "strip": cmd_strip(a.files, a.force)
    elif a.cmd == "restore": cmd_restore(a.files)
    else:
        for f in a.files:
            s, _, n = strip_images(read(f)); print(f"{os.path.basename(f)} · 이미지 {n}개"); print(outline(s))
