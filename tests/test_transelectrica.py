from datetime import datetime
from zoneinfo import ZoneInfo

from nuclear_energy.sources import transelectrica


HTML = """
<html>
  <body>
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Putere cerută [MW]</th>
          <th>Putere debitată [MW]</th>
          <th>Nuclear [MW]</th>
          <th>Eolian [MW]</th>
          <th>Hidro [MW]</th>
          <th>Hidrocarburi [MW]</th>
          <th>Carbune [MW]</th>
          <th>Fotovolt [MW]</th>
          <th>Biomasa [MW]</th>
          <th>Stocare [MW]</th>
          <th>Sold^{*} [MW]</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>2026-08-23 00:55:25</td>
          <td>5309</td>
          <td>3751</td>
          <td>0</td>
          <td>340</td>
          <td>1308</td>
          <td>1367</td>
          <td>654</td>
          <td>-13</td>
          <td>60</td>
          <td>33</td>
          <td>1558</td>
        </tr>
        <tr>
          <td>2026-08-23 00:47:12</td>
          <td>5310</td>
          <td>3734</td>
          <td>0</td>
          <td>344</td>
          <td>1303</td>
          <td>1336</td>
          <td>657</td>
          <td>-14</td>
          <td>61</td>
          <td>46</td>
          <td>1576</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_parse_transelectrica_live_generation_html_uses_latest_row() -> None:
    snapshot = transelectrica.parse_transelectrica_live_generation_html(
        HTML,
        source_url="https://example.test/live",
    )

    assert snapshot.country_iso_code == "ROU"
    assert snapshot.country_name == "Romania"
    assert snapshot.observed_at == datetime(2026, 8, 23, 0, 55, 25, tzinfo=ZoneInfo("Europe/Bucharest"))
    assert snapshot.demand_mw == 5309
    assert snapshot.production_mw == 3751
    assert snapshot.nuclear_mw == 0
    assert snapshot.wind_mw == 340
    assert snapshot.hydro_mw == 1308
    assert snapshot.hydrocarbons_mw == 1367
    assert snapshot.coal_mw == 654
    assert snapshot.solar_mw == -13
    assert snapshot.biomass_mw == 60
    assert snapshot.storage_mw == 33
    assert snapshot.net_import_export_mw == 1558
    assert snapshot.source_name == "Transelectrica Live SEN"
    assert snapshot.source_url == "https://example.test/live"
    assert snapshot.raw_payload["source_page"] == transelectrica.TRANSELECTRICA_SEN_URL


def test_fetch_transelectrica_live_generation_uses_public_page(monkeypatch) -> None:
    captured = {}

    def fake_get(url, follow_redirects, headers, timeout):
        captured["url"] = url
        captured["follow_redirects"] = follow_redirects
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(HTML)

    monkeypatch.setattr(transelectrica.httpx, "get", fake_get)

    snapshot = transelectrica.fetch_transelectrica_live_generation(
        url="https://example.test/live",
        timeout=9.0,
    )

    assert captured["url"] == "https://example.test/live"
    assert captured["follow_redirects"] is True
    assert captured["headers"]["User-Agent"] == transelectrica.USER_AGENT
    assert captured["timeout"] == 9.0
    assert snapshot.nuclear_mw == 0


def test_parse_transelectrica_live_generation_html_requires_generation_table() -> None:
    html = "<table><tr><th>Other</th></tr><tr><td>value</td></tr></table>"

    try:
        transelectrica.parse_transelectrica_live_generation_html(html)
    except ValueError as exc:
        assert "live generation table was not found" in str(exc)
    else:
        raise AssertionError("Expected missing table to raise ValueError")
