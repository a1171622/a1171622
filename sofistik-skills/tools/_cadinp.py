"""A small static CADINP interpreter (stdlib only) for the proof tools.

It reads a SOFiSTiK .dat the way CADINP would for the things the checks need:
program blocks (+PROG / -PROG / PROG ... END), comments ($ and !), records split at ';',
variables (STO#, LET#, DEL#, RCL#; arrays 'LET#GL 2,3,4' indexed #GL(0)), expressions
(+ - * / ** ^, SQR SIN COS TAN ATN EXP LOG ABS MAX MIN IIF DIV MOD POW, comparisons),
IF / ELSE / ENDIF and LOOP / ENDLOOP, generation lists '(101 130 1)', and comma lists.

Variable scope (CADINP manual cadinp_1.pdf pdf-page 12-13 (1-4/1-5): "LET# (only valid within current program)
or STO# (value will be saved to database)" ... "can be used by all other programs accessing the database"):
every program block starts with the STO# values saved so far; LET# lives in its block only.

What it extracts (Model):
  SOFiLOAD  load cases (last definition wins), COPY NO/FACT (evaluated per loop pass), load records, FACD
  ASE       SYST PROB / PLC, LC lists, EIGE n BUCK LC m
  MAXIMA    COMB ... BASE b, LC NO references
  BDK       CTRL ... LCST, the LC list of each CTRL group, MEMB SLN/ID, CONT, CVL REF STRT S
  AQB       LC lists, BEAM TYPE, COMB ... LCST
  SOFiMSHC  SLN NO GRP STYP SNO       AQUA  SECT / PROF names, STEE grades
Inferred items are marked [I] in comments.  Unknown syntax is reported, never silently skipped.
"""
from __future__ import annotations

import math
import re

OPERATOR_WORDS = ("DIV", "SIN", "COS", "SQR", "TAN", "EXP", "LOG", "ABS", "MOD", "ATN", "POW")
LOADKEYS = {"AREA", "LINE", "BEAM", "NODE", "QUAD", "POIN", "BRIC", "TRUS", "CABL", "SPRI", "ELEM", "VOLU",
            "FREE", "PLAN", "BOUN"}
TEXTKEYS = {"HEAD", "PAGE", "TXB", "TXE", "TEXT", "<TEXT>", "</TEXT>", "ECHO"}
TEXTITEMS = {"TITL", "TITLE", "TXT", "BEZ"}
CONTROL = {"IF", "ELSE", "ELSEIF", "ENDIF", "LOOP", "ENDLOOP"}


class EvalError(Exception):
    pass


class Undefined(EvalError):
    pass


# ------------------------------------------------------------------------------------------------
# reading
# ------------------------------------------------------------------------------------------------

def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    nul = raw.count(b"\x00")
    cr = raw.count(b"\r")
    raw = raw.replace(b"\x00", b"").replace(b"\r", b"")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return text, {"nul_bytes_removed": nul, "cr_removed": cr}


# ------------------------------------------------------------------------------------------------
# #INCLUDE expansion (shared by dat_lint.py and expand_master.py)
# ------------------------------------------------------------------------------------------------
# The server's spelling (sofistik-mcp/sofistik_mcp/solver.py:74 INCLUDE_RE): #INCLUDE also abbreviated to
# #INCL..., and +APPLY / APPLY.  Files are looked for as <name> and <name>.dat, next to the including file
# and next to the main .dat (solver.py:289-297), three levels deep (solver.py:56 INCLUDE_DEPTH = 3).
INCLUDE_LINE_RE = re.compile(r"^\s*#\s*incl\w*\s+(.+)$", re.IGNORECASE)
APPLY_LINE_RE = re.compile(r"^\s*[+*]?\s*appl\w*\s+(.+)$", re.IGNORECASE)
DEFINE_LINE_RE = re.compile(r"^\s*#\s*define\s+([^\s=]+)\s*(=.*)?$", re.IGNORECASE)
INCLUDE_DEPTH = 3


def include_name(arg):
    """The file name of an #INCLUDE argument, cut at a comment like the server does (solver.py:271)."""
    return re.split(r"\s\$(?:\s|$)|\s//|[;!]", arg)[0].strip().strip("\"'").strip()


def read_sources_tsv(path):
    """W/sources.tsv: '<PC file name><TAB><cloud path>' per line -> {name: path} (insertion order kept)."""
    mp = {}
    for no, l in enumerate(open(path, encoding="utf-8").read().replace("\r", "").split("\n"), 1):
        if not l.strip():
            continue
        if "\t" not in l:
            raise ValueError(f"{path}:{no}: no TAB between PC name and cloud path: {l!r}")
        k, v = l.split("\t", 1)
        mp[k.strip()] = v.strip()
    return mp


def _lookup(mp, name):
    if not mp:
        return None
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    for cand in (name, base, name + ".dat", base + ".dat"):
        if cand in mp:
            return mp[cand]
    low = {k.lower(): v for k, v in mp.items()}
    for cand in (name, base, name + ".dat", base + ".dat"):
        if cand.lower() in low:
            return low[cand.lower()]
    return None


def expand_includes(path, sources=None, depth=INCLUDE_DEPTH, recurse=True, strict_master=False):
    """Expand #INCLUDE lines of `path` in memory.

    sources: {PC name: cloud path} (sources.tsv) looked up first; otherwise <name> / <name>.dat next to the
    including file and next to the main file (the server's rule).  recurse=False expands one level only (the
    old inline script E).  Returns dict(lines, origin [(file, line)], includes [(name, path)], missing
    [(file, line, name)], nested [(file, line, name)], apply [(file, line, text)], too_deep [...]).
    A #INCLUDE of a #DEFINE block name is kept as written (not a file)."""
    import os
    main_dir = os.path.dirname(os.path.abspath(path))
    out = {"lines": [], "origin": [], "includes": [], "missing": [], "nested": [], "apply": [], "too_deep": [],
           "read_info": {}}
    blocks = set()

    def read(p, strict):
        if strict:
            t = open(p, encoding="utf-8").read().replace("\r", "")
            return t, {"nul_bytes_removed": 0, "cr_removed": 0}
        return read_text(p)

    def walk(p, level, stack):
        text, info = read(p, strict_master and level == depth)
        if level == depth:
            out["read_info"] = info
        lines = text.rstrip("\n").split("\n")
        for no, l in enumerate(lines, 1):
            code = strip_comment(l) if not l.lstrip().startswith("#") else l
            m = DEFINE_LINE_RE.match(l)
            if m and not m.group(2):
                blocks.add(m.group(1).casefold())
            m = INCLUDE_LINE_RE.match(l)
            if m:
                name = include_name(m.group(1))
                if not name or name.casefold() in blocks:
                    out["lines"].append(l)
                    out["origin"].append((p, no))
                    continue
                if level < depth:
                    out["nested"].append((p, no, name))
                if level <= 0 or (not recurse and level < depth):
                    if level <= 0:
                        out["too_deep"].append((p, no, name))
                    out["lines"].append(l)
                    out["origin"].append((p, no))
                    continue
                tgt = _lookup(sources, name)
                if tgt is None:
                    for d in (os.path.dirname(os.path.abspath(p)), main_dir):
                        for c in (name, name + ".dat") if not name.lower().endswith(".dat") else (name,):
                            cp = c if os.path.isabs(c) else os.path.join(d, c)
                            if os.path.exists(cp):
                                tgt = cp
                                break
                        if tgt:
                            break
                if tgt is None or not os.path.exists(tgt):
                    out["missing"].append((p, no, name if tgt is None else f"{name} (= {tgt}, not found)"))
                    out["lines"].append(l)
                    out["origin"].append((p, no))
                    continue
                key = os.path.realpath(tgt)
                if key in stack:
                    out["missing"].append((p, no, f"{name} (include cycle)"))
                    continue
                out["includes"].append((name, tgt))
                walk(tgt, level - 1, stack | {key})
                continue
            if APPLY_LINE_RE.match(code or "") and not (code or "").lstrip().startswith("-"):
                out["apply"].append((p, no, l.strip()[:80]))
            out["lines"].append(l)
            out["origin"].append((p, no))

    walk(path, depth, {os.path.realpath(path)})
    return out


def strip_comment(line):
    """Code part of a physical line: cut at '!' or at a '$' that starts a comment (not '$(')."""
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch == "!":
            return line[:i]
        elif ch == "$":
            nxt = line[i + 1:i + 2]
            if nxt == "(":
                continue
            if i == 0 or line[i - 1] in " \t":
                return line[:i]
    return line


def split_records(code):
    out, cur, q, depth = [], [], None, 0
    for ch in code:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return [r for r in out if r.strip()]


def tokenize(rec):
    toks, cur, q, depth = [], [], None, 0
    for ch in rec.strip():
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
            cur.append(ch)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in " \t" and depth == 0:
            if cur:
                toks.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        toks.append("".join(cur))
    # "A , B" -> "A,B": join tokens around stray commas (comma lists written with blanks)
    j = []
    for t in toks:
        if j and (t.startswith(",") or j[-1].endswith(",")):
            j[-1] += t
        else:
            j.append(t)
    return j


class Rec:
    __slots__ = ("line", "text", "toks", "key")

    def __init__(self, line, text):
        self.line = line
        self.text = text.strip()
        self.toks = tokenize(text)
        self.key = self.toks[0].upper() if self.toks else ""


class Block:
    def __init__(self, prog, enabled, line, head):
        self.prog = prog
        self.enabled = enabled
        self.line = line
        self.head = head
        self.recs = []


# ------------------------------------------------------------------------------------------------
# expressions
# ------------------------------------------------------------------------------------------------

_TOK = re.compile(r"\s*(?:(\d+\.?\d*(?:[Ee][-+]?\d+)?|\.\d+(?:[Ee][-+]?\d+)?)|(#[A-Za-z_][A-Za-z0-9_]*)|"
                  r"([A-Za-z_][A-Za-z0-9_]*)|(\*\*|<=|>=|==|<>|!=|[-+*/^(),<>=&|]))")
_UNIT = re.compile(r"\[[^\]]*\]")


def _lex(s):
    s = _UNIT.sub("", s)
    pos, out = 0, []
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            if s[pos:].strip() == "":
                break
            raise EvalError(f"cannot read expression at '{s[pos:pos + 12]}'")
        pos = m.end()
        if m.group(1):
            out.append(("n", float(m.group(1))))
        elif m.group(2):
            out.append(("v", m.group(2)[1:].upper()))
        elif m.group(3):
            out.append(("f", m.group(3).upper()))
        else:
            out.append(("o", m.group(4)))
    return out


def _deg(f):
    return lambda x: f(math.radians(x))   # [I] CADINP trigonometry in degrees (default UNIT setting)


FUNCS = {
    "SQR": math.sqrt, "SQRT": math.sqrt, "ABS": abs, "EXP": math.exp, "LOG": math.log,
    "SIN": _deg(math.sin), "COS": _deg(math.cos), "TAN": _deg(math.tan),
    "ATN": lambda x: math.degrees(math.atan(x)),
    "MAX": max, "MIN": min, "DIV": lambda a, b: float(int(a // b)), "MOD": lambda a, b: math.fmod(a, b),
    "POW": lambda a, b: a ** b, "INT": lambda x: float(int(x)),
    "IIF": lambda c, a, b: a if c else b,
}


class _P:
    def __init__(self, toks, env):
        self.t, self.i, self.env = toks, 0, env

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        k, v = self.peek()
        if k is None or (kind and k != kind) or (val is not None and v != val):
            raise EvalError(f"expected {val or kind}, got {v!r}")
        self.i += 1
        return v

    def parse(self):
        v = self.logic()
        if self.i != len(self.t):
            raise EvalError(f"unexpected {self.t[self.i][1]!r}")
        return v

    def logic(self):
        v = self.comp()
        while self.peek() in (("o", "&"), ("o", "|")):
            op = self.take()
            w = self.comp()
            v = float(bool(v) and bool(w)) if op == "&" else float(bool(v) or bool(w))
        return v

    def comp(self):
        v = self.add()
        k, op = self.peek()
        if k == "o" and op in ("<", ">", "<=", ">=", "==", "=", "<>", "!="):
            self.i += 1
            w = self.add()
            return float({"<": v < w, ">": v > w, "<=": v <= w, ">=": v >= w, "==": v == w, "=": v == w,
                          "<>": v != w, "!=": v != w}[op])
        return v

    def add(self):
        v = self.mul()
        while self.peek() in (("o", "+"), ("o", "-")):
            op = self.take()
            w = self.mul()
            v = v + w if op == "+" else v - w
        return v

    def mul(self):
        v = self.unary()
        while self.peek() in (("o", "*"), ("o", "/")):
            op = self.take()
            w = self.unary()
            if op == "/" and w == 0:
                raise EvalError("division by zero")
            v = v * w if op == "*" else v / w
        return v

    def unary(self):
        if self.peek() == ("o", "-"):
            self.i += 1
            return -self.unary()
        if self.peek() == ("o", "+"):
            self.i += 1
            return self.unary()
        return self.power()

    def power(self):
        v = self.atom()
        if self.peek() in (("o", "**"), ("o", "^")):
            self.i += 1
            w = self.unary()
            v = v ** w
        return v

    def atom(self):
        k, v = self.peek()
        if k == "n":
            self.i += 1
            return v
        if k == "v":
            self.i += 1
            if v not in self.env:
                raise Undefined(f"#{v} is not defined")
            val = self.env[v]
            if self.peek() == ("o", "("):
                self.i += 1
                idx = self.logic()
                self.take("o", ")")
                if not isinstance(val, list):
                    if int(idx) == 0:
                        return val
                    raise EvalError(f"#{v} is not an array")
                if not 0 <= int(idx) < len(val):
                    raise EvalError(f"#{v}({int(idx)}) outside the array (length {len(val)})")
                return val[int(idx)]
            if isinstance(val, list):
                return val[0]
            if isinstance(val, str):
                raise EvalError(f"#{v} is text")
            return val
        if k == "f":
            self.i += 1
            if v not in FUNCS:
                raise EvalError(f"unknown function {v}")
            self.take("o", "(")
            args = [self.logic()]
            while self.peek() == ("o", ","):
                self.i += 1
                args.append(self.logic())
            self.take("o", ")")
            try:
                return float(FUNCS[v](*args))
            except (ValueError, TypeError, ZeroDivisionError) as e:
                raise EvalError(f"{v}{tuple(args)}: {e}")
        if (k, v) == ("o", "("):
            self.i += 1
            r = self.logic()
            self.take("o", ")")
            return r
        raise EvalError(f"unexpected {v!r}")


def evaluate(expr, env):
    return _P(_lex(expr), env).parse()


_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([Ee][-+]?\d+)?(\[[^\]]*\])?$")
_GEN = re.compile(r"^\(\s*([^\s()]+)\s+([^\s()]+)(?:\s+([^\s()]+))?\s*\)$")


def is_literal_number(tok):
    return bool(_NUM.match(tok))


def value_of(tok, env):
    """Token -> float | str | list.  Raises EvalError/Undefined for a bad expression."""
    if not tok:
        return tok
    if tok[0] in "'\"":
        return tok.strip("'\"")
    if _NUM.match(tok):
        return float(_UNIT.sub("", tok))
    m = _GEN.match(tok)
    if m:
        a = evaluate(m.group(1), env)
        b = evaluate(m.group(2), env)
        st = evaluate(m.group(3), env) if m.group(3) else 1.0
        if st == 0:
            raise EvalError("generation step 0")
        n = int(round((b - a) / st)) + 1
        return [a + k * st for k in range(max(0, n))]
    if "," in tok and not tok.startswith(("MAX(", "MIN(", "IIF(", "POW(", "DIV(", "MOD(")):
        parts = _split_top(tok, ",")
        if len(parts) > 1:
            return [value_of(p, env) for p in parts if p != ""]
    if "#" in tok:
        return evaluate(tok, env)
    if re.search(r"[-+*/^()]", tok):
        try:
            return evaluate(tok, env)
        except EvalError:
            return tok          # a literal such as GAM-S1 or (D)
    return tok   # a literal word such as FIX, AUTO, PG


def _split_top(s, sep):
    out, cur, d = [], [], 0
    for ch in s:
        if ch == "(":
            d += 1
        elif ch == ")":
            d -= 1
        if ch == sep and d == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def flat_numbers(v):
    if isinstance(v, list):
        out = []
        for x in v:
            out.extend(flat_numbers(x))
        return out
    if isinstance(v, float):
        return [v]
    return []


# ------------------------------------------------------------------------------------------------
# events and execution
# ------------------------------------------------------------------------------------------------

class Ev:
    __slots__ = ("block", "line", "key", "toks", "vals", "text")

    def __init__(self, block, rec, vals):
        self.block = block
        self.line = rec.line
        self.key = rec.key
        self.toks = rec.toks
        self.vals = vals
        self.text = rec.text

    def kv(self, order=(), keywords=()):
        """{ITEM: (value, raw token)} from keyword and positional items after the record name."""
        kw = {k.upper() for k in tuple(order) + tuple(keywords)}
        out, pos, i = {}, 0, 1
        n = len(self.toks)
        while i < n:
            t = self.toks[i].upper()
            if t in kw and i + 1 < n and t not in out:
                out[t] = (self.vals[i + 1], self.toks[i + 1])
                i += 2
                continue
            while pos < len(order) and order[pos].upper() in out:
                pos += 1
            if pos < len(order):
                out[order[pos].upper()] = (self.vals[i], self.toks[i])
                pos += 1
            i += 1
        return out


class Dat:
    MAX_STEPS = 5_000_000

    def __init__(self, text, name=""):
        self.name = name
        self.lines = text.split("\n")
        self.blocks = []
        self.errors = []          # (line, message): evaluation / syntax problems
        self.undefined = []       # (line, message)
        self.events = []
        self.store = {}           # STO# values (database)
        self.stos = []            # (line, name, raw)
        self.lets = []            # (line, name, raw)
        self._split()
        self._run()

    @classmethod
    def from_file(cls, path):
        text, info = read_text(path)
        d = cls(text, path)
        d.read_info = info
        return d

    # -- structure
    def _split(self):
        cur = Block("PRE", True, 0, "")
        self.blocks.append(cur)
        for no, raw in enumerate(self.lines, 1):
            code = strip_comment(raw)
            if not code.strip():
                continue
            for r in split_records(code):
                rec = Rec(no, r)
                if not rec.toks:
                    continue
                k = rec.key
                if re.fullmatch(r"[+\-]?PROG", k):
                    prog = rec.toks[1].upper() if len(rec.toks) > 1 else "?"
                    cur = Block(prog, not k.startswith("-"), no, rec.text)
                    self.blocks.append(cur)
                    continue
                if k == "END" and cur.prog not in ("PRE", "GAP"):
                    cur = Block("GAP", True, no, "")
                    self.blocks.append(cur)
                    continue
                cur.recs.append(rec)

    def _structure(self, recs, bi):
        jumps, stack = {}, []
        for i, r in enumerate(recs):
            k = r.key
            if k == "IF":
                stack.append(("IF", i, None))
            elif k == "ELSEIF":
                self.errors.append((r.line, "ELSEIF is not supported by the static reader"))
            elif k == "ELSE":
                if not stack or stack[-1][0] != "IF":
                    self.errors.append((r.line, "ELSE without IF"))
                    continue
                t, a, _ = stack.pop()
                stack.append(("IF", a, i))
            elif k == "ENDIF":
                if not stack or stack[-1][0] != "IF":
                    self.errors.append((r.line, "ENDIF without IF"))
                    continue
                _, a, e = stack.pop()
                jumps[a] = (e, i)
                if e is not None:
                    jumps[e] = (None, i)
            elif re.fullmatch(r"LOOP(#\w+)?", k):
                stack.append(("LOOP", i, None))
            elif k == "ENDLOOP":
                if not stack or stack[-1][0] != "LOOP":
                    self.errors.append((r.line, "ENDLOOP without LOOP"))
                    continue
                _, a, _ = stack.pop()
                jumps[a] = i
                jumps[i] = a
        for t, a, _ in stack:
            self.errors.append((recs[a].line, f"{t} without END{t}"))
        return jumps

    # -- execution
    def _run(self):
        for bi, b in enumerate(self.blocks):
            if not b.enabled or b.prog == "GAP":
                continue
            env = dict(self.store)
            self._exec(b, bi, env)

    def _val(self, tok, env, line):
        try:
            return value_of(tok, env)
        except Undefined as e:
            self.undefined.append((line, str(e)))
            return None
        except EvalError as e:
            self.errors.append((line, f"{e} in '{tok}'"))
            return None

    def _cond(self, toks, env, line):
        expr = " ".join(toks[1:])
        if not expr:
            self.errors.append((line, "IF without condition"))
            return False
        try:
            return bool(evaluate(expr, env))
        except Undefined as e:
            self.undefined.append((line, str(e)))
        except EvalError as e:
            self.errors.append((line, f"{e} in IF {expr}"))
        return False

    def _assign(self, rec, env, kind):
        name = rec.toks[0].split("#", 1)[1].upper() if "#" in rec.toks[0] else ""
        rest = rec.text[len(rec.toks[0]):].strip()
        m = re.match(r"^([A-Za-z0-9_]+)(\(.*?\))?\s*=?\s*(.*)$", rec.toks[0].split("#", 1)[1]) if name else None
        if m and m.group(3):           # LET#A=5 written without a blank
            name = m.group(1).upper()
            rest = (m.group(3) + " " + rest).strip()
        elif m:
            name = m.group(1).upper()
        idx = None
        if m and m.group(2):
            try:
                idx = int(evaluate(m.group(2)[1:-1], env))
            except EvalError as e:
                self.errors.append((rec.line, str(e)))
                return
        if rest.startswith("="):
            rest = rest[1:].strip()
        (self.stos if kind == "STO" else self.lets).append((rec.line, name, rest))
        if not rest:
            if kind == "STO" and name in env:      # STO#name alone saves the current value
                self.store[name] = env[name]
            return
        parts = [p.strip() for p in _split_top(rest, ",")]
        vals = []
        for p in parts:
            if not p:
                continue
            tok = p.split()[0] if len(p.split()) > 1 and not p.startswith(("'", '"')) else p
            v = self._val(tok, env, rec.line)
            vals.append(v)
        if any(v is None for v in vals):
            return
        val = vals[0] if len(vals) == 1 else vals
        if idx is not None:
            arr = env.get(name)
            arr = list(arr) if isinstance(arr, list) else ([arr] if arr is not None else [])
            while len(arr) <= idx:
                arr.append(0.0)
            arr[idx] = val
            val = arr
        env[name] = val
        if kind == "STO":
            self.store[name] = val

    def _exec(self, b, bi, env):
        recs = b.recs
        jumps = self._structure(recs, bi)
        loops = []
        pc, steps = 0, 0
        while pc < len(recs):
            steps += 1
            if steps > self.MAX_STEPS:
                self.errors.append((recs[pc].line, "too many steps (endless loop?)"))
                return
            r = recs[pc]
            k = r.key
            if k == "IF":
                j = jumps.get(pc)
                if j is None:
                    pc += 1
                    continue
                if self._cond(r.toks, env, r.line):
                    pc += 1
                else:
                    pc = (j[0] + 1) if j[0] is not None else j[1] + 1
                continue
            if k == "ELSE":
                j = jumps.get(pc)
                pc = (j[1] + 1) if j else pc + 1
                continue
            if k in ("ENDIF", "ELSEIF"):
                pc += 1
                continue
            if re.fullmatch(r"LOOP(#\w+)?", k):
                end = jumps.get(pc)
                var = r.toks[0].split("#", 1)[1].upper() if "#" in r.toks[0] else None
                cnt_tok = r.toks[1] if len(r.toks) > 1 else None
                count = None
                if cnt_tok is None:
                    self.errors.append((r.line, "LOOP without count (open loop not supported)"))
                    count = 0
                elif re.fullmatch(r"[A-Za-z_]\w*", cnt_tok) and cnt_tok.upper() in env:
                    v = env[cnt_tok.upper()]
                    count = len(v) if isinstance(v, list) else 1
                else:
                    v = self._val(cnt_tok, env, r.line)
                    count = int(v) if isinstance(v, float) else 0
                if end is None or count <= 0:
                    pc = (end + 1) if end is not None else pc + 1
                    continue
                loops.append([var, count, 0, pc + 1])
                if var:
                    env[var] = 0.0
                pc += 1
                continue
            if k == "ENDLOOP":
                if not loops:
                    pc += 1
                    continue
                fr = loops[-1]
                fr[2] += 1
                if fr[2] < fr[1]:
                    if fr[0]:
                        env[fr[0]] = float(fr[2])
                    pc = fr[3]
                else:
                    loops.pop()
                    pc += 1
                continue
            if k.startswith(("STO#", "LET#")):
                self._assign(r, env, k[:3])
                pc += 1
                continue
            if k.startswith("DEL#"):
                n = k[4:].upper()
                env.pop(n, None)
                self.store.pop(n, None)
                pc += 1
                continue
            if k.startswith("RCL#"):
                n = k[4:].upper()
                if n == "ALL":
                    env.update(self.store)
                elif n in self.store:
                    env[n] = self.store[n]
                pc += 1
                continue
            if k.startswith(("PRT#", "@", "#DEFINE", "#ENDDEF", "#INCLUDE", "<")):
                pc += 1
                continue
            if k in TEXTKEYS:
                vals = list(r.toks)
            else:
                vals = [r.toks[0]]
                for i in range(1, len(r.toks)):
                    t = r.toks[i]
                    if r.toks[i - 1].upper() in TEXTITEMS:
                        vals.append(t.strip("'\""))
                    else:
                        vals.append(self._val(t, env, r.line))
            self.events.append(Ev(bi, r, vals))
            pc += 1


# ------------------------------------------------------------------------------------------------
# model
# ------------------------------------------------------------------------------------------------

def _int(v):
    if isinstance(v, float) and abs(v - round(v)) < 1e-9:
        return int(round(v))
    return None


def _ints(v):
    return [int(round(x)) for x in flat_numbers(v) if abs(x - round(x)) < 1e-9]


class LoadCase:
    def __init__(self, no, line, block):
        self.no = no
        self.line = line
        self.block = block
        self.type = None
        self.title = ""
        self.facd = 0.0
        self.facd_raw = None
        self.copies = []      # (src, fact, line, raw_no, raw_fact)
        self.loads = []       # (line, text, toks)
        self.superseded = []  # earlier definitions (line numbers)


class Model:
    def __init__(self, dat: Dat):
        self.dat = dat
        self.lcs = {}
        self.superseded_lines = set()   # load records of LC definitions later replaced
        self.ase = []        # dicts: block, line, prob, plc, lcs, eige
        self.maxima = []     # dicts: block, line, comb, base
        self.bdk = []        # dicts: block, line, groups=[{ctrl_line, lcst, lcs, membs=[...]}]
        self.aqb = []        # dicts: block, line, lcs, beam_type, lcst
        self.refs = []       # (lc, line, where)
        self.slns = {}       # sln -> {grp, sno, styp, line}
        self.sections = {}   # nr -> name
        self.materials = {}  # nr -> grade text
        self.section_mno = {}  # section nr -> material nr (PROF / SECT MNO)
        self.copy_notes = []
        self._build()

    def _build(self):
        d = self.dat
        cur_lc = None
        cur_blk = None
        ase = maxi = bdk = aqb = None
        grp = None
        sect = None
        for ev in d.events:
            b = d.blocks[ev.block]
            prog = b.prog
            if ev.block != cur_blk:
                cur_blk = ev.block
                cur_lc = None
                ase = maxi = bdk = aqb = None
                grp = None
                if prog == "ASE":
                    ase = {"block": ev.block, "line": b.line, "prob": "LINE", "plc": None, "lcs": [],
                           "eige": [], "head": b.head}
                    self.ase.append(ase)
                elif prog == "MAXIMA":
                    maxi = {"block": ev.block, "line": b.line, "combs": []}
                    self.maxima.append(maxi)
                elif prog == "BDK":
                    bdk = {"block": ev.block, "line": b.line, "groups": [], "head": b.head}
                    self.bdk.append(bdk)
                elif prog == "AQB":
                    aqb = {"block": ev.block, "line": b.line, "lcs": [], "beam": [], "lcst": [], "head": b.head}
                    self.aqb.append(aqb)
            k = ev.key
            if prog == "SOFILOAD":
                if k == "LC":
                    kv = ev.kv(("NO", "TYPE", "FACT", "FACD"), ("TITL", "DLX", "DLY", "DLZ"))
                    no = _int(kv.get("NO", (None,))[0])
                    if no is None:
                        d.errors.append((ev.line, f"LC number not readable: {ev.text[:60]}"))
                        cur_lc = None
                        continue
                    lc = LoadCase(no, ev.line, ev.block)
                    old = self.lcs.get(no)
                    if old is not None:
                        lc.superseded = old.superseded + [old.line]
                        self.superseded_lines.update(x[0] for x in old.loads)
                        self.superseded_lines.update(x[2] for x in old.copies)
                    t = kv.get("TYPE")
                    lc.type = t[0] if t else None
                    ti = kv.get("TITL")
                    lc.title = ti[0] if ti and isinstance(ti[0], str) else ""
                    fd = kv.get("FACD")
                    if fd:
                        lc.facd_raw = fd[1]
                        lc.facd = fd[0] if isinstance(fd[0], float) else 0.0
                    self.lcs[no] = lc
                    cur_lc = lc
                elif k == "COPY":
                    kv = ev.kv(("NO", "FACT"), ())
                    if cur_lc is None:
                        d.errors.append((ev.line, "COPY outside a load case"))
                        continue
                    no_v, no_raw = kv.get("NO", (None, None))
                    f_v, f_raw = kv.get("FACT", (1.0, None))
                    src = _int(no_v)
                    if src is None or not isinstance(f_v, float):
                        self.copy_notes.append((ev.line, f"COPY not resolvable statically: {ev.text[:80]}"))
                        cur_lc.copies.append((None, None, ev.line, no_raw, f_raw))
                        continue
                    cur_lc.copies.append((src, f_v, ev.line, no_raw, f_raw))
                    self.refs.append((src, ev.line, "SOFILOAD COPY"))
                elif k in LOADKEYS and cur_lc is not None:
                    cur_lc.loads.append((ev.line, ev.text, ev.toks, ev.vals))
                elif k in ("ACT", "HEAD", "UNIT", "LAR", "GRP", "PAGE", "ECHO", "CTRL", "SYST", "FUNC", "TXB",
                           "TXE"):
                    if k == "ACT":
                        cur_lc = None
            elif prog == "ASE" and ase is not None:
                if k == "SYST":
                    kv = ev.kv(("TYPE",), ("PROB", "PLC", "ITER", "TOL", "FMAX", "NMAT", "STOR"))
                    if "PROB" in kv and isinstance(kv["PROB"][0], str):
                        ase["prob"] = kv["PROB"][0].upper()
                    if "PLC" in kv:
                        ase["plc"] = _int(kv["PLC"][0])
                        if ase["plc"]:
                            self.refs.append((ase["plc"], ev.line, "ASE SYST PLC"))
                elif k == "LC":
                    kv = ev.kv(("NO", "FACT"), ("DLX", "DLY", "DLZ", "TITL", "TYPE"))
                    v = kv.get("NO", (None, None))[0]
                    for n in _ints(v):
                        ase["lcs"].append(n)
                        self.refs.append((n, ev.line, f"ASE {ase['prob']}"))
                elif k == "EIGE":
                    kv = ev.kv(("NEIG", "ETYP", "NITE", "MITE", "LMIN", "LC"), ("OPT",))
                    n = _int(kv.get("NEIG", (None,))[0]) or 0
                    first = _int(kv.get("LC", (2001.0,))[0]) or 2001
                    et = kv.get("ETYP", ("LANC",))[0]
                    ase["eige"].append({"line": ev.line, "n": n, "first": first, "etyp": str(et).upper()})
            elif prog == "MAXIMA" and maxi is not None:
                if k == "COMB":
                    kv = ev.kv(("NO", "EXTR", "TYPE"), ("BASE", "TITL", "LCST"))
                    base = _int(kv.get("BASE", (None,))[0])
                    maxi["combs"].append({"line": ev.line, "no": _int(kv.get("NO", (None,))[0]), "base": base})
                elif k == "LC":
                    kv = ev.kv(("NO",), ("TYPE", "FACT"))
                    for n in _ints(kv.get("NO", (None,))[0]):
                        self.refs.append((n, ev.line, "MAXIMA LC"))
            elif prog == "BDK" and bdk is not None:
                if k == "CTRL":
                    kv = ev.kv(("OPT",), ("LCST", "SCL", "CURV", "MTHD", "SWY", "SWZ", "LTB", "TAB", "BETA", "LLT0"))
                    lcst = _int(kv["LCST"][0]) if "LCST" in kv else None
                    grp = {"ctrl_line": ev.line, "lcst": lcst, "lcs": [], "membs": [], "text": ev.text}
                    bdk["groups"].append(grp)
                elif k == "LC":
                    kv = ev.kv(("NO",), ("TYPE", "FACT"))
                    lcs = _ints(kv.get("NO", (None,))[0])
                    if grp is None:
                        grp = {"ctrl_line": None, "lcst": None, "lcs": [], "membs": [], "text": ""}
                        bdk["groups"].append(grp)
                    grp["lcs"].extend(lcs)
                    for n in lcs:
                        self.refs.append((n, ev.line, "BDK LC"))
                elif k == "MEMB":
                    kv = ev.kv(("SLN",), ("TYPE", "ID", "SKY", "SKZ", "NO", "GRP"))
                    sln = _int(kv.get("SLN", (None,))[0])
                    mid = _int(kv["ID"][0]) if "ID" in kv else sln
                    if grp is None:
                        grp = {"ctrl_line": None, "lcst": None, "lcs": [], "membs": [], "text": ""}
                        bdk["groups"].append(grp)
                    grp["membs"].append({"line": ev.line, "sln": sln, "id": mid, "cont": [], "cvl": [],
                                         "lcs": list(grp["lcs"])})
                elif k == "CONT":
                    kv = ev.kv(("SLN",), ())
                    s = _int(kv.get("SLN", (None,))[0])
                    if grp and grp["membs"] and s is not None:
                        grp["membs"][-1]["cont"].append(s)
                elif k == "CVL":
                    kv = ev.kv(("REF",), ("STRT", "S", "CY", "CZ", "DX", "EZ", "HDIV"))
                    if grp is not None:
                        grp.setdefault("pending_cvl", []).append(
                            {k2: (v[0] if not isinstance(v[0], list) else v[0]) for k2, v in kv.items()})
            elif prog == "AQB" and aqb is not None:
                if k == "LC":
                    kv = ev.kv(("NO", "TYPE"), ("CST", "REF", "TITL"))
                    for n in _ints(kv.get("NO", (None,))[0]):
                        aqb["lcs"].append(n)
                        self.refs.append((n, ev.line, "AQB LC"))
                elif k == "BEAM":
                    aqb["beam"].append(ev.text)
                elif k == "COMB":
                    kv = ev.kv(("EXTR",), ("LCST",))
                    if "LCST" in kv:
                        aqb["lcst"].append(_int(kv["LCST"][0]))
            elif prog in ("SOFIMSHC", "SOFIMSHB"):
                if k == "SLN":
                    kv = ev.kv(("NO",), ("GRP", "STYP", "SNO", "SNOE", "NPA", "NPE", "TITL"))
                    no = _int(kv.get("NO", (None,))[0])
                    if no is not None:
                        g = kv.get("GRP", (None,))[0]
                        sno = kv.get("SNO", (None,))[0]
                        self.slns[no] = {"grp": _int(g) if isinstance(g, float) else g,
                                         "sno": _int(sno) if isinstance(sno, float) else None,
                                         "styp": kv.get("STYP", (None,))[0], "line": ev.line}
            elif prog == "AQUA":
                if k == "SECT":
                    kv = ev.kv(("NO", "MNO"), ())
                    sect = _int(kv.get("NO", (None,))[0])
                    if sect is not None and isinstance(kv.get("MNO", (None,))[0], float):
                        self.section_mno[sect] = _int(kv["MNO"][0])
                elif k == "PROF" and sect is not None:
                    kv = ev.kv(("TYPE", "Z1", "Z2", "Z3"), ("MNO",))
                    t = str(kv.get("TYPE", ("",))[0]).upper()
                    z = [kv.get(n, (None,))[0] for n in ("Z1", "Z2", "Z3")]
                    zs = ["%g" % x for x in z if isinstance(x, float)]
                    if isinstance(kv.get("MNO", (None,))[0], float):
                        self.section_mno[sect] = _int(kv["MNO"][0])
                    if t in ("CHS",) and len(zs) >= 2:
                        self.sections[sect] = f"CHS {zs[0]}x{zs[-1]}"
                    elif t and zs:
                        self.sections[sect] = f"{t} " + "x".join(zs)
                elif k == "STEE":
                    kv = ev.kv(("NO", "TYPE", "CLAS"), ("TITL",))
                    n = _int(kv.get("NO", (None,))[0])
                    if n is not None:
                        self.materials[n] = f"{kv.get('TYPE', ('',))[0]} {kv.get('CLAS', ('',))[0]}".strip()
            if prog == "BDK" and k == "MEMB" and grp is not None and grp.get("pending_cvl"):
                grp["membs"][-1]["cvl"] = grp.pop("pending_cvl")

    # -- helpers used by the checks
    def defined(self):
        return set(self.lcs)

    def combos(self):
        """LCs with COPY records (combination load cases)."""
        return {n: lc for n, lc in self.lcs.items() if lc.copies}

    def atoms(self, n, f=1.0, path=(), out=None, problems=None):
        """Expand LC n into its load atoms: {(atom_lc): [(factor, path), ...]}.  An LC with its own load
        records (or FACD) is itself an atom; COPYs are followed recursively."""
        if out is None:
            out, problems = {}, []
        lc = self.lcs.get(n)
        if lc is None:
            problems.append(f"LC {n} not defined (via {' > '.join(map(str, path + (n,)))})")
            return out, problems
        if n in path:
            problems.append(f"COPY cycle {' > '.join(map(str, path + (n,)))}")
            return out, problems
        if lc.loads or (lc.facd and not lc.copies) or (not lc.loads and not lc.copies):
            out.setdefault(n, []).append((f, path + (n,)))
        for src, fact, line, _, _ in lc.copies:
            if src is None:
                problems.append(f"line {line}: COPY not resolvable")
                continue
            self.atoms(src, f * fact, path + (n,), out, problems)
        return out, problems

    def result_ranges(self):
        """[(lo, hi, producer, line)] of load-case numbers written by programs other than SOFiLOAD."""
        out = []
        for a in self.ase:
            for e in a["eige"]:
                if e["n"] > 0:
                    out.append((e["first"], e["first"] + e["n"] - 1, f"ASE EIGE {e['etyp']}", e["line"]))
        for m in self.maxima:
            for c in m["combs"]:
                if c["base"] is not None:
                    out.append((c["base"] + 1, c["base"] + 99, f"MAXIMA COMB {c['no']} BASE {c['base']}",
                                c["line"]))   # [I] BASE + 01..99 (file comment)
        seen = set()
        for b in self.bdk:
            for g in b["groups"]:
                if g["lcst"] and (b["block"], g["lcst"]) not in seen:
                    seen.add((b["block"], g["lcst"]))
                    out.append((g["lcst"], g["lcst"], "BDK CTRL LCST", g["ctrl_line"]))
        for q in self.aqb:
            for s in q["lcst"]:
                if s:
                    out.append((s, s, "AQB COMB LCST", q["line"]))
        return out

    def nonlinear_lcs(self):
        out = {}
        for a in self.ase:
            if a["prob"] in ("TH2", "TH3", "NONL"):
                for n in a["lcs"]:
                    out[n] = (a["prob"], a["line"])
        return out

    def bdk_members(self):
        out = []
        for b in self.bdk:
            for g in b["groups"]:
                for m in g["membs"]:
                    out.append(dict(m, block=b["block"], lcst=g["lcst"]))
        return out
