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


@pytest.mark.parametrize('reverse', [False, True])
def test_clone_enable_is_scoped_to_its_bundle(reverse):
    from src.__main__ import _morphe_bundle_args
    bundles = [Path('clone-patches-2.1.0.mpp'), Path('patches-0.21.0.mpp')]
    if reverse:
        bundles.reverse()
    args = _morphe_bundle_args(bundles, ['Clone app', 'Block ad telemetry'], ['Force dark mode'])
    # Reconstruct the CLI's bundle scopes: flags bind to the preceding bundle.
    scopes = {}
    for flag, value in zip(args[::2], args[1::2]):
        if flag == '--patches':
            current = scopes.setdefault(value, [])
        else:
            current.append((flag, value))
    assert scopes['clone-patches-2.1.0.mpp'] == [('-e', 'Clone app')]
    assert scopes['patches-0.21.0.mpp'] == [('-d', 'Force dark mode'), ('-e', 'Block ad telemetry')]


def test_single_bundle_selections_unchanged():
    from src.__main__ import _morphe_bundle_args
    assert _morphe_bundle_args([Path('patches.mpp')], ['Clone app'], ['Other']) == [
        '--patches', 'patches.mpp', '-d', 'Other', '-e', 'Clone app'
    ]


def test_build_uses_scoped_arguments():
    # Exercise the actual run_build path up to invoking Java, without an APK/network.
    from src import __main__ as build
    import inspect
    import ast
    source = inspect.getsource(build.run_build)
    # Compile the production command-construction statements so the test catches
    # regressing the call site to appending all selections after the last bundle.
    tree = ast.parse(source)
    branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Name) and node.test.id == 'is_morphe'
                  and any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                          and t.id == 'morphe_cmd' for t in n.targets) for n in node.body))
    statements = branch.body[:next(i for i, n in enumerate(branch.body)
                                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                                 and t.id == 'output' for t in n.targets))]
    namespace = {'logging': build.logging, '_morphe_bundle_args': build._morphe_bundle_args,
                 'cli': Path('cli.jar'), 'patches': [Path('clone-patches.mpp'), Path('hush-patches.mpp')],
                 'current_include_patches': ['Clone app', 'Block ad telemetry'], 'exclude_patches': [],
                 'output_apk': Path('out.apk'), 'input_apk': Path('in.apk')}
    exec(compile(ast.Module(body=statements, type_ignores=[]), '<production-command>', 'exec'), namespace)
    command = namespace['morphe_cmd']
    assert command[command.index('--patches'):] == [
        '--patches', 'clone-patches.mpp', '-e', 'Clone app',
        '--patches', 'hush-patches.mpp', '-e', 'Block ad telemetry',
        '--out', 'out.apk', 'in.apk',
    ]
