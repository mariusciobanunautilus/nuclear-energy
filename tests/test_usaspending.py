from datetime import date

from nuclear_energy.models import SourceKind
from nuclear_energy.sources import usaspending


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_usaspending_nuclear_awards_maps_official_award(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "results": [
                    {
                        "Award ID": "89243226FNE400212",
                        "Recipient Name": "AMERICAN CENTRIFUGE OPERATING, LLC",
                        "Base Obligation Date": "2026-07-06",
                        "Start Date": "2026-07-06",
                        "End Date": "2036-07-05",
                        "Award Amount": 900000000.0,
                        "Description": "Establish domestic commercial HALEU capacity and begin production of HALEU UF6.",
                        "Awarding Agency": "Department of Energy",
                        "Awarding Sub Agency": "Department of Energy",
                        "Contract Award Type": "DELIVERY ORDER",
                        "generated_internal_id": "CONT_AWD_89243226FNE400212_8900_89243225DNE000022_8900",
                    }
                ]
            }
        )

    monkeypatch.setattr(usaspending.httpx, "post", fake_post)

    records = usaspending.fetch_usaspending_nuclear_awards(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 8, 14),
        terms=("HALEU",),
        limit=5,
        timeout=12.0,
    )

    assert captured["url"] == usaspending.USASPENDING_AWARD_SEARCH_URL
    assert captured["json"]["filters"]["keywords"] == ["HALEU"]
    assert captured["json"]["filters"]["time_period"] == [{"start_date": "2026-01-01", "end_date": "2026-08-14"}]
    assert captured["headers"]["User-Agent"] == usaspending.USER_AGENT
    assert captured["timeout"] == 12.0
    assert len(records) == 1

    record = records[0]
    assert record.document.source_kind == SourceKind.usaspending
    assert record.country_iso_code == "USA"
    assert record.country_name == "United States"
    assert record.transaction_type == "fuel_supply"
    assert record.stage == "confirmed_award"
    assert record.amount == 900000000.0
    assert record.amount_text == "USD 900,000,000.00"
    assert record.currency == "USD"
    assert record.counterparties == [
        "AMERICAN CENTRIFUGE OPERATING, LLC",
        "Department of Energy",
    ]
    assert record.transaction_external_id.startswith("usaspending-CONT_AWD_")
    assert record.document.raw_payload["query_term"] == "HALEU"


def test_fetch_usaspending_nuclear_awards_filters_noisy_visible_matches(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return FakeResponse(
            {
                "results": [
                    {
                        "Award ID": "36C24626F0176",
                        "Recipient Name": "DAIKIN APPLIED AMERICAS INC",
                        "Base Obligation Date": "2026-08-07",
                        "Award Amount": 150758.8,
                        "Description": "COOLING TOWER REFURBISHMENT",
                        "Awarding Agency": "Department of Veterans Affairs",
                        "generated_internal_id": "CONT_AWD_36C24626F0176_3600_GS07F0377V_4730",
                    }
                ]
            }
        )

    monkeypatch.setattr(usaspending.httpx, "post", fake_post)

    assert usaspending.fetch_usaspending_nuclear_awards(terms=("nuclear reactor",), limit=5) == []
