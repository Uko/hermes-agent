"""Regression tests for autofix policy boundaries found during review."""
from contextlib import contextmanager
from pathlib import Path

import pytest


def test_implicit_sync_leaves_pending_publication_unrecovered(tmp_path, monkeypatch):
    from pm import install
    from pm.package import InstallError
    from hermes_cli import runtime_state
    from pm import environments, paths

    @contextmanager
    def held(**kwargs):
        yield

    journal = tmp_path / "publication.json"
    journal.write_text("pending")
    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(install, "_venv_install_lock", held)
    monkeypatch.setattr(install, "_feature_policy", lambda *a, **k: (None, None))
    monkeypatch.setattr(paths, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(environments, "install_state_dir", lambda root: tmp_path)
    monkeypatch.setattr(runtime_state, "recover_publication", lambda *_: pytest.fail("publication was recovered"))
    with pytest.raises(InstallError, match="publication"):
        install.sync_venv(explicit=False)
    assert journal.read_text() == "pending"


def test_memory_provider_selection_does_not_prepare_dependencies_when_flag_set(monkeypatch):
    from hermes_cli.plugins_cmd_install import _select_memory_provider
    from hermes_cli import memory_setup
    from plugins import memory
    from rich.console import Console
    import io

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(memory, "find_provider_dir", lambda name: Path("/synthetic/provider"))
    monkeypatch.setattr(memory_setup, "prepare_memory_provider_dependencies", lambda name: pytest.fail("PM called"))
    out = io.StringIO()
    _select_memory_provider("example", Console(file=out), select=True)
    assert "HERMES_DISABLE_AUTOFIX" in out.getvalue()


def test_plugin_publication_refused_before_pm_bootstrap(tmp_path, monkeypatch):
    from pm import client
    from pm.plugin_inputs import StagedUpdate
    from pm.package import InstallError

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(client, "_request", lambda *a, **k: pytest.fail("PM bootstrapped"))
    with pytest.raises(InstallError, match="HERMES_DISABLE_AUTOFIX"):
        client.sync_venv(explicit=True, plugins=StagedUpdate({"staged": str(tmp_path)}))


def test_plugin_replacement_is_refused_before_dependency_consent(tmp_path, monkeypatch):
    from hermes_cli.plugins_transaction import publish_plugin
    from hermes_cli.plugins_cmd import PluginOperationError
    from hermes_cli import plugins_cmd

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(plugins_cmd, "_install_plugin_python_deps", lambda *a, **k: pytest.fail("dependency prompt started"))
    with pytest.raises(PluginOperationError, match="HERMES_DISABLE_AUTOFIX"):
        publish_plugin(tmp_path / "staged", tmp_path / "target", {}, {}, require_consent=True)


def test_dependency_consent_does_not_install_node_when_autofix_disabled(tmp_path, monkeypatch):
    from hermes_cli import plugins_cmd_install
    from rich.console import Console
    from types import SimpleNamespace
    import io
    import pm.workspace

    (tmp_path / "package.json").write_text('{}')
    tty = SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(plugins_cmd_install, "sys", SimpleNamespace(stdin=tty, stdout=tty))
    monkeypatch.setattr(plugins_cmd_install, "_ask_yes_no", lambda *a, **k: True)
    calls = []
    monkeypatch.setattr(pm.workspace, "install_node_sidecar", lambda *a, **k: calls.append(a) or None)
    monkeypatch.delenv("HERMES_DISABLE_AUTOFIX", raising=False)
    ok, _ = plugins_cmd_install._install_plugin_python_deps({"name": "test"}, tmp_path, Console(file=io.StringIO()))
    assert ok and len(calls) == 1
    calls.clear()
    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    ok, reason = plugins_cmd_install._install_plugin_python_deps({"name": "test"}, tmp_path, Console(file=io.StringIO()))
    assert not ok
    assert reason is not None and "HERMES_DISABLE_AUTOFIX" in reason
    assert calls == []


def test_plugin_sidecar_refresh_is_refused_before_dependency_install(tmp_path, monkeypatch):
    from hermes_cli.plugins_transaction import _refresh_declared_dependencies
    from hermes_cli.plugins_cmd import PluginOperationError
    import pm.workspace

    target = tmp_path / "target"
    staged = tmp_path / "staged"
    (target / "node_modules").mkdir(parents=True)
    staged.mkdir()
    (staged / "package.json").write_text('{}')
    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(pm.workspace, "install_node_sidecar", lambda *a, **k: pytest.fail("node installed"))
    with pytest.raises(PluginOperationError, match="HERMES_DISABLE_AUTOFIX"):
        _refresh_declared_dependencies(target, staged, {}, interactive=False)


def test_lazy_install_refusal_identifies_autofix_policy(monkeypatch):
    from pm.install import _refuse_lazy

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    error = _refuse_lazy("venv", "not present")
    assert "HERMES_DISABLE_AUTOFIX" in str(error)


def test_explicit_install_does_not_freeze_bundle_just_because_autofix_is_disabled(monkeypatch):
    from pm import install, features, extras

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.delenv("HERMES_DISABLE_LAZY_INSTALLS", raising=False)
    monkeypatch.setattr(features, "read_features", lambda: ["base"])
    monkeypatch.setattr(extras, "extra_supported", lambda *args, **kwargs: True)
    assert install._feature_policy(["additional"], repair=False, explicit=True) == (["base"], None)


def test_explicit_machine_maintenance_still_uses_configured_lazy_policy(monkeypatch):
    import pm
    from hermes_cli import post_update
    import pm.install

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.delenv("HERMES_DISABLE_LAZY_INSTALLS", raising=False)
    monkeypatch.setattr(pm, "drift", lambda: {"example": "stale"})
    monkeypatch.setattr(pm.install, "sealed", lambda: False)
    calls = []
    monkeypatch.setattr(pm, "ensure", lambda name, **kw: calls.append((name, kw)))
    result = post_update.step_provision_runtimes()
    assert result.get("refreshed") == ["example"]
    assert calls == [("example", {"explicit": True})]
