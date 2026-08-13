from nuclear_energy.models import SourceKind
from nuclear_energy.sources import federal_register


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_federal_register_documents_normalizes_results(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "results": [
                    {
                        "document_number": "2026-12345",
                        "title": "Nuclear Regulatory Commission notice",
                        "html_url": "https://www.federalregister.gov/documents/2026/08/13/2026-12345/example",
                        "publication_date": "2026-08-13",
                        "abstract": "Short abstract",
                        "type": "Notice",
                        "agencies": [{"name": "Nuclear Regulatory Commission"}],
                        "topics": [{"name": "Nuclear Energy"}],
                    }
                ]
            }
        )

    monkeypatch.setattr(federal_register.httpx, "get", fake_get)

    documents = federal_register.fetch_federal_register_documents(query="nuclear", limit=3, timeout=5.0)

    assert captured["url"] == federal_register.FEDERAL_REGISTER_DOCUMENTS_URL
    assert captured["params"]["conditions[term]"] == "nuclear"
    assert captured["params"]["order"] == "newest"
    assert captured["headers"]["User-Agent"] == federal_register.USER_AGENT
    assert captured["timeout"] == 5.0
    assert len(documents) == 1
    assert documents[0].source_kind == SourceKind.federal_register
    assert documents[0].source_name == "Federal Register"
    assert documents[0].external_id == "2026-12345"
    assert documents[0].authors == ["Nuclear Regulatory Commission"]
    assert "Notice" in documents[0].tags
    assert "Nuclear Energy" in documents[0].tags


def test_fetch_federal_register_documents_skips_results_without_url(monkeypatch):
    monkeypatch.setattr(
        federal_register.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse({"results": [{"document_number": "2026-1"}]}),
    )

    assert federal_register.fetch_federal_register_documents() == []
