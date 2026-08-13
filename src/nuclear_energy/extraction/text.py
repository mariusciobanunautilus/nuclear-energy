from __future__ import annotations

import re
from typing import Optional

import httpx
import trafilatura
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs = [line for line in lines if line]
    return "\n\n".join(paragraphs)


def _fallback_extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer", "header"]):
        tag.decompose()

    content = soup.find("article") or soup.find("main") or soup.body or soup
    return normalize_text(content.get_text("\n"))


def extract_text_from_html(html: str, *, url: Optional[str] = None) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if extracted:
        return normalize_text(extracted)
    return _fallback_extract_text(html)


def fetch_article_text(url: str, *, timeout: float = 20.0) -> str:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = _get_with_https_retry(client, url)
    return extract_text_from_html(response.text, url=str(response.url))


def _get_with_https_retry(client: httpx.Client, url: str) -> httpx.Response:
    urls = [url]
    if url.startswith("http://"):
        urls.append("https://" + url.removeprefix("http://"))

    last_error: Optional[Exception] = None
    for candidate in urls:
        try:
            response = client.get(candidate)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code not in {403, 404, 426}:
                raise

    if last_error:
        raise last_error
    raise RuntimeError(f"Could not fetch article URL: {url}")


def chunk_text(text: str, *, max_chars: int = 2500, overlap: int = 250) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must not be negative.")
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars.")

    cleaned = normalize_text(text)
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(start + max_chars, text_length)
        if end < text_length:
            midpoint = start + (max_chars // 2)
            break_candidates = [
                cleaned.rfind("\n\n", start, end),
                cleaned.rfind(". ", start, end),
                cleaned.rfind(" ", midpoint, end),
            ]
            break_at = max(break_candidates)
            if break_at > midpoint:
                end = break_at + 1

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = max(0, end - overlap)
        if next_start > 0:
            word_boundary = cleaned.rfind(" ", 0, next_start)
            if word_boundary > start:
                next_start = word_boundary + 1
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks
