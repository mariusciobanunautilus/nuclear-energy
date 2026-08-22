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


def test_fetch_rss_feed_uses_known_title_when_feed_title_is_missing(monkeypatch):
    class Feed:
        feed = {}
        entries = [
            {
                "id": "status-1",
                "title": "Power reactor status update",
                "link": "https://www.nrc.gov/status",
            },
        ]

    monkeypatch.setattr(rss.feedparser, "parse", lambda _url: Feed())

    documents = rss.fetch_rss_feed("https://www.nrc.gov/public-involve/rss?feed=plant-status", limit=1)

    assert documents[0].source_name == "NRC Power Reactor Status"


def test_fetch_rss_feed_prefers_known_title_over_generic_feed_title(monkeypatch):
    class Feed:
        feed = {"title": "Rss News"}
        entries = [
            {
                "id": "onr-1",
                "title": "ONR update",
                "link": "https://www.onr.org.uk/update",
            },
        ]

    monkeypatch.setattr(rss.feedparser, "parse", lambda _url: Feed())

    documents = rss.fetch_rss_feed("https://www.onr.org.uk/rss-news", limit=1)

    assert documents[0].source_name == "UK Office for Nuclear Regulation News"


def test_fetch_rss_feeds_skips_duplicate_entries_across_feeds(monkeypatch):
    def parse(feed_url):
        class Feed:
            feed = {"title": feed_url}
            entries = [
                {
                    "id": "shared-entry",
                    "title": f"Shared update from {feed_url}",
                    "link": f"{feed_url}/shared",
                },
                {
                    "id": f"unique-{feed_url}",
                    "title": f"Unique update from {feed_url}",
                    "link": f"{feed_url}/unique",
                },
            ]

        return Feed()

    monkeypatch.setattr(rss.feedparser, "parse", parse)

    documents = rss.fetch_rss_feeds(["https://example.com/a", "https://example.com/b"])

    assert [document.external_id for document in documents] == [
        "shared-entry",
        "unique-https://example.com/a",
        "unique-https://example.com/b",
    ]
