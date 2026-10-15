#!/usr/bin/env python3
"""upload_kit.py — 입력 파일 접수: 강의자료 · 기출 · 강의록을 검사 · 변환 · 지문 확인 후 work/in/ 에 등록 (지침 v2.0 Step 0 보조)

Univ AI 웹앱의 「수업 자료 업로드」 흐름(형식 검사 → Office→PDF 변환 → 내용 지문 → 저장 → 텍스트 추출 → 같은 지문이면
기존 결과 재사용)을 이 프로젝트에 옮긴 것. 근거는 `분석_UnivAI_문서업로드.md`.

  add   파일 … [--into work/in] [--reg work/업로드_목록.json] [--kind auto|강의자료|기출|강의록|기출그림] [--force]
        파일마다 차례로(하나가 실패해도 나머지는 계속):
        ① 형식 검사 — PDF · Office(pptx ppt docx doc xlsx xls) · md/txt 만 받는다. 0바이트 · 300 MB 초과는 거부.
           PDF 는 앞 1 KB 안에 `%PDF-` 가 있어야 한다. hwp/hwpx 는 거부(한글에서 PDF로 내보내서 다시).
        ② 내용 지문 — sha256-chunks-v2 (4 MB 조각마다 SHA-256 → 그 해시들을 이어 다시 SHA-256). 원본 기준.
           등록부에 같은 지문이 있으면 「중복」으로 알리고 복사하지 않는다(이미 만든 학습자료를 그대로 쓰면 된다).
           이름만 같고 지문이 다르면 「새 판」으로 받아 이름 뒤에 (2) 를 붙인다. --force 면 중복도 다시 받는다.
        ③ Office 는 LibreOffice(soffice)로 PDF 변환. 지문 확인을 먼저 하므로 중복 파일은 변환하지 않는다.
        ④ PDF 검사 — 암호(열 수 없으면 실패) · 쪽수(100쪽 초과 경고 — 지침 Step 0) · 글자 층이 없는 쪽(스캔본 →
           텍스트 추출로는 아무것도 안 보인다) · 파일명의 `p41-80` → `--first 41` 제안.
           md/txt — UTF-8 이 아니면 cp949 로 읽어 UTF-8 로 바꿔 저장. 강의록은 「상태:」 줄 · 【p.N】 마커 수,
           기출 md 는 〔그림 n〕 수를 센다.
        ⑤ 종류 판정(--kind auto: 파일명 기준) → --into 에 복사 → 등록부(JSON)에 기록.
        끝에 「접수 a/n · 변환 b · 중복 c · 실패 d」 한 줄. 실패가 있으면 종료 코드 1.
  list  [--reg …]          등록부를 표로 보인다.
  sig   파일 …              지문만 계산한다(Univ AI 와 같은 형식: sha256-chunks-v2_<바이트>_<hex>).

필요한 것: python3 · (있으면) pdfinfo · pdftotext · soffice. pdfinfo 가 없으면(Windows 등) pypdf 로 쪽수·암호·글자 층을
검사한다(없으면 pip 로 설치 시도). 그래도 안 되는 검사는 건너뛰고 그 사실을 적는다. 글자 층 없는 쪽은 원본 쪽번호로 적는다.
"""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SIG_V, CHUNK = "sha256-chunks-v2", 4 * 1024 * 1024
MAX_BYTES = 300 * 1024 * 1024
OFFICE = (".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls")
TEXT = (".md", ".markdown", ".txt")
HWP = (".hwp", ".hwpx")
KINDS = ("강의자료", "기출", "강의록", "기출그림")
TEXTLESS_CHARS = 20  # 한 쪽에서 글자(공백 제외)가 이보다 적으면 「글자 층 없음」


def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def tool(*names):
    for n in names:
        p = shutil.which(n)
        if p: return p
    return None


class Reject(Exception):
    """이 파일만 실패로 처리하고 다음 파일로 넘어간다"""


# ---------- ② 지문 ----------
def signature(path):
    size = os.path.getsize(path)
    h = hashlib.sha256(f"{SIG_V}:{CHUNK}:{size}:".encode())
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(hashlib.sha256(b).digest())
    return f"{SIG_V}_{size}_{h.hexdigest()}"


# ---------- ① 형식 ----------
def gate(path):
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path): raise Reject("파일이 없다")
    size = os.path.getsize(path)
    if ext in HWP: raise Reject("한글 파일은 받지 않는다 — 한글에서 PDF로 내보내서 다시 올릴 것")
    if ext != ".pdf" and ext not in OFFICE and ext not in TEXT:
        raise Reject(f"받지 않는 형식({ext or '확장자 없음'}) — PDF · Office · md/txt 만")
    if size == 0: raise Reject("빈 파일(0바이트)")
    if size > MAX_BYTES: raise Reject(f"{size / 1e6:.0f} MB — 300 MB 이하로 나눠서")
    if ext == ".pdf":
        with open(path, "rb") as f:
            if b"%PDF-" not in f.read(1024): raise Reject("확장자는 .pdf 인데 PDF 머리(%PDF-)가 없다 — 손상되었거나 다른 형식")
    return ext


def guess_kind(name, ext):
    if ext in TEXT:
        return "기출" if "기출" in name else "강의록"
    if "기출그림" in name: return "기출그림"
    if re.search(r"기출|중간고사|기말고사|족보|시험", name): return "기출"
    return "강의자료"


# ---------- ③ Office → PDF ----------
def to_pdf(path, workdir):
    soffice = tool("soffice", "libreoffice")
    if not soffice: raise Reject("LibreOffice(soffice)가 없어 PDF로 바꿀 수 없다 — PowerPoint·Word에서 PDF로 저장해 다시 올릴 것")
    try:
        code, out, err = run([soffice, "--headless", "--convert-to", "pdf", "--outdir", workdir, path], timeout=300)
    except subprocess.TimeoutExpired:
        raise Reject("PDF 변환이 5분 안에 끝나지 않았다")
    pdf = os.path.join(workdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if code != 0 or not os.path.exists(pdf):
        raise Reject("PDF 변환 실패" + (f": {err.strip().splitlines()[-1]}" if err.strip() else ""))
    return pdf


# ---------- ④ 검사 ----------
def pdf_check(path):
    r = {"pages": None, "encrypted": False, "textless": None, "notes": []}
    if tool("pdfinfo"):
        code, out, err = run(["pdfinfo", path])
        if code != 0:
            if re.search(r"password", err, re.I): raise Reject("암호가 걸린 PDF — 암호를 풀고 다시 올릴 것")
            raise Reject("PDF를 열 수 없다" + (f": {err.strip().splitlines()[-1]}" if err.strip() else ""))
        m = re.search(r"Pages:\s+(\d+)", out); r["pages"] = int(m.group(1)) if m else None
        r["encrypted"] = bool(re.search(r"Encrypted:\s+yes", out))  # 열리는데 암호화(인쇄·복사 제한)만 걸린 경우
    else:
        reader = pypdf_reader(path)
        if reader is not None:  # poppler 가 없는 곳(Windows 등) — pypdf 로 같은 검사를 한다
            if reader.is_encrypted:
                r["encrypted"] = True
                try:
                    if not reader.decrypt(""): raise Reject("암호가 걸린 PDF — 암호를 풀고 다시 올릴 것")
                except Reject: raise
                except Exception as ex: raise Reject(f"암호화된 PDF를 열 수 없다: {ex}")
            r["pages"] = len(reader.pages)
            if not tool("pdftotext"):
                r["textless"] = [i for i, pg in enumerate(reader.pages, 1) if len(re.sub(r"\s", "", pg.extract_text() or "")) < TEXTLESS_CHARS]
            r["notes"].append("pdfinfo 없음 → pypdf 로 검사")
        else:
            data = open(path, "rb").read()
            r["pages"] = len(re.findall(rb"/Type\s*/Page(?![s\w])", data)) or None
            r["encrypted"] = b"/Encrypt" in data
            r["notes"].append("pdfinfo·pypdf 없음 → 쪽수는 추정(압축된 PDF면 못 셀 수 있다)")
    if tool("pdftotext"):
        code, out, _ = run(["pdftotext", "-enc", "UTF-8", path, "-"], timeout=300)
        if code == 0:
            pages = out.split("\f")
            if pages and not pages[-1].strip(): pages = pages[:-1]
            r["textless"] = [i for i, p in enumerate(pages, 1) if len(re.sub(r"\s", "", p)) < TEXTLESS_CHARS]
    elif r["textless"] is None:
        r["notes"].append("pdftotext 없음 → 글자 층 검사 건너뜀")
    return r


def pypdf_reader(path):
    try:
        import pypdf
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdf", "--break-system-packages"], capture_output=True)
        try:
            import pypdf
        except ImportError:
            return None
    import logging; logging.getLogger("pypdf").setLevel(logging.ERROR)  # 「wrong pointing object」 같은 복구 경고는 숨긴다
    try:
        return pypdf.PdfReader(path)
    except Exception as ex:
        raise Reject(f"PDF를 열 수 없다: {ex}")


def first_page(name):
    m = re.search(r"(?<![A-Za-z])p\.?\s*(\d+)\s*[-–~]\s*(\d+)", name)
    return int(m.group(1)) if m else 1


def text_check(src, dst, kind):
    raw = open(src, "rb").read()
    note = []
    try:
        s = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            s = raw.decode("cp949"); note.append("cp949 → UTF-8")
        except UnicodeDecodeError:
            raise Reject("글자 인코딩을 알 수 없다(UTF-8 · cp949 아님)")
    open(dst, "w", encoding="utf-8").write(s)
    if kind == "강의록":
        st = re.search(r"상태\s*[:：]\s*(.+)", s)
        markers = len(re.findall(r"【p\.?\s*\d+", s))
        note.append(f"상태: {st.group(1).strip()[:30]}" if st else "「상태:」 줄 없음")
        note.append(f"슬라이드 마커 {markers}")
    elif kind == "기출":
        figs = len(re.findall(r"〔그림\s*\d+〕", s))
        note.append(f"그림 문항 〔그림 n〕 {figs}")
    note.append(f"{len(s):,}자")
    return note


# ---------- 등록부 ----------
def load_reg(p):
    if not os.path.exists(p): return []
    return json.load(open(p, encoding="utf-8"))


def save_reg(p, reg):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)  # 중간에 멈춰도 등록부가 반쯤 쓰인 채 남지 않게


def free_name(folder, name, reg):
    taken = {e["file"] for e in reg} | set(os.listdir(folder) if os.path.isdir(folder) else [])
    if name not in taken: return name
    stem, ext = os.path.splitext(name); n = 2
    while f"{stem} ({n}){ext}" in taken: n += 1
    return f"{stem} ({n}){ext}"


# ---------- 명령 ----------
def cmd_add(a):
    reg = load_reg(a.reg); os.makedirs(a.into, exist_ok=True)
    by_sig = {e["sig"]: e for e in reg}
    cnt = {"ok": 0, "conv": 0, "dup": 0, "fail": 0}
    for src in a.files:
        name = os.path.basename(src)
        try:
            ext = gate(src)
            sig = signature(src)
            if sig in by_sig and not a.force:
                e = by_sig[sig]
                print(f"↺ 중복  {name} = 이미 등록된 {e['file']} ({e['kind']} · {e['added'][:10]}) — 받지 않음")
                cnt["dup"] += 1; continue
            kind = a.kind if a.kind != "auto" else guess_kind(name, ext)
            note, entry = [], {"sig": sig, "original": name, "kind": kind}
            with tempfile.TemporaryDirectory() as tmp:
                work = src
                if ext in OFFICE:
                    work = to_pdf(src, tmp); cnt["conv"] += 1
                    note.append(f"{ext[1:]} → PDF"); entry["converted_from"] = ext[1:]
                want = os.path.splitext(name)[0] + (".pdf" if ext in OFFICE else ext)
                if sig in by_sig:  # --force 로 다시 받는 같은 파일 → 등록된 파일을 덮어쓴다
                    out_name = by_sig[sig]["file"]; note.append("--force: 등록된 파일을 덮어씀")
                else:
                    out_name = free_name(a.into, want, reg)
                    if out_name != want: note.append(f"같은 이름의 다른 판이 있어 「{out_name}」로 저장")
                dst = os.path.join(a.into, out_name)
                if ext in TEXT:
                    note += text_check(src, dst, kind)
                else:
                    r = pdf_check(work)
                    shutil.copyfile(work, dst)
                    first = first_page(name)
                    entry.update(pages=r["pages"], first=first, textless=r["textless"], encrypted=r["encrypted"])
                    if r["pages"]: note.append(f"{r['pages']}쪽")
                    if r["pages"] and r["pages"] > 100: note.append("⚠ 100쪽 초과 — 그림·표를 읽으려면 나눠서")
                    if r["encrypted"]: note.append("암호화(열람 가능 · 제한만)")
                    if r["textless"] is not None:
                        tl = [p + first - 1 for p in r["textless"]]  # 원본 쪽번호로 (범위를 잘라 올린 파일이면 --first 만큼 민다)
                        entry["textless"] = tl
                        if r["pages"] and len(tl) == r["pages"]: note.append("⚠ 전 쪽 글자 층 없음(스캔본)")
                        elif tl: note.append(f"글자 층 없는 쪽 {len(tl)}: " + ("" if first == 1 else "원본 ") + f"p.{short(tl)}")
                        else: note.append("글자 층 전 쪽 있음")
                    if kind == "강의자료": note.append(f"--first {first}")
                    note += r["notes"]
            entry.update(file=out_name, path=os.path.relpath(dst), added=datetime.datetime.now().isoformat(timespec="seconds"))
            if a.force and sig in by_sig: reg = [e for e in reg if e["sig"] != sig]
            reg.append(entry); by_sig[sig] = entry; save_reg(a.reg, reg)
            print(f"✓ 접수  {name} → {entry['path']} · {kind} · " + " · ".join(note))
            cnt["ok"] += 1
        except Reject as ex:
            print(f"✕ 실패  {name}: {ex}"); cnt["fail"] += 1
        except Exception as ex:  # 예상 못 한 오류도 그 파일만 실패로
            print(f"✕ 실패  {name}: {type(ex).__name__}: {ex}"); cnt["fail"] += 1
    n = len(a.files)
    print(f"접수 {cnt['ok']}/{n} · 변환 {cnt['conv']} · 중복 {cnt['dup']} · 실패 {cnt['fail']} · 등록부 {len(reg)}건 → {a.reg}")
    return 1 if cnt["fail"] else 0


def short(pages, k=12):
    s = ",".join(map(str, pages[:k]))
    return s + (f" …(+{len(pages) - k})" if len(pages) > k else "")


def cmd_list(a):
    reg = load_reg(a.reg)
    if not reg: print(f"등록부가 비어 있다: {a.reg}"); return 0
    print("| 파일 | 종류 | 쪽 | --first | 글자 층 없는 쪽 | 원본 | 등록 |\n|---|---|---|---|---|---|---|")
    for e in reg:
        tl = e.get("textless"); tl = "—" if tl is None else (short(tl) if tl else "0")
        print(f"| {e['file']} | {e['kind']} | {e.get('pages') or '—'} | {e.get('first', '—')} | {tl} | {e['original']} | {e['added'][:16]} |")
    return 0


def cmd_sig(a):
    for f in a.files: print(f"{signature(f)}  {os.path.basename(f)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="입력 파일 접수 (Univ AI 업로드 흐름 이식)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("files", nargs="+")
    p.add_argument("--into", default="work/in"); p.add_argument("--reg", default="work/업로드_목록.json")
    p.add_argument("--kind", default="auto", choices=("auto",) + KINDS); p.add_argument("--force", action="store_true")
    p = sub.add_parser("list"); p.add_argument("--reg", default="work/업로드_목록.json")
    p = sub.add_parser("sig"); p.add_argument("files", nargs="+")
    a = ap.parse_args()
    sys.exit({"add": cmd_add, "list": cmd_list, "sig": cmd_sig}[a.cmd](a))
