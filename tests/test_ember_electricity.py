from nuclear_energy.sources import ember_electricity


CSV_TEXT = """Area,ISO 3 code,Year,Area type,Electricity source,Generation (TWh),Share of generation (%),Capacity (GW)
Romania,ROU,2024,Country or economy,Nuclear,10.5,19.8,1.4
Romania,ROU,2024,Country or economy,Demand,55.0,,0
Romania,ROU,2024,Country or economy,Total generation,53.0,,0
Romania,ROU,2024,Country or economy,Net imports,-2.0,,0
Romania,ROU,2024,Country or economy,Fossil,18.0,,0
Romania,ROU,2024,Country or economy,Renewables,24.5,,0
Romania,ROU,2024,Country or economy,Clean,35.0,,0
Austria,AUT,2024,Country or economy,Nuclear,0.0,0.0,0.0
Austria,AUT,2024,Country or economy,Demand,70.0,,0
Europe,,2024,Region,Nuclear,600.0,20.0,100.0
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_parse_ember_yearly_electricity_csv_keeps_nuclear_country_rows():
    records = ember_electricity.parse_ember_yearly_electricity_csv(
        CSV_TEXT,
        source_url="https://example.com/ember.csv",
        since_year=2024,
    )

    assert len(records) == 1
    record = records[0]
    assert record.iso_code == "ROU"
    assert record.country_name == "Romania"
    assert record.year == 2024
    assert record.nuclear_generation_twh == 10.5
    assert record.nuclear_share_electricity_percent == 19.8
    assert record.nuclear_capacity_gw == 1.4
    assert record.electricity_generation_twh == 53.0
    assert record.electricity_demand_twh == 55.0
    assert record.net_electricity_imports_twh == -2.0
    assert record.source_url == "https://example.com/ember.csv"
    assert "Nuclear" in record.raw_payload["ember_sources"]


def test_parse_ember_yearly_electricity_csv_can_filter_requested_countries():
    records = ember_electricity.parse_ember_yearly_electricity_csv(
        CSV_TEXT,
        since_year=2024,
        iso_codes=["aut"],
    )

    assert len(records) == 1
    assert records[0].iso_code == "AUT"
    assert records[0].nuclear_generation_twh == 0.0


def test_fetch_ember_yearly_electricity_uses_public_csv(monkeypatch):
    captured = {}

    def fake_get(url, follow_redirects, headers, timeout):
        captured["url"] = url
        captured["follow_redirects"] = follow_redirects
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(CSV_TEXT)

    monkeypatch.setattr(ember_electricity.httpx, "get", fake_get)

    records = ember_electricity.fetch_ember_yearly_electricity(
        url="https://example.com/ember.csv",
        since_year=2024,
        timeout=12.0,
    )

    assert captured["url"] == "https://example.com/ember.csv"
    assert captured["follow_redirects"] is True
    assert captured["headers"]["User-Agent"] == ember_electricity.USER_AGENT
    assert captured["timeout"] == 12.0
    assert [record.iso_code for record in records] == ["ROU"]
