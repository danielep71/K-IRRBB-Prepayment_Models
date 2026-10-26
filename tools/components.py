"""Stage the VBA components of one commit and compare a workbook export with them.

stage    lists the components of a production or test build from the commit
         object (never the working tree), checks names and encoding, and
         writes manifest.json plus CRLF copies for import by Build-Workbook.ps1.
compare  checks a folder exported by Export-Workbook.ps1 against a manifest:
         missing, extra and changed components, code in document modules and
         non-default references all fail.

Usage:
  python tools/components.py stage --build test --commit HEAD --out build/stage
  python tools/components.py compare --manifest build/stage/manifest.json --export build/export
No packages are required. Neither command opens Excel or proves compilation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workbook_layout as layout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1

# Source folder -> (extension, required name prefix, builds that include it).
SOURCES = {
    'src/core': ('.bas', 'CORE_', layout.BUILDS),
    'src/modules': ('.bas', 'PREPAY_', layout.BUILDS),
    'src/workbook': ('.bas', 'WB_', layout.BUILDS),
    'src/classes': ('.cls', '', layout.BUILDS),
    'tests/modules': ('.bas', 'TEST_', (layout.TEST,)),
}
UNSUPPORTED = {'src/forms': 'UserForms need a reviewed .frx binary exception first'}
GUIDES = {'README.md'}
DEFAULT_REFERENCES = {'VBA', 'Excel', 'stdole', 'Office'}
NAME_RE = re.compile(r'^Attribute VB_Name = "([A-Za-z][A-Za-z0-9_]{0,30})"$', re.M)


@dataclass(frozen=True)
class Component:
    name: str
    kind: str
    path: str
    sha256: str


def normalise(text: str) -> str:
    """Compare form: LF endings, no trailing whitespace, no trailing blank lines."""
    lines = [line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'


def digest(text: str) -> str:
    return hashlib.sha256(normalise(text).encode('utf-8')).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def collect(build: str, files: dict[str, str]) -> tuple[list[Component], list[str]]:
    """Components of a build from {posix path: text}; returns (components, errors)."""
    components: list[Component] = []
    errors: list[str] = []
    documents = set(layout.document_modules(build))
    seen: set[str] = set()
    for path in sorted(files):
        folder = str(PurePosixPath(path).parent)
        leaf = PurePosixPath(path).name
        if folder in UNSUPPORTED:
            errors.append(f'{path}: {UNSUPPORTED[folder]}')
            continue
        if folder not in SOURCES or leaf in GUIDES:
            continue
        ext, prefix, builds = SOURCES[folder]
        stem = PurePosixPath(path).stem
        if PurePosixPath(path).suffix != ext:
            errors.append(f'{path}: only {ext} files belong in {folder}')
            continue
        if build not in builds:
            continue
        text = files[path]
        if not text.isascii():
            errors.append(f'{path}: VBA source must be ASCII (UTF-8 in Git, Windows-1252 in the VBE)')
            continue
        if not stem.startswith(prefix):
            errors.append(f'{path}: name must start with {prefix}')
        match = NAME_RE.search(text)
        if match is None or match.group(1) != stem:
            errors.append(f'{path}: Attribute VB_Name must equal the file name {stem!r}')
        if stem.casefold() in seen or stem in documents:
            errors.append(f'{path}: component name {stem!r} is already used')
        seen.add(stem.casefold())
        kind = 'class' if ext == '.cls' else 'standard'
        components.append(Component(stem, kind, path, digest(text)))
    return components, errors


def stage(build: str, commit: str, out: Path) -> int:
    sha = git('rev-parse', '--verify', f'{commit}^{{commit}}').strip()
    if git('status', '--porcelain', '--untracked-files=no').strip():
        print('warning: the working tree has changes; components are read from the commit only',
              file=sys.stderr)
    names = git('ls-tree', '-r', '--name-only', sha).splitlines()
    wanted = [n for n in names if str(PurePosixPath(n).parent) in {*SOURCES, *UNSUPPORTED}]
    files = {n: git('show', f'{sha}:{n}') for n in wanted}
    components, errors = collect(build, files)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'{out} must be a new or empty folder')
    target = out / 'components'
    target.mkdir(parents=True, exist_ok=True)
    for c in components:
        text = normalise(files[c.path]).replace('\n', '\r\n')
        (target / PurePosixPath(c.path).name).write_bytes(text.encode('ascii'))
    manifest: dict[str, Any] = {
        'schema': SCHEMA,
        'build': build,
        'commit': sha,
        'components': [asdict(c) for c in components],
        'document_modules': list(layout.document_modules(build)),
        'references': sorted(DEFAULT_REFERENCES),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Staged {len(components)} components and {len(manifest["document_modules"])} document modules '
          f'for the {build} build of {sha} in {out}')
    return 0


def document_code(text: str) -> list[str]:
    """Code lines of an exported document module; attributes and Option Explicit are not code."""
    lines = normalise(text).split('\n')
    if lines and lines[0].startswith('VERSION '):
        end = next((i for i, line in enumerate(lines) if line.strip() == 'END'), -1)
        lines = lines[end + 1:]
    return [line for line in lines
            if line.strip() and not line.startswith('Attribute ') and line.strip() != 'Option Explicit']


def compare(manifest: dict[str, Any], export: dict[str, str], references: list[str] | None) -> list[str]:
    """Differences between a manifest and {exported file name: text}; empty when they match."""
    errors: list[str] = []
    expected = {c['name']: c for c in manifest['components']}
    documents = set(manifest['document_modules'])
    exported = {PurePosixPath(n).stem: n for n in export if PurePosixPath(n).suffix in {'.bas', '.cls', '.frm'}}
    for name in sorted(expected.keys() - exported.keys()):
        errors.append(f'missing component: {name}')
    for name in sorted(documents - exported.keys()):
        errors.append(f'missing document module: {name}')
    for name in sorted(exported.keys() - expected.keys() - documents):
        errors.append(f'extra component: {exported[name]}')
    for name in sorted(expected.keys() & exported.keys()):
        entry = expected[name]
        suffix = PurePosixPath(exported[name]).suffix
        if suffix != PurePosixPath(entry['path']).suffix:
            errors.append(f'wrong component type: {exported[name]} for {entry["path"]}')
        elif digest(export[exported[name]]) != entry['sha256']:
            errors.append(f'changed component: {name} differs from {entry["path"]} at {manifest["commit"]}')
    for name in sorted(documents & exported.keys()):
        code = document_code(export[exported[name]])
        if code:
            errors.append(f'document module {name} contains code: {code[0]!r}')
    if references is not None:
        actual = set(references)
        allowed = set(manifest['references'])
        for ref in sorted(actual - allowed):
            errors.append(f'non-default reference: {ref}')
        for ref in sorted(allowed - actual):
            errors.append(f'missing default reference: {ref}')
    return errors


def read_export(folder: Path) -> dict[str, str]:
    return {p.name: p.read_bytes().decode('cp1252') for p in sorted(folder.iterdir()) if p.is_file()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p_stage = sub.add_parser('stage')
    p_stage.add_argument('--build', choices=layout.BUILDS, required=True)
    p_stage.add_argument('--commit', default='HEAD')
    p_stage.add_argument('--out', type=Path, required=True)
    p_compare = sub.add_parser('compare')
    p_compare.add_argument('--manifest', type=Path, required=True)
    p_compare.add_argument('--export', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'stage':
        return stage(args.build, args.commit, args.out)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if manifest.get('schema') != SCHEMA:
        raise SystemExit(f'unsupported manifest schema: {manifest.get("schema")}')
    refs_file = args.export / 'references.json'
    references = json.loads(refs_file.read_text(encoding='utf-8-sig')) if refs_file.exists() else None
    export = {n: t for n, t in read_export(args.export).items() if n != 'references.json'}
    errors = compare(manifest, export, references)
    if references is None:
        errors.append('references.json missing from the export; references not checked')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        print(f'FAIL: export does not match the {manifest["build"]} build of {manifest["commit"]}')
        return 1
    print(f'PASS: export matches the {manifest["build"]} build of {manifest["commit"]}: '
          f'{len(manifest["components"])} components, {len(manifest["document_modules"])} document modules, '
          'default references only')
    return 0


if __name__ == '__main__':
    sys.exit(main())
