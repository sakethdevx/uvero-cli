import pytest
import responses

from uvero import api


def test_url_builder():
    assert api._url("/test") == "https://uvero.app/test"


@responses.activate
def test_send_clipboard():
    responses.add(
        responses.POST,
        "https://uvero.app/api/clipboard/send",
        json={"success": True, "data": {"code": "5678"}},
        status=200,
    )
    result = api.send_clipboard("test content")
    assert result["success"] is True
    assert result["data"]["code"] == "5678"


@responses.activate
def test_get_clipboard():
    responses.add(
        responses.GET,
        "https://uvero.app/api/clipboard/get/1234",
        json={"success": True, "data": {"content": "retrieved text"}},
        status=200,
    )
    result = api.get_clipboard("1234")
    assert result["success"] is True
    assert result["data"]["content"] == "retrieved text"


@responses.activate
def test_failed_connection():
    responses.add(
        responses.GET,
        "https://uvero.app/api/clipboard/cli-health",
        body=api.requests.exceptions.ConnectionError("Connection Failed"),
    )
    with pytest.raises(api.UveroServiceConnectionError):
        api.health_check()
