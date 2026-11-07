"""Offline update detection, selective publishing, and migration tests."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
APPS = ['youtube', 'instagram', 'facebook', 'discord']


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/builds')
    monkeypatch.delenv('BUILD_SELECTION', raising=False)
    spec = importlib.util.spec_from_file_location('checker', ROOT / 'scripts/check_personal_updates.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scenario(checker, monkeypatch, tmp_path):
    releases = {app: {'tag_name': 'v1', 'assets': [
        {'name': 'patches-1.mpp', 'id': i, 'digest': 'sha256:abc'}
    ]} for i, app in enumerate(checker.SOURCES, 1)}
    previous = {'assets': [{'name': f'{app}-signed.apk'} for app in checker.SOURCES]
                + [{'name': 'source-state.json', 'browser_download_url': 'https://example/state'}]}
    state = {'build_profile': checker.BUILD_PROFILE, 'sources': {
        app: {'tag': 'v1', 'assets': copy.deepcopy(r['assets'])}
        for app, r in releases.items()
    }}
    calls = []

    def fetch(url, authenticated=True):
        calls.append((url, authenticated))
        if url == 'https://example/state':
            return state
        if url.endswith('/repos/example/builds/releases/latest'):
            if previous.get('error'):
                raise HTTPError(url, previous['error'], 'error', None, None)
            return previous
        for app, (owner, repo) in checker.SOURCES.items():
            if url == f'{checker.API}/repos/{owner}/{repo}/releases/latest':
                return releases[app]
        raise AssertionError(url)

    monkeypatch.setattr(checker, 'fetch_json', fetch)
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    return releases, previous, state, output, calls


def outputs(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines())


def decoded_state(path):
    return json.loads(base64.b64decode(outputs(path)['state_b64']))


def test_unchanged_skips_and_preserves_all_baselines(checker, scenario):
    _, _, old, output, calls = scenario
    checker.main()
    result = outputs(output)
    assert result['has_updates'] == 'false'
    assert json.loads(result['matrix_json']) == {'include': []}
    assert decoded_state(output)['sources'] == old['sources']
    assert decoded_state(output)['selected_apps'] == []
    assert decoded_state(output)['published_apps'] == APPS
    assert ('https://example/state', False) in calls


@pytest.mark.parametrize('app', APPS)
@pytest.mark.parametrize('change', ['tag', 'asset_id', 'digest'])
def test_only_changed_app_builds(checker, scenario, app, change):
    releases, _, old, output, _ = scenario
    original = copy.deepcopy(old['sources'])
    if change == 'tag':
        releases[app]['tag_name'] = 'v2'
    elif change == 'asset_id':
        releases[app]['assets'][0]['id'] += 100
    else:
        releases[app]['assets'][0]['digest'] = 'sha256:new'
    checker.main()
    assert outputs(output)['has_updates'] == 'true'
    assert json.loads(outputs(output)['selected_apps']) == [app]
    assert json.loads(outputs(output)['matrix_json']) == {
        'include': [{'app': app, 'source': checker.BUILD_SOURCES[app]}]
    }
    next_state = decoded_state(output)
    assert next_state['sources'][app] != original[app]
    for other in set(APPS) - {app}:
        assert next_state['sources'][other] == original[other]


def test_only_selected_app_advanced_after_publish(checker, scenario, monkeypatch):
    releases, previous, state, output, _ = scenario
    releases['discord']['tag_name'] = 'v2'
    checker.main()
    after_discord = decoded_state(output)
    assert after_discord['selected_apps'] == ['discord']
    output.unlink()
    state.clear()
    state.update(after_discord)
    previous['assets'] = [
        {'name': 'discord-new.apk'},
        {'name': 'source-state.json', 'browser_download_url': 'https://example/state'},
    ]
    checker.main()
    assert outputs(output)['has_updates'] == 'false'
    assert decoded_state(output)['published_apps'] == APPS


def test_pending_unselected_change_is_not_ignored(checker, scenario, monkeypatch):
    releases, previous, state, output, _ = scenario
    releases['youtube']['tag_name'] = 'v2'
    releases['discord']['tag_name'] = 'v2'
    monkeypatch.setenv('BUILD_SELECTION', 'discord')
    checker.main()
    after_discord = decoded_state(output)
    assert after_discord['selected_apps'] == ['discord']
    assert after_discord['sources']['youtube']['tag'] == 'v1'
    monkeypatch.delenv('BUILD_SELECTION')
    output.unlink()
    state.clear()
    state.update(after_discord)
    previous['assets'] = [
        {'name': 'discord-new.apk'},
        {'name': 'source-state.json', 'browser_download_url': 'https://example/state'},
    ]
    checker.main()
    assert json.loads(outputs(output)['selected_apps']) == ['youtube']


@pytest.mark.parametrize('choice,expected', [
    ('all', APPS),
    ('youtube', ['youtube']),
    ('instagram', ['instagram']),
    ('facebook', ['facebook']),
    ('discord', ['discord']),
])
def test_manual_selection_builds_and_publishes_only_choice(checker, scenario, monkeypatch, choice, expected):
    _, _, _, output, _ = scenario
    monkeypatch.setenv('BUILD_SELECTION', choice)
    checker.main()
    assert json.loads(outputs(output)['selected_apps']) == expected


@pytest.mark.parametrize('missing', ['release', 'state', 'apk', 'source'])
def test_incomplete_baseline_recovers_only_missing_apps(checker, scenario, missing):
    _, previous, state, output, _ = scenario
    if missing == 'release':
        previous['error'] = 404
        expected = APPS
    elif missing == 'state':
        previous['assets'] = previous['assets'][:-1]
        expected = APPS
    elif missing == 'apk':
        previous['assets'] = previous['assets'][1:]
        expected = ['youtube']
    else:
        state['sources'].pop('facebook')
        expected = ['facebook']
    checker.main()
    assert json.loads(outputs(output)['selected_apps']) == expected


@pytest.mark.parametrize('code', [401, 403, 429, 500])
def test_api_errors_fail_closed(checker, scenario, code):
    _, previous, _, output, _ = scenario
    previous['error'] = code
    with pytest.raises(HTTPError):
        checker.main()
    assert not output.exists()


def test_metadata_only_release_rejected(checker, scenario):
    releases, _, _, output, _ = scenario
    releases['youtube']['assets'][0]['name'] = 'README.txt'
    with pytest.raises(RuntimeError, match='No patch bundle'):
        checker.main()
    assert not output.exists()


def test_asset_order_does_not_change_signature(checker, scenario):
    releases, _, _, _, _ = scenario
    assets = releases['youtube']['assets']
    assets.append({'name': 'a.json', 'id': 20})
    before = checker.current_sources()
    assets.reverse()
    assert checker.current_sources() == before


def test_verify_checks_selected_app_only(checker, scenario, tmp_path):
    releases, _, state, _, _ = scenario
    state['selected_apps'] = ['discord']
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(state))
    checker.verify_state(path)
    releases['youtube']['tag_name'] = 'v2'
    checker.verify_state(path)  # unrelated app update does not block this release
    releases['discord']['tag_name'] = 'v2'
    with pytest.raises(RuntimeError, match='changed during build'):
        checker.verify_state(path)


def run_release(tmp_path, apps, fail_create=False):
    for app in apps:
        (tmp_path / f'{app}-test.apk').write_text('apk')
    (tmp_path / 'source-state.json').write_text(json.dumps({'selected_apps': apps}))
    for name in ['obtainium.json', 'SHA256SUMS.txt']:
        (tmp_path / name).write_text('fixture')
    fake = tmp_path / 'gh'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_LOG"\n'
                    'if [ "$2" = create ] && [ "$FAIL_CREATE" = 1 ]; then exit 1; fi\n')
    fake.chmod(0o755)
    log = tmp_path / 'gh.log'
    env = {**os.environ, 'PATH': f'{tmp_path}:{os.environ["PATH"]}', 'GH_LOG': str(log),
           'FAIL_CREATE': str(int(fail_create)), 'GITHUB_RUN_NUMBER': '12',
           'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': 'abc123'}
    result = subprocess.run(['bash', str(ROOT / 'scripts/publish_personal_release.sh')],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


@pytest.mark.parametrize('apps', [['discord'], ['youtube', 'instagram'], APPS])
@pytest.mark.parametrize('fail_create', [False, True])
def test_release_only_selected_apps_after_successful_upload(tmp_path, apps, fail_create):
    result, calls = run_release(tmp_path, apps, fail_create)
    assert '--draft --target abc123' in calls[0]
    for app in apps:
        assert f'{app}-test.apk' in calls[0]
    for other in set(APPS) - set(apps):
        assert f'{other}-test.apk' not in calls[0]
    assert (result.returncode != 0) == fail_create
    assert len(calls) == (1 if fail_create else 2)
    if not fail_create:
        assert calls[1] == 'release edit build-12-1 --draft=false --latest'


def test_release_rejects_extra_apk(tmp_path):
    for app in ['youtube', 'discord']:
        (tmp_path / f'{app}-test.apk').write_text('apk')
    (tmp_path / 'source-state.json').write_text(json.dumps({'selected_apps': ['discord']}))
    result = subprocess.run(['bash', str(ROOT / 'scripts/publish_personal_release.sh')],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0


def test_workflow_contract():
    workflow = yaml.load((ROOT / '.github/workflows/personal-build.yml').read_text(), Loader=yaml.BaseLoader)
    # Scheduling is delegated to an external workflow_dispatch caller.
    assert 'schedule' not in workflow['on']
    assert 'workflow_dispatch' in workflow['on']
    jobs = workflow['jobs']
    assert jobs['build']['needs'] == 'check'
    assert "needs.check.outputs.has_updates == 'true'" in jobs['build']['if']
    assert jobs['build']['strategy']['matrix'] == '${{ fromJSON(needs.check.outputs.matrix_json) }}'
    assert jobs['publish']['needs'] == ['check', 'build']
    assert "needs.build.result == 'success'" in jobs['publish']['if']
    assert 'BUILD_SELECTION' in jobs['check']['steps'][-1]['env']
    script = jobs['publish']['steps'][-1]['run']
    assert script.index('--verify-state') < script.index('publish_personal_release.sh')
    assert ' -eq 4' not in script
    assert jobs['check']['outputs']['selected_apps']
    assert jobs['check']['outputs']['matrix_json']
    assert workflow['on']['workflow_dispatch']['inputs']['app']['options'] == ['all', 'check', *APPS]
    assert "inputs.app != 'check'" in jobs['check']['steps'][-1]['env']['BUILD_SELECTION']
    for source, expected in [('morphe', ('MorpheApp', 'morphe-patches')),
                             ('hushgram', ('SysAdminDoc', 'HushGram')),
                             ('hushfacebook', ('SysAdminDoc', 'HushFacebook')),
                             ('venus', ('VenusIsJaded', 'Venus-Patches'))]:
        config = json.loads((ROOT / f'sources/{source}.json').read_text())[-2 if source == 'venus' else -1]
        assert (config['user'].lower(), config['repo'].lower()) == tuple(x.lower() for x in expected)
        assert config['tag'] == 'latest'


def test_original_three_app_profile_migration(checker, scenario):
    _, previous, old, output, _ = scenario
    old['build_profile'] = 'facebook-clone-v1'
    old['sources'].pop('discord')
    previous['assets'] = [
        a for a in previous['assets'] if a['name'] != 'discord-signed.apk'
    ]
    checker.main()
    assert json.loads(outputs(output)['selected_apps']) == ['discord']
