from nuclear_energy import config
from nuclear_energy.config import _split_csv_env


def test_split_csv_env_trims_empty_values():
    assert _split_csv_env(" https://a.example/feed.xml, ,https://b.example/rss ") == [
        "https://a.example/feed.xml",
        "https://b.example/rss",
    ]


def test_split_csv_env_handles_missing_value():
    assert _split_csv_env(None) == []


def test_settings_loads_env_files_from_current_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("RSS_FEEDS", raising=False)
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path / "installed-package")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.local").write_text("RSS_FEEDS=https://a.example/rss,https://b.example/rss\n")

    config.get_settings.cache_clear()
    try:
        assert config.get_settings().rss_feeds == ["https://a.example/rss", "https://b.example/rss"]
    finally:
        config.get_settings.cache_clear()
