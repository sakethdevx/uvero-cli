
import pytest
from typer.testing import CliRunner

from uvero.cli import app
from uvero.config import state

runner = CliRunner()

@pytest.fixture(autouse=True)
def reset_state():
    """Reset global CLI state between tests."""
    state.json_output = False
    state.quiet = False
    state.no_color = False
    state.no_emoji = False
    state.config = {}

@pytest.fixture
def mock_api(mocker):
    return mocker.patch("uvero.cli.api")

@pytest.fixture
def mock_clipboard(mocker):
    mocker.patch("uvero.cli.write_clipboard")
    mocker.patch("uvero.cli.read_clipboard", return_value="pasted_content")
    return mocker

def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Uvero CLI v" in result.stdout

def test_version_json():
    result = runner.invoke(app, ["--json", "version"])
    assert result.exit_code == 0
    assert '"version":' in result.stdout

def test_health(mock_api):
    mock_api.health_check.return_value = {"success": True}
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "reachable" in result.stdout

def test_health_json(mock_api):
    mock_api.health_check.return_value = {"success": True}
    result = runner.invoke(app, ["--json", "health"])
    assert result.exit_code == 0
    assert '"status": "healthy"' in result.stdout

def test_send_raw(mock_api, mock_clipboard):
    # Mock pipe stdin reading
    mock_api.send_clipboard.return_value = {"success": True, "data": {"code": "1234"}}
    result = runner.invoke(app, ["send", "-", "--raw"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1234"
    mock_api.send_clipboard.assert_called_once_with("pasted_content")

def test_send_json(mock_api, mock_clipboard):
    mock_api.send_clipboard.return_value = {"success": True, "data": {"code": "4321"}}
    result = runner.invoke(app, ["--json", "send", "-"])
    assert result.exit_code == 0
    assert '"code": "4321"' in result.stdout
    assert '"url":' in result.stdout

def test_get_stdout(mock_api):
    mock_api.get_clipboard.return_value = {"success": True, "data": {"content": "hello world"}}
    result = runner.invoke(app, ["get", "9999", "--stdout"])
    assert result.exit_code == 0
    assert "hello world\n" == result.stdout

def test_config_set_get():
    # Set config
    res1 = runner.invoke(app, ["config", "set", "output_mode", "json"])
    assert res1.exit_code == 0

    # Get config
    res2 = runner.invoke(app, ["config", "get", "output_mode"])
    assert res2.exit_code == 0
    assert "json" in res2.stdout

def test_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Python:" in result.stdout
