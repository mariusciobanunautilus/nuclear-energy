from nuclear_energy.models import SourceKind
from nuclear_energy.sources import eur_lex


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_eur_lex_documents_normalizes_sparql_results(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "results": {
                    "bindings": [
                        {
                            "work": {
                                "type": "uri",
                                "value": "http://publications.europa.eu/resource/cellar/example",
                            },
                            "type": {
                                "type": "uri",
                                "value": "http://publications.europa.eu/resource/authority/resource-type/REG",
                            },
                            "celex": {"type": "literal", "value": "32026R0001"},
                            "title": {"type": "literal", "value": "Regulation on nuclear energy safeguards"},
                            "date": {"type": "literal", "value": "2026-08-13"},
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(eur_lex.httpx, "get", fake_get)

    documents = eur_lex.fetch_eur_lex_documents(query="nuclear energy", limit=5, timeout=11.0)

    assert captured["url"] == eur_lex.CELLAR_SPARQL_URL
    assert "application/sparql-results+json" in captured["params"]["format"]
    assert "nuclear" in captured["params"]["query"]
    assert "energy" in captured["params"]["query"]
    assert captured["headers"]["User-Agent"] == eur_lex.USER_AGENT
    assert captured["timeout"] == 11.0
    assert len(documents) == 1
    assert documents[0].source_kind == SourceKind.eur_lex
    assert documents[0].source_name == "EUR-Lex"
    assert documents[0].external_id == "32026R0001"
    assert str(documents[0].url) == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0001"
    assert documents[0].published_at.year == 2026
    assert "Regulation on nuclear energy safeguards" in documents[0].content
    assert "REG" in documents[0].tags


def test_fetch_eur_lex_documents_skips_empty_queries(monkeypatch):
    def fake_get(*_args, **_kwargs):
        raise AssertionError("HTTP should not be called for an empty query")

    monkeypatch.setattr(eur_lex.httpx, "get", fake_get)

    assert eur_lex.fetch_eur_lex_documents(query="a an of", limit=5) == []


def test_fetch_eur_lex_documents_skips_results_without_celex(monkeypatch):
    monkeypatch.setattr(
        eur_lex.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse({"results": {"bindings": [{"title": {"value": "No CELEX"}}]}}),
    )

    assert eur_lex.fetch_eur_lex_documents() == []
