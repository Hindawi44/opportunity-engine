import json

import pytest
import requests

from scripts.run_finn_email_intake import _json_object


def _response(payload: object, *, status_code: int = 400) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://oauth2.googleapis.com/token"
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode("utf-8")
    return response


def test_oauth_failure_exposes_only_provider_error_code() -> None:
    response = _response({
        "error": "invalid_grant",
        "error_description": "sensitive provider detail must not be logged",
    })

    with pytest.raises(RuntimeError) as captured:
        _json_object(response, label="Gmail OAuth token endpoint")

    assert str(captured.value) == (
        "Gmail OAuth token endpoint rejected the request: invalid_grant"
    )
    assert "sensitive provider detail" not in str(captured.value)


def test_non_json_failure_exposes_only_http_status() -> None:
    response = requests.Response()
    response.status_code = 400
    response.url = "https://oauth2.googleapis.com/token"
    response._content = b"not-json-and-never-logged"

    with pytest.raises(RuntimeError) as captured:
        _json_object(response, label="Gmail OAuth token endpoint")

    assert str(captured.value) == (
        "Gmail OAuth token endpoint rejected the request: http_400"
    )
    assert "not-json-and-never-logged" not in str(captured.value)
