from datetime import datetime, timezone
from types import SimpleNamespace

from nuclear_energy.extraction.transactions import detect_nuclear_transactions


def _document(**kwargs):
    defaults = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Cernavoda awarded EUR 1.9 billion refurbishment contract",
        "url": "https://example.com/cernavoda-contract",
        "source_name": "Example News",
        "source_kind": "rss",
        "published_at": datetime(2026, 8, 14, tzinfo=timezone.utc),
        "summary": "Nuclearelectrica selected suppliers for nuclear refurbishment work in Romania.",
        "content": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_detect_nuclear_transactions_extracts_country_plant_and_amount():
    transactions = detect_nuclear_transactions([_document()])

    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.country_iso_code == "ROU"
    assert transaction.country_name == "Romania"
    assert transaction.plant_name == "Cernavoda"
    assert transaction.transaction_type == "contract_award"
    assert transaction.amount_text == "EUR 1.9 billion"
    assert transaction.amount == 1_900_000_000
    assert transaction.currency == "EUR"
    assert transaction.confidence >= 0.7
    assert transaction.external_id.startswith("doc-")


def test_detect_nuclear_transactions_infers_country_from_plant_name():
    transactions = detect_nuclear_transactions(
        [
            _document(
                title="Sizewell C signs new engineering agreement",
                summary="A supplier agreement was announced for the nuclear power project.",
            )
        ]
    )

    assert len(transactions) == 1
    assert transactions[0].country_iso_code == "GBR"
    assert transactions[0].plant_name == "Sizewell C"


def test_detect_nuclear_transactions_skips_unlocated_transaction_language():
    transactions = detect_nuclear_transactions(
        [
            _document(
                title="Company announces USD 100 million financing agreement",
                summary="The company said the proceeds would support future clean-energy plans.",
            )
        ]
    )

    assert transactions == []


def test_detect_nuclear_transactions_does_not_treat_document_codes_as_money():
    transactions = detect_nuclear_transactions(
        [
            _document(
                title="Issuance of Multiple Exemptions",
                summary="US nuclear notice identifier 13208USD mentions a data acquisition system.",
            )
        ]
    )

    assert transactions == []
