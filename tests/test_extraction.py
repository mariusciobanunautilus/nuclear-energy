import pytest

from nuclear_energy.extraction import text


def test_chunk_text_splits_with_overlap():
    source = " ".join(f"word{i}" for i in range(120))

    chunks = text.chunk_text(source, max_chars=120, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert chunks[0][-20:].strip() in chunks[1]


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        text.chunk_text("content", max_chars=100, overlap=100)


def test_extract_text_from_html_uses_fallback(monkeypatch):
    monkeypatch.setattr(text.trafilatura, "extract", lambda *_args, **_kwargs: None)

    extracted = text.extract_text_from_html(
        """
        <html>
          <body>
            <nav>Navigation</nav>
            <article>
              <h1>Nuclear policy update</h1>
              <p>Research reactors support science and medicine.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/article",
    )

    assert "Nuclear policy update" in extracted
    assert "Research reactors support science and medicine." in extracted
    assert "Navigation" not in extracted
