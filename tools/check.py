"""Offline setup checks; no Excel or model validation."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('README.md', 'LICENSE', 'SECURITY.md', 'CONTRIBUTING.md',
            'docs/PROVENANCE.md', 'docs/GOVERNANCE.md', 'INSTALLATION.md')


def inspect(root, names):
    """Return actionable errors for the tracked working-tree files."""
    errors = [f'Missing required file: {p}' for p in REQUIRED if p not in names]
    for name in names:
        path = root / name
        if not path.is_file():
            errors.append(f'Missing tracked file: {name}')
            continue
        if path.suffix.lower() in {'.xlsx', '.xlsm', '.xlsb', '.xls', '.exe', '.zip'}:
            errors.append(f'Unapproved binary: {name}')
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            errors.append(f'Non-UTF-8 source: {name}')
            continue
        if text and not text.endswith('\n'):
            errors.append(f'Missing final newline: {name}')
        if any(line.rstrip(' \t') != line for line in text.splitlines()):
            errors.append(f'Trailing whitespace: {name}')
        if path.suffix == '.py':
            try:
                ast.parse(text, filename=name)
            except SyntaxError as exc:
                errors.append(str(exc))
        if path.suffix == '.json':
            try:
                json.loads(text)
            except ValueError as exc:
                errors.append(f'{name}: {exc}')
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^\s)]+)\)', text):
                parsed = urlsplit(target)
                if not parsed.scheme and parsed.path:
                    dest = (path.parent / unquote(parsed.path)).resolve()
                    if not dest.is_relative_to(root.resolve()) or not dest.exists():
                        errors.append(f'{name}: missing/unsafe link {target}')
        if name.startswith('.github/workflows/'):
            for action in re.findall(r'^\s*-?\s*uses:\s*([^\s#]+)', text, re.M):
                if not action.startswith('./') and not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', action):
                    errors.append(f'{name}: unpinned action {action}')
    return errors


def main():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    errors = inspect(ROOT, [name for name in names if name])
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
