from datetime import date

from nuclear_energy.models import SourceKind
from nuclear_energy.sources import eu_ted


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_ted_nuclear_procurements_maps_notice(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "notices": [
                    {
                        "publication-number": "12-2025",
                        "publication-date": "2025-01-02+01:00",
                        "notice-type": "can-standard",
                        "buyer-name": {"eng": ["The Radiation and Nuclear Safety Authority"]},
                        "winner-name": {"eng": ["Nuklex AB"]},
                        "buyer-country": ["FIN"],
                        "total-value": 549159,
                        "total-value-cur": ["EUR"],
                        "classification-cpv": ["09344000", "14733000"],
                        "links": {
                            "html": {
                                "ENG": "https://ted.europa.eu/en/notice/-/detail/12-2025",
                            }
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(eu_ted.httpx, "post", fake_post)

    records = eu_ted.fetch_ted_nuclear_procurements(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        terms=("nuclear", "uranium"),
        limit=3,
        timeout=11.0,
    )

    assert captured["url"] == eu_ted.TED_NOTICE_SEARCH_URL
    assert captured["json"]["query"] == "(FT ~ nuclear OR FT ~ uranium) AND publication-date>=20250101 AND publication-date<=20250131"
    assert captured["headers"]["User-Agent"] == eu_ted.USER_AGENT
    assert captured["timeout"] == 11.0
    assert len(records) == 1

    record = records[0]
    assert record.document.source_kind == SourceKind.eu_ted
    assert record.country_iso_code == "FIN"
    assert record.country_name == "Finland"
    assert record.transaction_type == "fuel_supply"
    assert record.stage == "confirmed_award"
    assert record.amount == 549159
    assert record.amount_text == "EUR 549,159.00"
    assert record.currency == "EUR"
    assert record.counterparties == ["The Radiation and Nuclear Safety Authority", "Nuklex AB"]
    assert record.source_url == "https://ted.europa.eu/en/notice/-/detail/12-2025"
    assert record.transaction_external_id == "eu-ted-12-2025"
