"""Static checks of the VBA source, after the K-SACCR house style.

Checks every .bas under src/ and tests/modules/:
  - decodes as cp1252 and is ASCII only, no byte-order mark;
  - first line is Attribute VB_Name, matching the file name;
  - Option Explicit present; Option Private Module in src/core/;
  - module prefix: CORE_ in src/core/, PPM_ in src/modules/, TEST_ in tests/;
  - no tabs, no trailing whitespace;
  - no Range.End (it needs a window) and no function returning a typed
    array (both break the headless test host);
  - every Sub/Function has the banner line right after its signature.

Usage:  python tools/check_source.py   (exit code 1 on any finding)
"""

from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = {"core": "CORE_", "modules": "PPM_", "workbook": "M_", "tests": "TEST_"}


def check(path: str) -> list[str]:
    out = []
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        out.append("byte-order mark")
    try:
        text = raw.decode("cp1252")
    except UnicodeDecodeError as e:
        return [f"not cp1252: {e}"]
    if any(ord(ch) > 127 for ch in text):
        out.append("non-ASCII character")
    lines = text.replace("\r\n", "\n").split("\n")
    m = re.match(r'Attribute VB_Name = "([A-Za-z0-9_]+)"$', lines[0])
    name = os.path.splitext(os.path.basename(path))[0]
    if not m or m.group(1) != name:
        out.append("first line is not Attribute VB_Name = \"%s\"" % name)
    area = "tests" if "/tests/" in path.replace("\\", "/") else os.path.basename(os.path.dirname(path))
    if not name.startswith(PREFIX.get(area, "")):
        out.append("module name lacks prefix %s" % PREFIX.get(area))
    if not any(ln.strip() == "Option Explicit" for ln in lines):
        out.append("no Option Explicit")
    if area == "core" and not any(ln.strip() == "Option Private Module" for ln in lines):
        out.append("core module without Option Private Module")
    for i, ln in enumerate(lines, 1):
        if "\t" in ln:
            out.append(f"line {i}: tab")
        if ln != ln.rstrip():
            out.append(f"line {i}: trailing whitespace")
        code = ln.split("'")[0]
        if re.search(r"\.End\(xl", code):
            out.append(f"line {i}: Range.End")
        if re.match(r"\s*(Public |Private )?Function .*\) As \w+\(\)", code):
            out.append(f"line {i}: function returns a typed array")
    for i, ln in enumerate(lines):
        if re.match(r"(Public |Private )?(Sub|Function) \w+", ln):
            j = i
            while lines[j].rstrip().endswith("_"):
                j += 1
            nxt = lines[j + 1:j + 3]
            if not (len(nxt) == 2 and nxt[0] == "'" and nxt[1].startswith("'=====")):
                out.append(f"line {i + 1}: procedure without banner")
    return out


def main() -> int:
    files = sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.bas"), recursive=True)) + \
        sorted(glob.glob(os.path.join(ROOT, "tests", "modules", "*.bas")))
    bad = 0
    for f in files:
        findings = check(f)
        rel = os.path.relpath(f, ROOT)
        if findings:
            bad += 1
            for x in findings:
                print(f"{rel}: {x}")
        else:
            print(f"{rel}: OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
