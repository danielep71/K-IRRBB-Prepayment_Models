"""Full quality gate; install requirements-quality-ci.txt and actionlint first."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    actionlint = shutil.which('actionlint')
    if actionlint is None:
        raise SystemExit('actionlint 1.7.12 is required; see tools/README.md')
    version = subprocess.check_output([actionlint, '-version'], text=True).splitlines()[0]
    if version.lstrip('v') != '1.7.12':
        raise SystemExit(f'Expected actionlint v1.7.12, found {version}')
    commands = [
        [sys.executable, 'tools/check.py'],
        [sys.executable, 'tools/check_config.py'],
        [sys.executable, '-m', 'ruff', 'check', '.'],
        [sys.executable, '-m', 'mypy'],
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'quality_test_*.py'],
        [actionlint, '-shellcheck=', '-pyflakes='],
    ]
    for command in commands:
        print('RUN:', ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    # Prove the workflow validator is active, not merely installed.
    bad = 'name: Bad\non: push\njobs:\n  bad:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ${{ secrets.DOES_NOT_EXIST.foo }}\n        bogus-key: true\n'
    result = subprocess.run([actionlint, '-shellcheck=', '-pyflakes=', '-'],
                            input=bad, text=True, capture_output=True, cwd=ROOT)
    if result.returncode != 1 or 'bogus-key' not in result.stdout + result.stderr:
        raise SystemExit('actionlint negative fixture did not produce the expected diagnostic')
    print('Malformed-workflow rejection verified. Full quality gate passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
