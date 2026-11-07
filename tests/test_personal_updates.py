"""Offline update detection and release transaction regression tests."""
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


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/builds')
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
    state = {'build_profile': checker.BUILD_PROFILE, 'sources': {app: {'tag': 'v1', 'assets': copy.deepcopy(r['assets'])}
                         for app, r in releases.items()}}
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


def test_unchanged_skips_and_round_trips_state(checker, scenario):
    _, _, state, output, calls = scenario
    checker.main()
    result = outputs(output)
    assert result['has_updates'] == 'false'
    assert json.loads(base64.b64decode(result['state_b64'])) == state
    assert ('https://example/state', False) in calls



@pytest.mark.parametrize('app', ['youtube', 'instagram', 'facebook', 'discord'])
@pytest.mark.parametrize('change', ['tag', 'asset_id', 'digest'])
def test_each_source_update_triggers_build(checker, scenario, app, change):
    releases, _, _, output, _ = scenario
    if change == 'tag':
        releases[app]['tag_name'] = 'v2'
    elif change == 'asset_id':
        releases[app]['assets'][0]['id'] += 100
    else:
        releases[app]['assets'][0]['digest'] = 'sha256:new'
    checker.main()
    assert outputs(output)['has_updates'] == 'true'


@pytest.mark.parametrize('missing', ['release', 'state', 'apk', 'source'])
def test_incomplete_baseline_rebuilds(checker, scenario, missing):
    _, previous, state, output, _ = scenario
    if missing == 'release':
        previous['error'] = 404
    elif missing == 'state':
        previous['assets'] = previous['assets'][:-1]
    elif missing == 'apk':
        previous['assets'] = previous['assets'][1:]
    else:
        state['sources'].pop('facebook')
    checker.main()
    assert outputs(output)['has_updates'] == 'true'


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


def test_publish_rejects_changed_upstream(checker, scenario, tmp_path):
    releases, _, state, _, _ = scenario
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(state))
    checker.verify_state(path)
    releases['youtube']['tag_name'] = 'v2'
    with pytest.raises(RuntimeError, match='changed during build'):
        checker.verify_state(path)


@pytest.mark.parametrize('fail_create', [False, True])
def test_release_only_goes_public_after_successful_upload(tmp_path, fail_create):  
    for app in ['youtube', 'instagram', 'facebook', 'discord']:
        (tmp_path / f'{app}-test.apk').write_text('apk')
    fake = tmp_path / 'gh'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_LOG"\n'
                    'if [ "$2" = create ] && [ "$FAIL_CREATE" = 1 ]; then exit 1; fi\n')
    fake.chmod(0o755)
    log = tmp_path / 'gh.log'
    env = {**os.environ, 'PATH': f'{tmp_path}:{os.environ["PATH"]}', 'GH_LOG': str(log),
           'FAIL_CREATE': str(int(fail_create)), 'GITHUB_RUN_NUMBER': '12',
           'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': 'abc123'}
    result = subprocess.run(['bash', str(ROOT / 'scripts/publish_personal_release.sh')],
                            cwd=tmp_path, env=env)
    calls = log.read_text().splitlines()
    assert '--draft --target abc123' in calls[0]
    assert (result.returncode != 0) == fail_create
    assert len(calls) == (1 if fail_create else 2)
    if not fail_create:
        assert calls[1] == 'release edit build-12-1 --draft=false --latest'


def test_workflow_contract():
    workflow = yaml.load((ROOT / '.github/workflows/personal-build.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on']['schedule'] == [{'cron': '17 0,4 * * *'}]
    jobs = workflow['jobs']
    assert jobs['build']['needs'] == 'check'
    assert "needs.check.outputs.has_updates == 'true'" in jobs['build']['if']
    assert jobs['publish']['needs'] == ['check', 'build']
    assert "needs.build.result == 'success'" in jobs['publish']['if']
    assert "inputs.app == 'all'" in jobs['publish']['if']
    script = jobs['publish']['steps'][-1]['run']
    assert script.index('--verify-state') < script.index('publish_personal_release.sh')
    matrix = jobs['build']['strategy']['matrix']
    for app in ['youtube', 'instagram', 'facebook', 'discord']:
        assert f'"app":"{app}"' in matrix
    for source, expected in [('morphe', ('MorpheApp', 'morphe-patches')),
                              ('hushgram', ('SysAdminDoc', 'HushGram')),
                              ('hushfacebook', ('SysAdminDoc', 'HushFacebook'))]:
        config = json.loads((ROOT / f'sources/{source}.json').read_text())[-1]
        assert (config['user'].lower(), config['repo'].lower()) == tuple(x.lower() for x in expected)
        assert config['tag'] == 'latest'


@pytest.mark.parametrize('event,app,updates,build_result,want_build,want_publish', [
    ('schedule', '', 'false', 'skipped', False, False),
    ('schedule', '', 'true', 'success', True, True),
    ('schedule', '', 'true', 'failure', True, False),
    ('schedule', '', 'true', 'cancelled', True, False),
    ('workflow_dispatch', 'all', 'false', 'success', True, True),
    ('workflow_dispatch', 'youtube', 'true', 'success', True, False),
    ('workflow_dispatch', 'instagram', 'true', 'success', True, False),
    ('workflow_dispatch', 'facebook', 'true', 'success', True, False),
    ('workflow_dispatch', 'discord', 'true', 'success', True, False),
])
def test_actual_job_conditions(event, app, updates, build_result, want_build, want_publish):
    workflow = yaml.load((ROOT / '.github/workflows/personal-build.yml').read_text(), Loader=yaml.BaseLoader)
    values = {'github.event_name': event, 'inputs.app': app,
              'needs.check.outputs.has_updates': updates,
              'needs.check.result': 'success', 'needs.build.result': build_result,
              'success()': build_result == 'success'}

    def evaluate(expression):
        expression = expression.removeprefix('${{').removesuffix('}}').strip()
        for name, value in values.items():
            expression = expression.replace(name, repr(value))
        return eval(expression.replace('&&', ' and ').replace('||', ' or '), {'__builtins__': {}})

    assert evaluate(workflow['jobs']['build']['if']) == want_build
    assert evaluate(workflow['jobs']['publish']['if']) == want_publish


def test_existing_non_clone_release_rebuilds_once(checker, scenario):
    _, _, state, output, _ = scenario
    state.pop('build_profile')
    checker.main()
    assert outputs(output)['has_updates'] == 'true'
    state.update(json.loads(base64.b64decode(outputs(output)['state_b64'])))
    output.unlink()
    checker.main()
    assert outputs(output)['has_updates'] == 'false'
