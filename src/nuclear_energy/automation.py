from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import httpx


GITHUB_API_VERSION = "2022-11-28"
GITHUB_ACTIONS_URL = "https://github.com/mariusciobanunautilus/nuclear-energy/actions/workflows/public-ingest.yml"


class WorkflowDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkflowDispatchResult:
    status_code: int
    run_id: int | None = None
    api_url: str | None = None
    html_url: str | None = None


def trigger_github_workflow(
    *,
    token: str,
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str,
    inputs: Mapping[str, str] | None = None,
    timeout: float = 20.0,
) -> WorkflowDispatchResult:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
    payload: dict[str, object] = {
        "ref": ref,
        "return_run_details": True,
    }
    if inputs:
        payload["inputs"] = dict(inputs)

    response = httpx.post(
        url,
        json=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        timeout=timeout,
    )
    if response.status_code not in {200, 204}:
        raise WorkflowDispatchError(_dispatch_error_message(response))

    if response.status_code == 204 or not response.content:
        return WorkflowDispatchResult(status_code=response.status_code, html_url=GITHUB_ACTIONS_URL)

    data = response.json()
    return WorkflowDispatchResult(
        status_code=response.status_code,
        run_id=_optional_int(data.get("workflow_run_id") or data.get("run_id") or data.get("id")),
        api_url=_optional_string(data.get("url") or data.get("api_url")),
        html_url=_optional_string(data.get("html_url") or data.get("workflow_url")) or GITHUB_ACTIONS_URL,
    )


def _dispatch_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        detail = str(payload.get("message") or payload)
    return f"GitHub workflow dispatch failed with HTTP {response.status_code}: {detail}"


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
