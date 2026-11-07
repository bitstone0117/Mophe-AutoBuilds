"""Facebook clone identity, bundle isolation and release migration checks."""
import json
from pathlib import Path
import runpy
import subprocess
from unittest.mock import patch

import pytest
from src import downloader

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('package,allowed', [
    ('com.facebook.katana.morphe', True),
    ('com.facebook.katana', False),
    ('unexpected.package', False),
    ('', False),
])
def test_collect_rejects_non_clone(tmp_path, monkeypatch, package, allowed):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('APP_NAME', 'facebook')
    (tmp_path / 'build_records').mkdir()
    (tmp_path / 'facebook-test.apk').write_bytes(b'fixture')
    (tmp_path / 'build_records/build_report_facebook.json').write_text(json.dumps([
        {'status': 'success', 'apk': 'facebook-test.apk'}
    ]))
    with patch('subprocess.run', return_value=subprocess.CompletedProcess(
        [], 0, stdout=f"package: name='{package}' versionCode='1'\n"
    )) as inspect:
        if allowed:
            runpy.run_path(str(ROOT / 'scripts/collect_personal_build.py'))
            assert (tmp_path / 'release-apks/facebook-test.apk').is_file()
        else:
            with pytest.raises(RuntimeError, match='Expected Facebook clone'):
                runpy.run_path(str(ROOT / 'scripts/collect_personal_build.py'))
            assert not (tmp_path / 'release-apks').exists()
        assert inspect.call_args.args[0] == ['aapt', 'dump', 'badging', 'facebook-test.apk']


def test_obtainium_tracks_clone_only_for_facebook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/builds')
    (tmp_path / 'release-apks').mkdir()
    runpy.run_path(str(ROOT / 'scripts/personal_obtainium.py'))
    apps = json.loads((tmp_path / 'release-apks/obtainium.json').read_text())['apps']
    assert {app['name']: app['id'] for app in apps} == {
        'Facebook': 'com.facebook.katana.morphe',
        'Instagram': 'com.instagram.android',
        'Youtube': 'app.morphe.android.youtube',
    }


def test_both_patch_bundles_survive_identical_filenames(monkeypatch):
    monkeypatch.chdir(ROOT)
    def release(entry):
        name = 'morphe-cli.jar' if entry['repo'] == 'morphe-cli' else 'patches-1.0.mpp'
        return {'assets': [{'name': name, 'browser_download_url': 'https://example/' + entry['repo']}]}
    with patch.object(downloader.utils, 'detect_release', side_effect=release), \
         patch.object(downloader, 'download_resource', side_effect=lambda url, name: Path(name)) as download:
        files, _ = downloader.download_required('hushfacebook')
    assert files == [Path('morphe-cli.jar'), Path('clone-patches-1.0.mpp'), Path('patches-1.0.mpp')]
    assert download.call_count == 3


def test_stock_input_and_clone_patch_selection():
    for provider in ['playstore', 'apkmirror']:
        config = json.loads((ROOT / f'apps/{provider}/facebook.json').read_text())
        assert config['package'] == 'com.facebook.katana'
    selection = (ROOT / 'patches/facebook-hushfacebook.txt').read_text().splitlines()
    assert '+Clone app' in selection
    assert '+Block ad telemetry' in selection
