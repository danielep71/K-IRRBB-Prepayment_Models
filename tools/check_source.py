"""Filename and provenance rules, independent of model source."""
import json
import re
from pathlib import Path, PurePosixPath


def inspect_source(root: Path, names: list[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name.casefold() in seen:
            errors.append(f'Case-insensitive path collision: {name}')
        seen.add(name.casefold())
        for part in PurePosixPath(name).parts:
            if (not re.fullmatch(r'[A-Za-z0-9_.-]+', part)
                    or part.endswith('.')
                    or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                        *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
                errors.append(f'Non-portable path: {name}')
    try:
        data = json.loads((root / 'docs/provenance.json').read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not data.get('sources'):
            raise ValueError('schema_version=1 and nonempty sources required')
        covered: set[str] = set()
        for source in data['sources']:
            if not re.fullmatch(r'https://github.com/[\w.-]+/[\w.-]+', source['repository']):
                raise ValueError('source repository must be a canonical GitHub URL')
            if not re.fullmatch(r'[a-f0-9]{40}', source['reference_revision']):
                raise ValueError('reference_revision must be a full commit SHA')
            if not source['treatment'].strip() or not source['files']:
                raise ValueError('treatment and files required')
            for name in source['files']:
                if name not in names or name in covered:
                    raise ValueError(f'untracked or repeated provenance path: {name}')
                covered.add(name)
        required = {'.editorconfig', '.gitattributes', '.gitignore', 'LICENSE',
                    '.github/scripts/issue-metadata.py', 'tools/test_issue_metadata.py',
                    '.github/scripts/labels-sync.mjs', '.github/scripts/labels-drift.mjs'}
        if required - covered:
            raise ValueError(f'missing imported-file provenance: {sorted(required - covered)}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(f'Invalid provenance register: {exc}')
    return errors
