from nuclear_energy.extraction.resolution import match_entity_mentions


def test_match_entity_mentions_returns_canonical_entities():
    matches = match_entity_mentions("Centrus and U.S. DOE discussed HALEU with Orano.")

    names = {match["canonical_name"] for match in matches}

    assert "Centrus Energy" in names
    assert "U.S. Department of Energy" in names
    assert "Orano" in names
