from typer.testing import CliRunner

from offal.main import app

runner = CliRunner()


def test_status_command(mocker):
    repo_mock = mocker.patch("git.Repo", autospec=True)
    repo_mock.return_value.git.reg_list.return_value = "10"
    repo_mock.return_value.git.ls_files.return_value = "file1.py\nfile2.py"
    repo_mock.return_value.git.shortlog.return_value = "1\tAuthor1\n2\tAuthor2"

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Number of Commits" in result.output
    assert "Number of Entities" in result.output
    assert "Number of Authors" in result.output


def test_revisions_command(mocker):
    result = runner.invoke(app, ["revisions"])

    assert result.exit_code == 0


def test_friends_command(mocker):
    result = runner.invoke(app, ["friends", "src/offal/__main__.py"])

    assert result.exit_code == 0
