"""Normal startup must not perform administrative maintenance."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def disable_startup_autofix(monkeypatch):
    monkeypatch.setenv('HERMES_DISABLE_AUTOFIX', '1')


def test_launch_does_not_adopt_source_or_sync_dependencies(tmp_path, monkeypatch):
    from hermes_cli import venv_sync, post_update
    root = tmp_path / 'repo'
    root.mkdir()
    (root / '.git').mkdir()
    (root / 'pyproject.toml').write_text('')
    monkeypatch.delenv('HERMES_DISABLE_LAZY_INSTALLS', raising=False)
    monkeypatch.setattr(post_update, 'step_adopt_blessed_checkout', lambda *_: (_ for _ in ()).throw(AssertionError('unexpected adoption')))
    assert venv_sync.prepare_launch(root, ['chat']) is None


def test_launch_warns_for_pending_update_without_clearing(tmp_path, monkeypatch, capsys):
    from hermes_cli import venv_sync
    marker = tmp_path / 'pending'
    marker.write_text('owed')
    monkeypatch.setattr(venv_sync, 'completion_pending_path', lambda root: marker)
    assert venv_sync.prepare_launch(tmp_path, ['gateway', 'run']) is None
    assert marker.read_text() == 'owed'
    assert 'hermes update' in capsys.readouterr().err



def test_disabled_autofix_reexecs_current_managed_python(tmp_path, monkeypatch):
    from hermes_cli import venv_sync, steward, _launchers
    import pm
    root = tmp_path / 'repo'
    root.mkdir()
    (root / '.git').mkdir()
    (root / 'pyproject.toml').write_text('')
    target = tmp_path / 'managed-python'
    monkeypatch.setattr(steward, 'read_install_stamp', lambda root: {'updateMechanism': 'self'})
    monkeypatch.setattr(pm, 'venv_is_current', lambda **kw: True)
    monkeypatch.setattr(_launchers, 'resolve_store_python', lambda root: target)
    monkeypatch.setattr(venv_sync, 'completion_pending_path', lambda root: tmp_path / 'absent')
    assert venv_sync.prepare_launch(root, ['chat']) == target


def test_disabled_autofix_does_not_gate_startup_on_currency(tmp_path, monkeypatch):
    from hermes_cli import venv_sync, steward, _launchers
    import pm
    monkeypatch.setattr(steward, 'read_install_stamp', lambda root: {'updateMechanism': 'self'})
    monkeypatch.setattr(pm, 'venv_is_current', lambda **kw: (_ for _ in ()).throw(AssertionError('currency check was invoked')))
    monkeypatch.setattr(_launchers, 'resolve_store_python', lambda root: None)
    assert venv_sync.prepare_launch(tmp_path, ['gateway', 'run']) is None



def test_disabled_autofix_allows_busy_lock_without_pending_publication(tmp_path, monkeypatch):
    from pm import environments
    from contextlib import contextmanager
    import hermes_cli.runtime_state as state
    @contextmanager
    def busy(*a, **kw):
        yield False
    state_dir = tmp_path / 'state'
    state_dir.mkdir()
    monkeypatch.setattr(environments, 'install_state_dir', lambda root: state_dir)
    monkeypatch.setattr(state, 'runtime_lock', busy)
    monkeypatch.setattr(environments, 'committed_venv', lambda root: None)
    monkeypatch.setattr(environments, '_require_own_dependencies', lambda root: None)
    assert environments.activate_dependencies(tmp_path) is None


def test_disabled_autofix_refuses_pending_publication(tmp_path, monkeypatch):
    from pm import environments
    from contextlib import contextmanager
    @contextmanager
    def held(*a, **kw):
        yield True
    import hermes_cli.runtime_state as state
    state_dir = tmp_path / 'state'
    state_dir.mkdir()
    (state_dir / 'publication.json').write_text('{}')
    monkeypatch.setattr(environments, 'install_state_dir', lambda root: state_dir)
    monkeypatch.setattr(state, 'runtime_lock', held)
    monkeypatch.setattr(state, 'recover_publication', lambda root: (_ for _ in ()).throw(AssertionError('unexpected recovery')))
    with pytest.raises(RuntimeError, match='publication'):
        environments.activate_dependencies(tmp_path)
    assert (state_dir / 'publication.json').read_text() == '{}'


def test_new_autofix_flag_disables_startup_maintenance(monkeypatch):
    from hermes_cli.startup_autofix import startup_autofix_disabled
    monkeypatch.delenv('HERMES_DISABLE_AUTOFIX', raising=False)
    monkeypatch.setenv('HERMES_DISABLE_AUTOFIX', '1')
    assert startup_autofix_disabled()


def test_autofix_default_on(monkeypatch):
    from hermes_cli.startup_autofix import startup_autofix_disabled
    monkeypatch.delenv('HERMES_DISABLE_AUTOFIX')
    assert not startup_autofix_disabled()
    monkeypatch.setenv('HERMES_DISABLE_AUTOFIX', '0')
    assert not startup_autofix_disabled()


def test_boot_does_not_run_home_migrations(tmp_path, monkeypatch):
    from hermes_cli import boot_bootstrap
    called = []
    monkeypatch.setattr(boot_bootstrap, 'run_boot_bootstrap', lambda root: called.append(root))
    boot_bootstrap.maybe_run_boot_bootstrap(tmp_path)
    assert called == []


def test_automatic_repair_leaves_pending_marker(tmp_path, monkeypatch):
    from hermes_cli import _early_recovery as recovery
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'pyproject.toml').write_text('')
    marker = root / '.update-incomplete'
    marker.write_text('synthetic pending update')
    monkeypatch.setattr(recovery, '_claim_recovery_lock', lambda *_: (_ for _ in ()).throw(AssertionError('unexpected repair')))
    assert recovery.recover_if_needed(root, argv=['chat']) is False
    assert marker.read_text() == 'synthetic pending update'


def test_cli_startup_does_not_sync_skills(tmp_path, monkeypatch):
    from hermes_cli import main, config
    import tools.skills_sync as skills
    monkeypatch.setattr(config, 'get_hermes_home', lambda: tmp_path)
    monkeypatch.setattr(main, '_termux_should_prefetch_update_check', lambda: False)
    monkeypatch.setattr(skills, 'sync_skills', lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected skill sync')))
    assert main._sync_bundled_skills_for_startup() is False


def test_tui_startup_does_not_sync_skills(monkeypatch):
    from hermes_cli import main_tui_launch
    import tools.skills_sync as skills
    called = []
    monkeypatch.setattr(skills, 'sync_skills', lambda **kw: called.append(kw))
    main_tui_launch._sync_bundled_skills_quietly()
    assert called == []


def test_gateway_startup_does_not_sync_skills(monkeypatch):
    from gateway import run_bootstrap
    import hermes_logging
    import tools.skills_sync as skills
    from hermes_cli import security_audit_startup
    called = []
    monkeypatch.setattr(skills, 'sync_skills', lambda **kw: called.append(kw))
    monkeypatch.setattr(hermes_logging, 'setup_logging', lambda **kw: None)
    monkeypatch.setattr(security_audit_startup, 'log_startup_security_warnings', lambda **kw: None)
    run_bootstrap._start_gateway_configure_logging(None)
    assert called == []


def test_left_core_plugin_not_installed_at_startup(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from hermes_cli import left_core_migration as migration
    from hermes_constants import hermes_home_key
    import hermes_constants
    import pm.install
    calls = []
    monkeypatch.setattr(hermes_constants, 'get_hermes_home', lambda: tmp_path)
    monkeypatch.setattr(migration, '_pending', lambda *args, **kwargs: [SimpleNamespace(plugin='example', platform=None)])
    monkeypatch.setattr(migration, '_install_one', lambda *args, **kwargs: calls.append(args) or True)
    monkeypatch.setattr(pm.install, 'lazy_installs_allowed', lambda: True)
    migration._attempted.discard(hermes_home_key(tmp_path))
    assert migration.recover_at_startup() == []
    assert calls == []



def test_old_moved_aside_zip_recovery_cannot_autofix(tmp_path):
    import os, shutil, subprocess, sys
    root = tmp_path / 'repo'
    root.mkdir()
    shutil.copy(Path(__file__).resolve().parents[2] / 'hermes_bootstrap.py', root / 'hermes_bootstrap.py')
    (root / '.hermes-update-zip-swap').write_text('pending')
    old = root / 'hermes_cli.hermes-update-old'
    old.mkdir()
    (old / '_early_recovery.py').write_text("from pathlib import Path\ndef restore_interrupted_pull(root):\n    (root / 'unexpected-write').write_text('bad')\n    return False\n")
    env = {**os.environ, 'HERMES_DISABLE_AUTOFIX': '1'}
    cmd = [sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import hermes_bootstrap', str(root)]
    result = subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode != 0
    assert not (root / 'unexpected-write').exists()
    assert (root / '.hermes-update-zip-swap').read_text() == 'pending'




def test_update_does_not_authorize_automatic_dependency_repair(tmp_path):
    from hermes_cli import _early_recovery as recovery
    assert recovery.recover_if_needed(tmp_path, argv=['update']) is False




def test_memory_provider_not_installed_at_startup(tmp_path, monkeypatch):
    from hermes_cli import memory_provider_migration as migration
    import hermes_constants
    import pm.install
    monkeypatch.setattr(hermes_constants, 'get_hermes_home', lambda: tmp_path)
    monkeypatch.setattr(pm.install, 'lazy_installs_allowed', lambda: True)
    called = []
    monkeypatch.setattr(migration, 'migrate_home', lambda *a, **k: called.append(a) or 'hindsight')
    assert migration.recover_at_startup('hindsight') is False
    assert called == []
