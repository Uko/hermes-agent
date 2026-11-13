"""Plugin changes must not implicitly provision dependencies under autofix policy."""
import pytest


@pytest.mark.parametrize("enabled, disabled", [(set(), {"example"}), ({"example"}, set())])
def test_plugin_change_saves_selection_without_dependency_preparation(tmp_path, monkeypatch, enabled, disabled):
    from hermes_cli.plugins_admission import admit_plugin_set_change
    import pm.client
    from ruamel.yaml import YAML

    home = tmp_path / "profile"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("other: kept\nplugins:\n  enabled: [example]\n")
    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.setattr(pm.client, "sync_venv", lambda **kw: pytest.fail("package manager started"))
    admit_plugin_set_change(enabled, disabled, active_plugins_dir=home / "plugins")
    saved = YAML(typ='safe').load(config.read_text())
    assert saved['other'] == 'kept'
    assert saved['plugins']['enabled'] == sorted(enabled)
    assert saved['plugins']['disabled'] == sorted(disabled)


def test_stale_selection_does_not_overwrite_config(tmp_path, monkeypatch):
    from hermes_cli.plugins_admission import AdmissionRefused, admit_plugin_set_change

    config = tmp_path / 'config.yaml'
    config.write_text('other: updated\n')
    monkeypatch.setenv('HERMES_DISABLE_AUTOFIX', '1')
    with pytest.raises(AdmissionRefused, match='changed'):
        admit_plugin_set_change({'example'}, set(), active_plugins_dir=tmp_path / 'plugins', expected_config='stale')
    assert config.read_text() == 'other: updated\n'


def test_autofix_policy_disables_on_demand_package_installs(monkeypatch):
    from pm.install import lazy_installs_allowed

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    monkeypatch.delenv("HERMES_DISABLE_LAZY_INSTALLS", raising=False)
    assert not lazy_installs_allowed()


def test_autofix_policy_blocks_unattended_plugin_updates(monkeypatch):
    from hermes_cli.plugins_cadence import auto_apply_enabled

    monkeypatch.setenv("HERMES_DISABLE_AUTOFIX", "1")
    assert not auto_apply_enabled(lambda *keys: True)


def test_plugin_change_keeps_original_admission_when_flag_off(tmp_path, monkeypatch):
    from hermes_cli.plugins_admission import admit_plugin_set_change
    import pm.client

    calls = []
    monkeypatch.delenv("HERMES_DISABLE_AUTOFIX", raising=False)
    monkeypatch.setattr(pm.client, "sync_venv", lambda **kw: calls.append(kw))
    admit_plugin_set_change({"example"}, set(), active_plugins_dir=tmp_path / "plugins")
    assert len(calls) == 1
    assert calls[0]["explicit"] is True
