"""Search the SOFiSTiK manuals (PDF) and the shipped example .dat files.

Manuals: a text index of the English manuals (the *_1.pdf copies; *_0.pdf are German) ships in
manual_index/manuals_en.json.gz, built from the PDFs in C:\\Sofistik workflow with pypdf.  A PDF that
is not in that index (or whose size changed) can be added with index_manual; that index is cached in
%LOCALAPPDATA%\\sofistik-mcp\\manual_cache.
Examples: every .dat inside the shipped <module>.dat folders of examples_folders (settings.json), read on
first use and kept in memory.
"""
from __future__ import annotations

import gzip
import json
import os
import re

from .config import ROOT
from .messages import read_text

SHIPPED_INDEX = os.path.join(ROOT, "manual_index", "manuals_en.json.gz")


def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "sofistik-mcp", "manual_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _terms(query: str) -> list[str]:
    q = query.strip()
    phrases = re.findall(r'"([^"]+)"', q)
    rest = re.sub(r'"[^"]+"', " ", q)
    words = [w for w in re.split(r"\s+", rest) if w]
    return [t.lower() for t in phrases + words]


def _snippet(text: str, term: str, width: int = 160) -> str:
    i = text.lower().find(term)
    if i < 0:
        return ""
    a, b = max(0, i - width), min(len(text), i + len(term) + width)
    return ("..." if a else "") + re.sub(r"\s+", " ", text[a:b]).strip() + ("..." if b < len(text) else "")


class Manuals:
    def __init__(self, folders):
        self.folders = folders
        self.index = {}             # name -> {"size", "pages", "path"}
        self.loaded = False

    def _pdfs(self):
        out: dict = {}
        for f in self.folders:
            if os.path.isdir(f):
                for n in os.listdir(f):
                    if n.lower().endswith(".pdf"):
                        out.setdefault(n, os.path.join(f, n))
        return out

    def load(self):
        if self.loaded:
            return
        if os.path.isfile(SHIPPED_INDEX):
            with gzip.open(SHIPPED_INDEX, "rt", encoding="utf-8") as g:
                data = json.load(g)
            for n, m in data.get("manuals", {}).items():
                self.index[n] = {"size": m.get("size"), "pages": m["pages"], "path": None, "source": "shipped"}
        try:
            cdir = _cache_dir()
            for n in os.listdir(cdir):
                if n.endswith(".json.gz"):
                    with gzip.open(os.path.join(cdir, n), "rt", encoding="utf-8") as g:
                        m = json.load(g)
                    self.index[m["name"]] = {"size": m.get("size"), "pages": m["pages"], "path": None,
                                             "source": "cache"}
        except OSError:
            pass
        self.loaded = True

    def status(self):
        self.load()
        pdfs = self._pdfs()
        rows = []
        for n in sorted(set(pdfs) | set(self.index)):
            p = pdfs.get(n)
            idx = self.index.get(n)
            size = os.path.getsize(p) if p else None
            rows.append({"manual": n, "path": p, "pages": len(idx["pages"]) if idx else None,
                         "indexed": bool(idx), "index_matches_file": bool(idx and size and idx["size"] == size),
                         "language": "German" if n.endswith("_0.pdf") else "English"})
        return rows

    def build(self, name):
        """Index one PDF now (needs pypdf)."""
        from pypdf import PdfReader
        pdfs = self._pdfs()
        if name not in pdfs:
            raise FileNotFoundError(f"{name} not found in {self.folders}")
        p = pdfs[name]
        pages = []
        for pg in PdfReader(p).pages:
            try:
                pages.append(pg.extract_text() or "")
            except Exception:
                pages.append("")
        rec = {"name": name, "size": os.path.getsize(p), "pages": pages}
        with gzip.open(os.path.join(_cache_dir(), name + ".json.gz"), "wt", encoding="utf-8") as g:
            json.dump(rec, g)
        self.load()
        self.index[name] = {"size": rec["size"], "pages": pages, "path": p, "source": "cache"}
        return {"manual": name, "pages": len(pages)}

    def search(self, query, manuals=None, max_hits=15):
        self.load()
        terms = _terms(query)
        if not terms:
            return {"error": "Empty query."}
        names = list(self.index)
        if manuals:
            want = [m.lower().replace(".pdf", "") for m in (manuals if isinstance(manuals, list) else [manuals])]
            names = [n for n in names if any(n.lower().startswith(w) for w in want)]
        hits = []
        for n in names:
            for i, text in enumerate(self.index[n]["pages"]):
                low = text.lower()
                if all(t in low for t in terms):
                    score = sum(low.count(t) for t in terms)
                    hits.append((score, n, i + 1, text))
        hits.sort(key=lambda h: -h[0])
        return {"query": query, "terms": terms, "manuals_searched": len(names), "total_pages_matching": len(hits),
                "hits": [{"manual": n, "pdf_page": p, "score": s, "snippet": _snippet(t, terms[0])}
                         for s, n, p, t in hits[:max_hits]],
                "tip": "Read a hit with read_manual_page(manual, pdf_page)."}

    def page(self, manual, page, count=1):
        self.load()
        name = manual if manual.lower().endswith(".pdf") else manual + ".pdf"
        if name not in self.index:
            cands = [n for n in self.index if n.lower().startswith(manual.lower())]
            if len(cands) == 1:
                name = cands[0]
            else:
                return {"error": f"Manual {manual} not indexed. Indexed: {', '.join(sorted(self.index))}"}
        pages = self.index[name]["pages"]
        page = int(page)
        if not 1 <= page <= len(pages):
            return {"error": f"{name} has pages 1-{len(pages)}."}
        count = max(1, min(int(count), 5))
        return {"manual": name, "pages": f"{page}-{min(len(pages), page + count - 1)}",
                "text": "\n\n--- page break ---\n\n".join(pages[page - 1:page - 1 + count])}


class Examples:
    def __init__(self, folders):
        self.folders = folders
        self.files = None          # path -> text

    def load(self):
        if self.files is not None:
            return
        self.files = {}
        for f in self.folders:
            for dirpath, dirs, names in os.walk(f):
                # only the shipped example folders (<module>.dat\english|deutsch\...), not project work
                dirs[:] = [d for d in dirs
                           if not d.startswith(".") and d.lower() not in ("sofistik-mcp", "__pycache__")]
                rel = os.path.relpath(dirpath, f)
                if rel == ".":
                    dirs[:] = [d for d in dirs if d.lower().endswith(".dat")]
                    continue
                if not rel.split(os.sep)[0].lower().endswith(".dat"):
                    continue
                for n in names:
                    if n.lower().endswith(".dat"):
                        p = os.path.join(dirpath, n)
                        try:
                            if os.path.getsize(p) < 5_000_000:
                                self.files[p] = read_text(p)
                        except OSError:
                            continue

    def search(self, query, max_files=15, prefer="english"):
        self.load()
        assert self.files is not None  # load() always sets it
        terms = _terms(query)
        if not terms:
            return {"error": "Empty query."}
        hits = []
        for p, text in self.files.items():
            low = text.lower()
            if not all(t in low for t in terms):
                continue
            score = sum(low.count(t) for t in terms)
            if prefer and prefer in p.lower():
                score += 1000
            info = " ".join(re.findall(r"^!#!Info\s+Example:\s*(.*)$", text, re.MULTILINE)[:1])
            lines = text.split("\n")
            shown = []
            for i, ln in enumerate(lines):
                if terms[0] in ln.lower():
                    shown.append(f"{i + 1}: {ln.rstrip()[:200]}")
                    if len(shown) >= 3:
                        break
            hits.append((score, p, info, shown))
        hits.sort(key=lambda h: -h[0])
        return {"query": query, "files_searched": len(self.files), "files_matching": len(hits),
                "hits": [{"file": p, "title": info, "lines": shown} for _s, p, info, shown in hits[:max_files]],
                "tip": "Open a hit with read_text_file(path)."}
