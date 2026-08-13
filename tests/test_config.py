from nuclear_energy.config import _split_csv_env


def test_split_csv_env_trims_empty_values():
    assert _split_csv_env(" https://a.example/feed.xml, ,https://b.example/rss ") == [
        "https://a.example/feed.xml",
        "https://b.example/rss",
    ]


def test_split_csv_env_handles_missing_value():
    assert _split_csv_env(None) == []
