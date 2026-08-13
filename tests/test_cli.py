from nuclear_energy.cli import _describe_openai_error


def test_describe_openai_error_explains_exhausted_credits():
    message = _describe_openai_error(Exception("429 insufficient_quota credit_balance_exhausted"))

    assert "credits are exhausted" in message
    assert "https://platform.openai.com/settings/organization/billing" in message


def test_describe_openai_error_explains_missing_key():
    message = _describe_openai_error(Exception("OPENAI_API_KEY is required"))

    assert message == "OPENAI_API_KEY is missing. Add it to .env.local, then rerun this command."
