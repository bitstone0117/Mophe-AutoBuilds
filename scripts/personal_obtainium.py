"""All three APKs share a unique release tag, including patch-only rebuilds."""
import json
import os
from pathlib import Path

repo = os.environ['GITHUB_REPOSITORY']
apps = []
for name in ('facebook', 'instagram', 'youtube'):
    apps.append({
        'url': f'https://github.com/{repo}',
        'name': name.title(),
        'author': repo.split('/')[0],
        'additionalSettings': json.dumps({
            'apkFilterRegEx': f'^{name}-.*\\.apk$',
        }),
    })
Path('release-apks/obtainium.json').write_text(json.dumps({'apps': apps}, indent=2))
