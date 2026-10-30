"""SourceManager 的配置读写与环境变量测试。"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from dataradar.source_manager import SourceManager


def write_config(path: Path) -> None:
    path.write_text(
        "rss:\n  enabled: true\n  feeds: []\nweb_scraper:\n  targets: []\n",
        encoding="utf-8",
    )


def test_source_manager_uses_config_path_environment(tmp_path, monkeypatch):
    config_path = tmp_path / "custom.yaml"
    write_config(config_path)
    monkeypatch.setenv("CONFIG_PATH", str(config_path))

    manager = SourceManager()
    result = manager.add_feed("https://example.com/feed.xml", name="Example Feed")

    assert result["id"] == "example-feed"
    data = YAML(typ="safe").load(config_path.read_text(encoding="utf-8"))
    assert data["rss"]["feeds"][0]["url"] == "https://example.com/feed.xml"


def test_source_manager_initializes_missing_config_from_example(tmp_path):
    config_path = tmp_path / "nested" / "config.yaml"
    example_path = Path(__file__).parents[1] / "config" / "config.example.yaml"
    example_before = example_path.read_bytes()

    manager = SourceManager(str(config_path))
    feeds = manager.list_feeds()
    assert feeds
    assert config_path.exists()

    manager.add_feed("https://example.com/new.xml", id="new", name="New")
    assert b"https://example.com/new.xml" in config_path.read_bytes()
    assert example_path.read_bytes() == example_before


def test_source_manager_source_lifecycle(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    manager = SourceManager(str(config_path))

    manager.add_feed("https://example.com/feed.xml", id="example", name="Example")
    assert manager.list_feeds()[0]["enabled"] is True
    assert manager.disable_source("example") is True
    assert manager.list_feeds()[0]["enabled"] is False
    assert manager.enable_source("example") is True
    assert manager.remove_source("example") is True
    assert manager.list_feeds() == []


def test_source_manager_generates_unique_ids_for_non_ascii_names(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    manager = SourceManager(str(config_path))

    first = manager.add_feed("https://example.com/a.xml", name="科技资讯")
    second = manager.add_feed("https://example.com/b.xml", name="科技资讯")

    assert first["id"] == "example-com"
    assert second["id"] == "example-com-2"
    assert [item["id"] for item in manager.list_feeds()] == ["example-com", "example-com-2"]


def test_source_manager_updates_feed_and_enables_rss(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("rss:\n  enabled: false\n  feeds: []\n", encoding="utf-8")
    manager = SourceManager(str(config_path))

    manager.add_feed("https://example.com/feed.xml", id="example", name="Example")
    result = manager.update_feed(
        "example",
        "https://example.com/updated.xml",
        name="Updated",
        max_age_days=10,
        enabled=True,
    )

    assert result["status"] == "updated"
    assert manager.list_feeds() == [{
        "id": "example",
        "name": "Updated",
        "url": "https://example.com/updated.xml",
        "enabled": True,
        "max_age_days": 10,
        "content_type": "text",
    }]
    assert "enabled: true" in config_path.read_text(encoding="utf-8")

