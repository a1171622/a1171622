"""docsearch.py: manual index (shipped + built from a PDF) and the example .dat search."""
from __future__ import annotations

import gzip
import json
import os

import pytest

from sofistik_mcp import docsearch


def make_pdf(path, pages):
    """A real PDF with one text line per page (pypdf can write it; extract_text reads it back)."""
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, StreamObject
    w = PdfWriter()
    for txt in pages:
        p = w.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        p[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
        s = StreamObject()
        s.set_data(f"BT /F1 12 Tf 72 720 Td ({txt}) Tj ET".encode("latin-1"))
        p[NameObject("/Contents")] = w._add_object(s)
    with open(path, "wb") as f:
        w.write(f)
    return str(path)


@pytest.fixture
def shipped(tmp_path, monkeypatch):
    """A tiny shipped index and an empty cache folder (LOCALAPPDATA) in tmp_path."""
    idx = tmp_path / "manuals_en.json.gz"
    data = {"manuals": {
        "ase_1.pdf": {"size": 1234, "pages": ["ASE general statics", "GRP group SELECT LTB check LTB",
                                              "nonlinear LTB analysis"]},
        "aqb_1.pdf": {"size": 99, "pages": ["AQB design of sections", "lateral torsional buckling LTB"]},
    }}
    with gzip.open(idx, "wt", encoding="utf-8") as g:
        json.dump(data, g)
    monkeypatch.setattr(docsearch, "SHIPPED_INDEX", str(idx))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    man = tmp_path / "manuals"
    man.mkdir()
    return man


def test_terms():
    assert docsearch._terms('GRP "group select"  LTB') == ["group select", "grp", "ltb"]
    assert docsearch._terms("   ") == []


def test_snippet():
    t = "x" * 300 + " The LTB check " + "y" * 300
    s = docsearch._snippet(t, "ltb", width=10)
    assert s == "...xxxxx The LTB check yyy..."
    assert docsearch._snippet("abc", "zzz") == ""
    assert docsearch._snippet("short ltb", "ltb") == "short ltb"


def test_search_shipped(shipped):
    m = docsearch.Manuals([str(shipped)])
    r = m.search("LTB")
    assert r["terms"] == ["ltb"] and r["manuals_searched"] == 2 and r["total_pages_matching"] == 3
    assert (r["hits"][0]["manual"], r["hits"][0]["pdf_page"], r["hits"][0]["score"]) == ("ase_1.pdf", 2, 2)
    assert {(h["manual"], h["pdf_page"]) for h in r["hits"]} == {("ase_1.pdf", 2), ("ase_1.pdf", 3), ("aqb_1.pdf", 2)}
    assert "LTB" in r["hits"][0]["snippet"] and "read_manual_page" in r["tip"]
    r = m.search('"lateral torsional" ltb')
    assert [(h["manual"], h["pdf_page"]) for h in r["hits"]] == [("aqb_1.pdf", 2)]
    assert m.search("LTB", manuals=["aqb"])["manuals_searched"] == 1
    assert m.search("LTB", manuals="ASE_1.PDF")["manuals_searched"] == 1
    assert len(m.search("LTB", max_hits=1)["hits"]) == 1
    assert m.search("nothinglikethis")["hits"] == []
    assert m.search("  ") == {"error": "Empty query."}


def test_page(shipped):
    m = docsearch.Manuals([])
    assert m.page("aqb_1", 2) == {"manual": "aqb_1.pdf", "pages": "2-2", "text": "lateral torsional buckling LTB"}
    assert m.page("ase", 1, count=9)["pages"] == "1-3"                           # unique prefix, max 5 pages
    r = m.page("ase_1.pdf", 2, count=2)
    assert r["text"] == "GRP group SELECT LTB check LTB\n\n--- page break ---\n\nnonlinear LTB analysis"
    assert "has pages 1-2" in m.page("aqb_1", 3)["error"] and "has pages 1-2" in m.page("aqb_1", 0)["error"]
    e = m.page("a", 1)["error"]                                                # ambiguous prefix
    assert "not indexed" in e and "aqb_1.pdf, ase_1.pdf" in e


def test_status_build_and_cache(shipped, tmp_path):
    make_pdf(shipped / "sofiload_1.pdf", ["SOFiLOAD wind load", "LTB on page two LTB LTB"])
    make_pdf(shipped / "sofiload_0.pdf", ["Windlast"])
    (shipped / "notes.txt").write_text("x")
    m = docsearch.Manuals([str(shipped), str(tmp_path / "missing")])
    st = {r["manual"]: r for r in m.status()}
    assert set(st) == {"ase_1.pdf", "aqb_1.pdf", "sofiload_1.pdf", "sofiload_0.pdf"}
    assert st["sofiload_1.pdf"]["indexed"] is False and st["sofiload_1.pdf"]["path"] == str(shipped / "sofiload_1.pdf")
    assert st["sofiload_0.pdf"]["language"] == "German" and st["sofiload_1.pdf"]["language"] == "English"
    assert st["ase_1.pdf"]["indexed"] is True and st["ase_1.pdf"]["path"] is None
    assert st["ase_1.pdf"]["index_matches_file"] is False and st["ase_1.pdf"]["pages"] == 3

    assert m.build("sofiload_1.pdf") == {"manual": "sofiload_1.pdf", "pages": 2}
    cache = tmp_path / "Local" / "sofistik-mcp" / "manual_cache" / "sofiload_1.pdf.json.gz"
    assert cache.is_file()
    r = m.search("LTB", manuals=["sofiload"])
    assert [(h["manual"], h["pdf_page"], h["score"]) for h in r["hits"]] == [("sofiload_1.pdf", 2, 3)]
    st = {r["manual"]: r for r in m.status()}
    assert st["sofiload_1.pdf"]["indexed"] and st["sofiload_1.pdf"]["index_matches_file"] is True

    fresh = docsearch.Manuals([str(shipped)])                                  # next server start: from cache
    assert fresh.page("sofiload_1", 1)["text"] == "SOFiLOAD wind load"
    fresh.load()
    assert fresh.index["sofiload_1.pdf"]["source"] == "cache" and fresh.index["ase_1.pdf"]["source"] == "shipped"
    with pytest.raises(FileNotFoundError, match="nothere.pdf not found"):
        m.build("nothere.pdf")


def test_build_page_with_unreadable_text(shipped, monkeypatch):
    make_pdf(shipped / "x_1.pdf", ["one", "two"])
    import pypdf
    real = pypdf.PageObject.extract_text
    state = {"n": 0}

    def flaky(self, *a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise ValueError("broken font")
        return real(self, *a, **k)
    monkeypatch.setattr(pypdf.PageObject, "extract_text", flaky)
    m = docsearch.Manuals([str(shipped)])
    assert m.build("x_1.pdf")["pages"] == 2
    assert m.page("x_1", 1)["text"] == "" and m.page("x_1", 2)["text"] == "two"


def test_no_shipped_index_and_unwritable_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(docsearch, "SHIPPED_INDEX", str(tmp_path / "none.json.gz"))
    monkeypatch.setattr(docsearch, "_cache_dir", lambda: (_ for _ in ()).throw(OSError("denied")))
    m = docsearch.Manuals([])
    assert m.search("x")["manuals_searched"] == 0 and m.status() == []


def test_cache_dir_without_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "home") if p == "~" else p)
    assert docsearch._cache_dir() == os.path.join(str(tmp_path / "home"), ".cache", "sofistik-mcp", "manual_cache")
    assert os.path.isdir(docsearch._cache_dir())


def test_real_shipped_index_loads():
    """The committed index covers the English manuals (e.g. bdk_1.pdf) and has page text."""
    if not os.path.isfile(docsearch.SHIPPED_INDEX):
        pytest.skip("manual_index/manuals_en.json.gz not in this checkout")
    m = docsearch.Manuals([])
    m.load()
    assert "bdk_1.pdf" in m.index and all(n.endswith(".pdf") for n in m.index)
    # German copies (_0) only where there is no English one (_1)
    assert all(n[:-6] + "_1.pdf" not in m.index for n in m.index if n.endswith("_0.pdf"))
    assert m.search("LTB", manuals=["bdk"])["hits"]


# ---------------------------------------------------------------- examples

@pytest.fixture
def examples(tmp_path):
    root = tmp_path / "Sofistik workflow"
    files = {
        "ase.dat/english/frame.dat": "!#!Info  Example: portal frame\n+PROG ASE\nSYST PROB TH2\nLC 1\n",
        "ase.dat/deutsch/rahmen.dat": "!#!Info  Example: Rahmen\n+PROG ASE\nSYST PROB TH2\n",
        "sofiload.dat/english/sub/wind.dat": "+PROG SOFILOAD\nWIND 1\nprob th2 here\n",
        "ase.dat/english/readme.txt": "SYST PROB TH2\n",
        "ase.dat/.hidden/x.dat": "SYST PROB TH2\n",
        "wind-loads/mine.dat": "SYST PROB TH2\n",                              # project work, not shipped
        "top.dat": "SYST PROB TH2\n",
        "ase.dat/sofistik-mcp/selftest.dat": "SYST PROB TH2\n",
        "ase.dat/__pycache__/x.dat": "SYST PROB TH2\n",
    }
    for rel, txt in files.items():
        p = root.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    return root


def test_examples_only_module_dat_folders(examples):
    e = docsearch.Examples([str(examples)])
    r = e.search("prob th2")
    files = [h["file"] for h in r["hits"]]
    assert r["files_searched"] == 3 and r["files_matching"] == 3
    assert set(files[:2]) == {str(examples / "ase.dat" / "english" / "frame.dat"),
                              str(examples / "sofiload.dat" / "english" / "sub" / "wind.dat")}
    assert files[2] == str(examples / "ase.dat" / "deutsch" / "rahmen.dat")       # English first
    frame = next(h for h in r["hits"] if h["file"].endswith("frame.dat"))
    assert frame["title"] == "portal frame" and frame["lines"] == ["3: SYST PROB TH2"]
    assert "read_text_file" in r["tip"]


def test_examples_phrase_limits_and_errors(examples, tmp_path):
    e = docsearch.Examples([str(examples), str(tmp_path / "missing")])
    assert [h["file"] for h in e.search('"LC 1"')["hits"]] == [str(examples / "ase.dat" / "english" / "frame.dat")]
    assert len(e.search("th2", max_files=1)["hits"]) == 1
    assert e.search("") == {"error": "Empty query."}
    big = examples / "ase.dat" / "english" / "big.dat"
    big.write_bytes(b"SYST PROB TH2\n" + b"x" * 5_000_000)
    assert docsearch.Examples([str(examples)]).search("th2")["files_searched"] == 3   # >5 MB skipped


def test_examples_shown_lines_capped(examples):
    p = examples / "ase.dat" / "english" / "many.dat"
    p.write_text("".join(f"GRP {i}\n" for i in range(10)))
    h = docsearch.Examples([str(examples)]).search("grp")["hits"][0]
    assert h["lines"] == ["1: GRP 0", "2: GRP 1", "3: GRP 2"] and h["title"] == ""
