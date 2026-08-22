from nuclear_energy import config
from nuclear_energy.config import DEFAULT_RSS_FEEDS, DEFAULT_WATCHLIST_ENTITIES, _split_csv_env


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


def test_settings_uses_default_rss_feeds(monkeypatch):
    monkeypatch.delenv("RSS_FEEDS", raising=False)

    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert settings.rss_feeds == DEFAULT_RSS_FEEDS
        assert "https://www.iaea.org/feeds/topnews" in settings.rss_feeds
        assert "https://www.nrc.gov/public-involve/rss?feed=news" in settings.rss_feeds
        assert "https://www.nrc.gov/public-involve/rss?feed=plant-status" in settings.rss_feeds
        assert "https://www.onr.org.uk/rss-news" in settings.rss_feeds
        assert "https://reglementation-controle.asnr.fr/rss/arrets_reacteur" in settings.rss_feeds
        assert "https://www.nuclearelectrica.ro/snn/en/feed/" in settings.rss_feeds
    finally:
        config.get_settings.cache_clear()


def test_settings_loads_watchlist_values(monkeypatch):
    monkeypatch.setenv("WATCHLIST_ENTITIES", "Westinghouse, Cameco")
    monkeypatch.setenv("WATCHLIST_PROJECTS", "Cernavoda, Sizewell C")
    monkeypatch.setenv("WATCHLIST_COUNTRIES", "USA, ROU")
    monkeypatch.setenv("WATCHLIST_THEMES", "fuel_cycle, policy")

    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert settings.watchlist_entities == ["Westinghouse", "Cameco"]
        assert settings.watchlist_projects == ["Cernavoda", "Sizewell C"]
        assert settings.watchlist_countries == ["USA", "ROU"]
        assert settings.watchlist_themes == ["fuel_cycle", "policy"]
    finally:
        config.get_settings.cache_clear()


def test_settings_uses_default_trader_watchlist(monkeypatch):
    monkeypatch.delenv("WATCHLIST_ENTITIES", raising=False)
    monkeypatch.delenv("WATCHLIST_PROJECTS", raising=False)
    monkeypatch.delenv("WATCHLIST_COUNTRIES", raising=False)
    monkeypatch.delenv("WATCHLIST_THEMES", raising=False)

    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert settings.watchlist_entities == DEFAULT_WATCHLIST_ENTITIES
        assert "Cernavoda" in settings.watchlist_projects
        assert "USA" in settings.watchlist_countries
        assert "fuel_cycle" in settings.watchlist_themes
    finally:
        config.get_settings.cache_clear()
