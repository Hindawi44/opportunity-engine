from urllib.request import Request

from opportunity_engine.discovery.checkpoint_state_restore import (
    _CrossOriginAuthorizationRedirectHandler,
)


def _redirected_request(source_url: str, target_url: str) -> Request:
    request = Request(
        source_url,
        headers={
            "Authorization": "Bearer repository-token",
            "Accept": "application/vnd.github+json",
            "User-Agent": "checkpoint-test",
        },
    )
    redirected = _CrossOriginAuthorizationRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        target_url,
    )
    assert redirected is not None
    return redirected


def test_cross_origin_artifact_redirect_strips_authorization() -> None:
    redirected = _redirected_request(
        "https://api.github.com/repos/example/repo/actions/artifacts/123/zip",
        "https://productionresultssa.blob.core.windows.net/actions-results/signed.zip",
    )

    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("Accept") == "application/vnd.github+json"
    assert redirected.get_header("User-agent") == "checkpoint-test"


def test_same_origin_redirect_preserves_authorization() -> None:
    redirected = _redirected_request(
        "https://api.github.com/repos/example/repo/actions/artifacts/123/zip",
        "https://api.github.com/repos/example/repo/actions/artifacts/123/archive",
    )

    assert redirected.get_header("Authorization") == "Bearer repository-token"
