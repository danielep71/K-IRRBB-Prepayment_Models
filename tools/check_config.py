"""Validate YAML configuration and repository-specific issue defaults."""
import json
import re
from pathlib import Path
from typing import Any

import yaml

ACTIVE_RELEASE_BRANCH = 'release/0.2.0'


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
                for job in data.get('jobs', {}).values():
                    for step in [job, *job.get('steps', [])]:
                        action = step.get('uses', '')
                        if action and not action.startswith('./'):
                            if not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', action):
                                raise ValueError(f'unpinned action: {action}')
                        if action.startswith('actions/checkout@'):
                            if step.get('with', {}).get('persist-credentials') is not False:
                                raise ValueError('checkout must disable persisted credentials')
            if path.parent.name == 'ISSUE_TEMPLATE' and path.name != 'config.yml':
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
            if path.name == 'dependabot.yml':
                if data.get('version') != 2:
                    raise ValueError('Dependabot version 2 required')
                for update in data['updates']:
                    if set(update.get('labels', [])) - labels:
                        raise ValueError('unknown Dependabot label')
                    if update.get('target-branch') != ACTIVE_RELEASE_BRANCH:
                        raise ValueError(f'Dependabot must target the active release branch {ACTIVE_RELEASE_BRANCH}')
        except (yaml.YAMLError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{path.relative_to(root)}: {exc}')
    return errors


if __name__ == '__main__':
    problems = inspect_config(Path(__file__).resolve().parents[1])
    if problems:
        raise SystemExit('\n'.join(problems))
    print('YAML and repository configuration checks passed.')
