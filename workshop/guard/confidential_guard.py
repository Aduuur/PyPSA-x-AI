# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Keep the confidential workshop data out of git.

The four files in ``workshop/inputs/`` are confidential (one per role). This
script reads them locally at runtime, derives fingerprints from them
(distinctive numbers and their rounded or rescaled forms, e-mail addresses and
domains, phone numbers, reference codes, dates, names of people) and looks for
those fingerprints in what is about to be committed or pushed.

The fingerprints are never written anywhere and matches are reported masked,
so running the guard does not leak the data either. A fingerprint that also
occurs in the public baseline commit (e.g. a plant capacity that is in the open
power plant data) is ignored.

Usage (normally called by the hooks in ``workshop/githooks/``)::

    python3 workshop/guard/confidential_guard.py staged
    python3 workshop/guard/confidential_guard.py message <file>
    python3 workshop/guard/confidential_guard.py push <remote> <local_sha>
    python3 workshop/guard/confidential_guard.py tree      # all tracked files
    python3 workshop/guard/confidential_guard.py files <path> [<path> ...]

Exit code 1 means confidential data was found.
"""

import csv
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "workshop" / "inputs"
BASELINE = "086fc6c2d38b208e7e51a2995c8d7bd6fb8b9f83"  # public baseline
FORBIDDEN_PATHS = ("workshop/inputs/", "workshop/private/", "data-brazil")
PERSON_COLUMNS = {"landowner", "contact_name", "contact_person"}

NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w]|\.\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+\d[\d ()-]{7,}\d")
REFCODE = re.compile(r"\b[A-Z]{2,}-\d[\w/-]*")
DATE = re.compile(r"\b(?:19|20)\d\d-[01]\d-[0-3]\d\b")


def sig(s):
    """Number of significant digits of a number written as a string."""
    return len(s.replace(".", "").lstrip("0").rstrip("0"))


def norm(s):
    """Canonical spelling: no trailing zeros after the decimal point."""
    return s.rstrip("0").rstrip(".") if "." in s else s


def number_variants(s):
    """Distinctive spellings of a number: as written, rounded, x100, /100."""
    out = set()
    if "." not in s:
        n = int(s)
        if sig(s) >= 4 and not 1900 <= n <= 2100:  # years are not distinctive
            out.add(s)
        return out
    dec = len(s.split(".")[1])
    x = float(s)
    for value, decimals in ((x, dec), (x * 100, max(dec - 2, 0)), (x / 100, dec + 2)):
        for d in range(decimals, 0, -1):
            r = norm(f"{value:.{d}f}")
            if sig(r) >= 4:
                out.add(r)
    return out


def fingerprints():
    """{token: source file}. Numbers and codes are matched as tokens, names
    and domains as substrings (in ``subs``)."""
    toks, subs = {}, {}
    if not INPUTS.is_dir():
        return toks, subs
    for f in sorted(p for p in INPUTS.iterdir() if p.is_file()):
        text = f.read_text(errors="ignore")
        found = set()
        for m in NUM.finditer(text):
            found |= number_variants(m.group(0))
        for rx in (REFCODE, DATE):
            found.update(m.group(0).lower() for m in rx.finditer(text))
        for m in EMAIL.finditer(text):
            found.add(m.group(0).lower())
            subs.setdefault(m.group(0).split("@")[1].lower(), f.name)
        for m in PHONE.finditer(text):
            found.add(re.sub(r"\D", "", m.group(0)))
        if f.suffix == ".csv":
            for row in csv.DictReader(io.StringIO(text)):
                for col in PERSON_COLUMNS & set(row):
                    name = (row[col] or "").strip()
                    if row.get("contact_email") and len(name.split()) >= 2:
                        subs.setdefault(name.lower(), f.name)
                        subs.setdefault(name.split()[-1].lower(), f.name)
        for t in found:
            toks.setdefault(t, f.name)
    return toks, subs


def git(*args, check=True):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=check
    ).stdout


_public = {}


def is_public(token):
    """True if the token already occurs in the public baseline commit."""
    if token not in _public:
        r = subprocess.run(
            ["git", "grep", "-q", "-i", "-F", "-w", "-e", token, BASELINE, "--", "."],
            cwd=ROOT, capture_output=True,
        )
        _public[token] = r.returncode == 0
    return _public[token]


def line_tokens(line):
    for m in NUM.finditer(line):
        yield norm(m.group(0))
    for rx in (REFCODE, DATE, EMAIL):
        for m in rx.finditer(line):
            yield m.group(0).lower()
    for m in PHONE.finditer(line):
        yield re.sub(r"\D", "", m.group(0))


def scan(chunks, toks, subs):
    """chunks: iterable of (label, text). Returns masked findings."""
    hits = []
    for label, text in chunks:
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            found = {t for t in line_tokens(line) if t in toks}
            found |= {s for s in subs if s in low}
            for t in sorted(found):
                if not is_public(t):
                    src = toks.get(t) or subs.get(t)
                    hits.append(f"{label}:{i}: <{len(t)} chars hidden> (from {src})")
    return hits


def added_lines(diff):
    """[(file, added text)] from a unified diff."""
    out, cur, buf = [], None, []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            if cur:
                out.append((cur, "\n".join(buf)))
            cur, buf = line[6:] if line.startswith("+++ b/") else line[4:], []
        elif line.startswith("+") and cur:
            buf.append(line[1:])
    if cur:
        out.append((cur, "\n".join(buf)))
    return out


def read_text(path):
    p = ROOT / path
    if not p.is_file() or p.stat().st_size > 20_000_000:
        return None
    try:
        return p.read_text()
    except (UnicodeDecodeError, OSError):
        return None


def collect(argv):
    mode = argv[1] if len(argv) > 1 else "staged"
    if mode == "staged":
        paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
        return paths, added_lines(git("diff", "--cached", "-U0", "--no-color", "--text"))
    if mode == "message":
        return [], [("commit message", Path(argv[2]).read_text(errors="ignore"))]
    if mode == "push":
        remote, local = argv[2], argv[3]
        rng = [local, "--not", f"--remotes={remote}", BASELINE]
        commits = git("rev-list", *rng).split()
        paths, chunks = [], []
        for c in commits:
            chunks.append((f"commit {c[:8]} message", git("log", "-1", "--format=%B", c)))
            paths += git("show", "--format=", "--name-only", c).splitlines()
            chunks += [(f"commit {c[:8]} {f}", t) for f, t in added_lines(
                git("show", "--format=", "-U0", "--no-color", "--text", c))]
        return paths, chunks
    if mode == "tree":
        paths = git("ls-files").splitlines()
        return paths, [(p, t) for p in paths if (t := read_text(p)) is not None]
    if mode == "files":
        chunks = []
        for a in argv[2:]:
            for p in [Path(a)] if Path(a).is_file() else Path(a).rglob("*"):
                if p.is_file() and INPUTS not in p.resolve().parents:
                    chunks.append((str(p), p.read_text(errors="ignore")))
        return [], chunks
    print(__doc__)
    sys.exit(2)


def main(argv):
    paths, chunks = collect(argv)
    errors = [f"forbidden path: {p}" for p in paths if p.startswith(FORBIDDEN_PATHS)]

    toks, subs = fingerprints()
    if not toks and not subs:
        print("confidential-guard: WARNING, workshop/inputs/ not found, "
              "content check skipped (path check still active)", file=sys.stderr)
    else:
        errors += scan(chunks, toks, subs)

    if errors:
        print("\nconfidential-guard: BLOCKED. Confidential workshop data found:\n",
              file=sys.stderr)
        for e in errors[:40]:
            print("  " + e, file=sys.stderr)
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more", file=sys.stderr)
        print("\nRemove these values; load them at runtime from workshop/inputs/ "
              "instead.\nSee 'Confidential data' in AGENTS.md. "
              "Do not bypass this check (no --no-verify).\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
