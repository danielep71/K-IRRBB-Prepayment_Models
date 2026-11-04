"""Offline repository integrity checks; no Excel or model validation."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from check_source import inspect_source

# Deliberate binary exception: reviewed branding export only (see docs/assets/README.md).
APPROVED_IMAGES = {
    'docs/assets/prepayment-social-preview.png':
        'ad5b59d0219f2f53dae35005fca47450a92f47586208d06db2506bfba4790aa4',
}

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('README.md', 'LICENSE', 'SECURITY.md', 'CONTRIBUTING.md',
            'docs/PROVENANCE.md', 'docs/provenance.json', 'docs/GOVERNANCE.md', 'INSTALLATION.md',
            'src/README.md', 'tests/README.md', 'examples/README.md', 'tools/README.md')
# Operational guides state current rules in my own voice (see docs/GOVERNANCE.md).
GUIDES = ('CONTRIBUTING.md', 'RELEASING.md', 'SECURITY.md', 'INSTALLATION.md', 'docs/GOVERNANCE.md',
          'docs/REPOSITORY_SETTINGS.md', 'docs/TRAFFIC.md')
THIRD_PERSON = re.compile(r'\bthe\s+(?:owner|maintainer)s?\b', re.I)


def inspect(root: Path, names: list[str]) -> list[str]:
    """Return actionable errors for the tracked working-tree files."""
    errors = [f'Missing required file: {p}' for p in REQUIRED if p not in names]
    for name in names:
        errors += inspect_file(root, name, names)
    return errors


def inspect_file(root: Path, name: str, names: list[str]) -> list[str]:
    """Errors for one tracked file: its presence, binary status, encoding and text checks."""
    path = root / name
    if not path.is_file():
        return [f'Missing tracked file: {name}']
    if name in APPROVED_IMAGES:
        if hashlib.sha256(path.read_bytes()).hexdigest() != APPROVED_IMAGES[name]:
            return [f'Unreviewed image content: {name}']
        return []
    if path.suffix.lower() in {'.xlsx', '.xlsm', '.xlsb', '.xls', '.exe', '.zip'}:
        return [f'Unapproved binary: {name}']
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return [f'Non-UTF-8 source: {name}']
    return inspect_text(root, name, text, names)


def inspect_text(root: Path, name: str, text: str, names: list[str]) -> list[str]:
    """Errors in the text of one tracked file."""
    errors = []
    path = root / name
    if text and not text.endswith('\n'):
        errors.append(f'Missing final newline: {name}')
    if any(line.rstrip(' \t') != line for line in text.splitlines()):
        errors.append(f'Trailing whitespace: {name}')
    errors += syntax_errors(name, path.suffix, text)
    if name in GUIDES:
        for match in THIRD_PERSON.finditer(text):
            number = text.count('\n', 0, match.start()) + 1
            phrase = ' '.join(match.group().split())
            errors.append(f'{name}:{number}: "{phrase}" in an operational guide; write "I" or "me"')
    if path.suffix == '.md':
        errors += link_errors(root, path, name, text, names)
    if name.startswith('.github/workflows/'):
        for action in re.findall(r'^\s*-?\s*uses:\s*([^\s#]+)', text, re.M):
            if not action.startswith('./') and not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', action):
                errors.append(f'{name}: unpinned action {action}')
    return errors


def syntax_errors(name: str, suffix: str, text: str) -> list[str]:
    """Python must parse and JSON must load."""
    if suffix == '.py':
        try:
            ast.parse(text, filename=name)
        except SyntaxError as exc:
            return [str(exc)]
    if suffix == '.json':
        try:
            json.loads(text)
        except ValueError as exc:
            return [f'{name}: {exc}']
    return []


def link_errors(root: Path, path: Path, name: str, text: str, names: list[str]) -> list[str]:
    """Relative Markdown links must reach a tracked file inside the repository."""
    errors = []
    for target in re.findall(r'\]\(([^\s)]+)\)', text):
        parsed = urlsplit(target)
        if not parsed.scheme and parsed.path:
            dest = (path.parent / unquote(parsed.path)).resolve()
            if not dest.is_relative_to(root.resolve()) or dest.relative_to(root.resolve()).as_posix() not in names:
                errors.append(f'{name}: missing/unsafe link {target}')
    return errors


def main() -> int:
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    tracked = [name for name in names if name]
    errors = inspect(ROOT, tracked) + inspect_source(ROOT, tracked)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    commands = [
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_*.py'],
        ['node', '.github/scripts/labels-sync.mjs', '--policy', '.github/label-policy.json', '--self-test'],
        ['node', '.github/scripts/labels-drift.mjs', '--policy', '.github/label-policy.json', '--self-test'],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    print('Repository integrity checks passed (no Excel/model certification).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
