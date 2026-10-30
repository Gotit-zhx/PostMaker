from postmaker.core.config import load_config


def test_dataradar_endpoint_can_be_overridden_by_environment(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("dataradar:\n  api_base: http://old\n  timeout: 5\n", encoding="utf-8")
    monkeypatch.setenv("DATARADAR_API_BASE", "http://new:18000")
    monkeypatch.setenv("DATARADAR_TIMEOUT", "21")
    loaded = load_config(str(config))
    assert loaded["dataradar"] == {"api_base": "http://new:18000", "timeout": 21}
