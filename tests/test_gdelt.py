from nuclear_energy.models import SourceKind
from nuclear_energy.sources import gdelt


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_gdelt_documents_normalizes_articles(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "articles": [
                    {
                        "url": "https://example.com/nuclear",
                        "title": "Nuclear energy update",
                        "seendate": "20260813104500",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    }
                ]
            }
        )

    monkeypatch.setattr(gdelt.httpx, "get", fake_get)

    documents = gdelt.fetch_gdelt_documents(query="nuclear", limit=5, timespan="1day", timeout=7.0)

    assert captured["url"] == gdelt.GDELT_DOC_API_URL
    assert captured["params"]["mode"] == "artlist"
    assert captured["params"]["format"] == "json"
    assert captured["params"]["query"] == "nuclear"
    assert captured["params"]["timespan"] == "1day"
    assert captured["headers"]["User-Agent"] == gdelt.USER_AGENT
    assert captured["timeout"] == 7.0
    assert len(documents) == 1
    assert documents[0].source_kind == SourceKind.gdelt
    assert documents[0].source_name == "GDELT DOC 2.0"
    assert documents[0].external_id == "https://example.com/nuclear"
    assert documents[0].published_at.year == 2026
    assert "example.com" in documents[0].tags


def test_fetch_gdelt_documents_skips_articles_without_url(monkeypatch):
    monkeypatch.setattr(gdelt.httpx, "get", lambda *_args, **_kwargs: FakeResponse({"articles": [{"title": "No URL"}]}))

    assert gdelt.fetch_gdelt_documents() == []
