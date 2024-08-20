from typer.testing import CliRunner

from offal.main import app

runner = CliRunner()


def test_status_command(mocker):
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0


def test_revisions_command(mocker):
    result = runner.invoke(app, ["revisions"])

    assert result.exit_code == 0


def test_friends_command(mocker):
    result = runner.invoke(app, ["friends", "src/offal/__main__.py"])

    assert result.exit_code == 0
