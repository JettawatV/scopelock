import os

import pytest

from scopelock.settings import PROJECT_ROOT, model_name, project_id


def test_settings_load_from_project_environment():
    assert PROJECT_ROOT.name == "scopelock"
    assert project_id() == os.environ["GOOGLE_CLOUD_PROJECT"]
    assert model_name() == os.environ["SCOPELOCK_MODEL"]


def test_missing_project_configuration_fails_clearly(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT")
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT is missing"):
        project_id()
