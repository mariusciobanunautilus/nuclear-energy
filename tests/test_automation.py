import httpx
import pytest

from nuclear_energy.automation import WorkflowDispatchError, trigger_github_workflow


def test_trigger_github_workflow_posts_dispatch_request(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={
                "workflow_run_id": 12345,
                "url": "https://api.github.com/repos/example/repo/actions/runs/12345",
                "html_url": "https://github.com/example/repo/actions/runs/12345",
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = trigger_github_workflow(
        token="secret-token",
        owner="example",
        repo="repo",
        workflow_id="public-ingest.yml",
        ref="main",
        inputs={"mode": "official-transactions"},
        timeout=9.0,
    )

    assert captured["url"] == "https://api.github.com/repos/example/repo/actions/workflows/public-ingest.yml/dispatches"
    assert captured["json"] == {
        "ref": "main",
        "return_run_details": True,
        "inputs": {"mode": "official-transactions"},
    }
    assert captured["headers"]["Accept"] == "application/vnd.github+json"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["headers"]["X-GitHub-Api-Version"] == "2022-11-28"
    assert captured["timeout"] == 9.0
    assert result.run_id == 12345
    assert result.html_url == "https://github.com/example/repo/actions/runs/12345"


def test_trigger_github_workflow_accepts_no_content_response(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(204))

    result = trigger_github_workflow(
        token="secret-token",
        owner="example",
        repo="repo",
        workflow_id="public-ingest.yml",
        ref="main",
    )

    assert result.status_code == 204
    assert result.html_url


def test_trigger_github_workflow_raises_clear_error(monkeypatch):
    def fake_post(*args, **kwargs):
        return httpx.Response(403, json={"message": "Resource not accessible by token"})

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(WorkflowDispatchError, match="HTTP 403"):
        trigger_github_workflow(
            token="secret-token",
            owner="example",
            repo="repo",
            workflow_id="public-ingest.yml",
            ref="main",
        )
