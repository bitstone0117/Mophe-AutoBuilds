"""Publish only the successful signed APK named in the build report."""
import json
import os
from pathlib import Path
import shutil
import re
import subprocess

app = os.environ['APP_NAME']
reports = json.loads(Path(f'build_records/build_report_{app}.json').read_text())
if len(reports) != 1 or reports[0].get('status') != 'success':
    raise RuntimeError('Expected one successful build')
apk = Path(reports[0]['apk'])
if apk.name != str(apk) or apk.suffix != '.apk' or not apk.is_file():
    raise RuntimeError('Invalid signed APK output')
if app == 'facebook':
    badging = subprocess.run(
        ['aapt', 'dump', 'badging', str(apk)],
        check=True, capture_output=True, text=True,
    ).stdout
    package = re.search(r"^package: name='([^']+)'", badging, re.MULTILINE)
    if not package or package.group(1) != 'com.facebook.katana.morphe':
        raise RuntimeError('Expected Facebook clone package com.facebook.katana.morphe; refusing to publish')
Path('release-apks').mkdir(exist_ok=True)
shutil.copy2(apk, Path('release-apks') / apk.name)
