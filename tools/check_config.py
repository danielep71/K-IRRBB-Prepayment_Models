"""Validate YAML configuration and repository-specific issue defaults."""
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Dependabot's target-branch names the active release branch; CI checks that it exists.
RELEASE_BRANCH = re.compile(r'release/\d+\.\d+\.\d+')
# Every pip install of the hash-locked tools must verify hashes and refuse source builds.
PIP_FLAGS = ('--require-hashes', '--only-binary=:all:')
# A run step that starts Python or Node.js needs the interpreter installed by an earlier
# setup step of the same job, at an exact X.Y.Z version, not the runner image's copy.
RUNTIMES = {'python': ('actions/setup-python@', 'python-version'),
            'node': ('actions/setup-node@', 'node-version')}
RUNTIME_COMMAND = re.compile(r'(?:^|[\s;&|(])(python3?|node)(?=\s|$)', re.M)
EXACT_VERSION = re.compile(r'\d+\.\d+\.\d+')
REQUIREMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*==[^\s;]+(?:\s+--hash=sha256:[0-9a-f]{64})+')
# Fields each issue form must require, so triage starts from verifiable reports.
REQUIRED_FORM_FIELDS = {
    'bug.yml': ('commit', 'model', 'reproduce', 'expected', 'observed', 'environment', 'acceptance',
                'validation', 'dependencies', 'target_end_date'),
    'documentation.yml': ('location', 'problem', 'correction', 'source', 'acceptance', 'validation',
                          'dependencies', 'target_end_date'),
    'feature.yml': ('area', 'problem', 'contract', 'acceptance', 'boundary', 'dependencies',
                    'target_end_date'),
}


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently overwriting values."""


def unique_mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def unrequired_fields(form: str, body: list[dict[str, Any]]) -> list[str]:
    """The fields REQUIRED_FORM_FIELDS names for a form that it lacks or leaves optional."""
    required = {field.get('id') for field in body if (field.get('validations') or {}).get('required') is True}
    return [name for name in REQUIRED_FORM_FIELDS.get(form, ()) if name not in required]


def inspect_config(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads((root / '.github/labels.json').read_text(encoding='utf-8'))
    labels = {label['name'] for label in manifest['core']}
    for path in sorted((root / '.github').rglob('*.yml')):
        try:
            data = yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueLoader)
            if not isinstance(data, dict):
                raise ValueError('expected a YAML mapping')
            if path.parent.name == 'workflows':
                check_workflow(data)
            if path.parent.name == 'ISSUE_TEMPLATE' and path.name != 'config.yml':
                check_issue_form(path.name, data, labels)
            if path.name == 'dependabot.yml':
                check_dependabot(data, labels)
        except (yaml.YAMLError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{path.relative_to(root)}: {exc}')
    errors += inspect_requirements(root)
    return errors


def runtime_errors(steps: list[dict[str, Any]]) -> list[str]:
    """Runtimes that a run step starts before a setup step installed them at an exact version."""
    installed: set[str] = set()
    errors = []
    for step in steps:
        action = str(step.get('uses', ''))
        for runtime, (prefix, key) in RUNTIMES.items():
            if action.startswith(prefix):
                version = str((step.get('with') or {}).get(key, ''))
                if not EXACT_VERSION.fullmatch(version):
                    errors.append(f'{prefix.rstrip("@")} needs an exact {key}, not {version!r}')
                installed.add(runtime)
        for command in RUNTIME_COMMAND.findall(str(step.get('run', ''))):
            runtime = 'node' if command == 'node' else 'python'
            if runtime not in installed:
                errors.append(f'{command} runs before {RUNTIMES[runtime][0].rstrip("@")} installs it')
    return errors


def check_workflow(data: dict[Any, Any]) -> None:
    """Actions are SHA-pinned, checkouts persist no credentials, pip installs verify hashes and
    runtimes are installed at an exact version before use."""
    for job in data.get('jobs', {}).values():
        for step in [job, *job.get('steps', [])]:
            action = step.get('uses', '')
            if action and not action.startswith('./'):
                if not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', action):
                    raise ValueError(f'unpinned action: {action}')
            if action.startswith('actions/checkout@'):
                if step.get('with', {}).get('persist-credentials') is not False:
                    raise ValueError('checkout must disable persisted credentials')
            for command in pip_installs(str(step.get('run', ''))):
                if not all(flag in command.split() for flag in PIP_FLAGS):
                    raise ValueError(f'pip install without {" ".join(PIP_FLAGS)}: {command}')
        problems = runtime_errors(job.get('steps', []))
        if problems:
            raise ValueError(problems[0])


def check_issue_form(name: str, data: dict[Any, Any], labels: set[str]) -> None:
    """Catalogue labels with one priority, the owner as assignee, unique IDs and the required fields."""
    chosen = data.get('labels', [])
    if not chosen or set(chosen) - labels:
        raise ValueError('unknown or missing issue labels')
    if len(set(chosen) & {'P1', 'P2', 'P3'}) != 1:
        raise ValueError('one priority required')
    if 'danielep71' not in data.get('assignees', []):
        raise ValueError('owner assignee required')
    ids = [field['id'] for field in data['body'] if field['type'] != 'markdown']
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate issue form field ID')
    missing = unrequired_fields(name, data['body'])
    if missing:
        raise ValueError(f'issue form must require: {", ".join(missing)}')


def check_dependabot(data: dict[Any, Any], labels: set[str]) -> None:
    """Version 2, catalogue labels, one release/X.Y.Z target for every entry, and the pip entry."""
    if data.get('version') != 2:
        raise ValueError('Dependabot version 2 required')
    for update in data['updates']:
        if set(update.get('labels', [])) - labels:
            raise ValueError('unknown Dependabot label')
        if not RELEASE_BRANCH.fullmatch(str(update.get('target-branch', ''))):
            raise ValueError('Dependabot must target the active release branch, release/X.Y.Z')
    if len({update['target-branch'] for update in data['updates']}) != 1:
        raise ValueError('every Dependabot entry must target the same active release branch')
    if not any(update.get('package-ecosystem') == 'pip' and update.get('directory') == '/tools'
               for update in data['updates']):
        raise ValueError('Dependabot must update the pip requirements in /tools')


def logical_lines(text: str) -> list[str]:
    """Lines with backslash continuations joined and comments removed."""
    joined = re.sub(r'[ \t]*\\[ \t]*\n[ \t]*', ' ', text)
    return [line.split('#', 1)[0].strip() for line in joined.splitlines() if line.split('#', 1)[0].strip()]


def pip_installs(script: str) -> list[str]:
    return [line for line in logical_lines(script) if re.search(r'\bpip install\b', line)]


def inspect_requirements(root: Path) -> list[str]:
    """Every requirement in tools/requirements*.txt is pinned and carries at least one hash."""
    errors: list[str] = []
    for path in sorted((root / 'tools').glob('requirements*.txt')):
        for line in logical_lines(path.read_text(encoding='utf-8')):
            if not REQUIREMENT.fullmatch(line):
                errors.append(f'{path.relative_to(root)}: requirement without an exact pin and hash: '
                              f'{line.split()[0]}')
    return errors


def dependabot_targets(root: Path) -> list[str]:
    """The distinct target-branch values of .github/dependabot.yml, parsed as YAML."""
    data = yaml.load((root / '.github/dependabot.yml').read_text(encoding='utf-8'), Loader=UniqueLoader)
    return sorted({str(update['target-branch']) for update in data['updates'] if 'target-branch' in update})


if __name__ == '__main__':
    if sys.argv[1:] == ['--dependabot-targets']:
        print('\n'.join(dependabot_targets(Path(__file__).resolve().parents[1])))
        raise SystemExit(0)
    problems = inspect_config(Path(__file__).resolve().parents[1])
    if problems:
        raise SystemExit('\n'.join(problems))
    print('YAML and repository configuration checks passed.')
