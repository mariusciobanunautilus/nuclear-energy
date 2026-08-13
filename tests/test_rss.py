from nuclear_energy.sources import rss


def test_fetch_rss_feed_normalizes_entries(monkeypatch):
    class Feed:
        feed = {"title": "Example Nuclear Feed"}
        entries = [
            {
                "id": "entry-1",
                "title": "New reactor policy update",
                "link": "https://example.com/reactor-policy",
                "published": "Tue, 11 Aug 2026 10:00:00 GMT",
                "summary": "Short summary",
                "author": "Reporter",
                "tags": [{"term": "policy"}],
            },
            {
                "title": "Skipped because link is missing",
            },
        ]

    monkeypatch.setattr(rss.feedparser, "parse", lambda _url: Feed())

    documents = rss.fetch_rss_feed("https://example.com/rss", limit=10)

    assert len(documents) == 1
    assert documents[0].source_name == "Example Nuclear Feed"
    assert documents[0].external_id == "entry-1"
    assert documents[0].title == "New reactor policy update"
    assert documents[0].authors == ["Reporter"]
    assert documents[0].tags == ["policy"]
