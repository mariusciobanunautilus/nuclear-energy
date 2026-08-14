import httpx

from nuclear_energy.cli import _describe_openai_error, _describe_source_http_error, _ingest_energy, build_parser
from nuclear_energy.models import SourceKind


def test_describe_openai_error_explains_exhausted_credits():
    message = _describe_openai_error(Exception("429 insufficient_quota credit_balance_exhausted"))

    assert "credits are exhausted" in message
    assert "https://platform.openai.com/settings/organization/billing" in message


def test_describe_openai_error_explains_missing_key():
    message = _describe_openai_error(Exception("OPENAI_API_KEY is required"))

    assert message == "OPENAI_API_KEY is missing. Add it to .env.local, then rerun this command."


def test_describe_source_http_error_explains_rate_limit():
    request = httpx.Request("GET", "https://api.example.com")
    response = httpx.Response(429, request=request)
    error = httpx.HTTPStatusError("too many requests", request=request, response=response)

    assert _describe_source_http_error("Example", error) == (
        "Example rate limit reached. Wait a few minutes, then rerun this command."
    )


def test_parser_accepts_energy_ingest_country_filters():
    args = build_parser().parse_args(["ingest-energy", "--country", "ROU", "--country", "FRA", "--since-year", "2020"])

    assert args.command == "ingest-energy"
    assert args.country == ["ROU", "FRA"]
    assert args.since_year == 2020


def test_parser_accepts_transaction_detection_options():
    args = build_parser().parse_args(["detect-transactions", "--limit", "25", "--min-confidence", "0.6"])

    assert args.command == "detect-transactions"
    assert args.limit == 25
    assert args.min_confidence == 0.6
    assert args.replace_detected is True


def test_parser_accepts_event_detection_options():
    args = build_parser().parse_args(["detect-events", "--limit", "25", "--min-confidence", "0.7"])

    assert args.command == "detect-events"
    assert args.limit == 25
    assert args.min_confidence == 0.7


def test_parser_can_keep_existing_transaction_rows():
    args = build_parser().parse_args(["detect-transactions", "--keep-existing"])

    assert args.replace_detected is False


def test_parser_accepts_event_sync_options():
    args = build_parser().parse_args(["sync-events", "--limit", "25"])

    assert args.command == "sync-events"
    assert args.limit == 25


def test_parser_accepts_relationship_sync_options():
    args = build_parser().parse_args(["sync-relationships", "--limit", "25"])

    assert args.command == "sync-relationships"
    assert args.limit == 25


def test_parser_accepts_usaspending_ingest_options():
    args = build_parser().parse_args(
        [
            "ingest-usaspending",
            "--limit",
            "10",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-08-14",
            "--term",
            "HALEU",
        ]
    )

    assert args.command == "ingest-usaspending"
    assert args.limit == 10
    assert args.start_date.isoformat() == "2026-01-01"
    assert args.end_date.isoformat() == "2026-08-14"
    assert args.term == ["HALEU"]


def test_parser_accepts_eu_ted_ingest_options():
    args = build_parser().parse_args(["ingest-eu-ted", "--limit", "15", "--term", "uranium"])

    assert args.command == "ingest-eu-ted"
    assert args.limit == 15
    assert args.term == ["uranium"]


def test_parser_accepts_stage_one_operator_commands():
    repair_args = build_parser().parse_args(["repair-source-tiers"])
    report_args = build_parser().parse_args(["completeness-report"])

    assert repair_args.command == "repair-source-tiers"
    assert report_args.command == "completeness-report"


def test_energy_ingest_records_success(monkeypatch):
    records = [object(), object()]
    calls = []

    monkeypatch.setattr("nuclear_energy.cli.fetch_ember_yearly_electricity", lambda **kwargs: records)
    monkeypatch.setattr("nuclear_energy.cli.upsert_country_energy_years", lambda rows: len(rows))
    monkeypatch.setattr(
        "nuclear_energy.cli._record_ingestion_success",
        lambda *args: calls.append(args),
    )

    args = build_parser().parse_args(["ingest-energy", "--since-year", "2020"])

    assert _ingest_energy(args) == 0
    assert calls == [(SourceKind.eia, "Ember Yearly Electricity Data", 2, 2)]
