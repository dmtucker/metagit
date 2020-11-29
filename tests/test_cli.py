"""Test the metagit CLI."""


import os.path
from pathlib import Path
import subprocess
import sys

from click.testing import CliRunner

from metagit import __version__, MetagitError, MetagitProject, MetagitRepo
from metagit import __main__ as cli

from util import git_repo_for_metagit_repo, non_metagit_dir_project, rm_rf


# @click.command changes function parameters at runtime:
# pylint: disable=no-value-for-parameter


def test_python_m():
    """Test python -m."""
    command = [sys.executable, "-m", "metagit"]
    assert subprocess.run(command, check=False).returncode == 0


def test_main():
    """Test invocation with no arguments matches --help."""
    runner = CliRunner()
    no_args_result = runner.invoke(cli.main, [])
    assert no_args_result.exit_code == 0
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert no_args_result.output == help_result.output


def test_main_debug():
    """`metagit --debug` shows tracebacks instead of failing gracefully."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["--no-debug", "status"])
        assert result.exit_code != 0
        assert isinstance(result.exception, SystemExit)
        result = runner.invoke(cli.main, ["--debug", "status"])
        assert result.exit_code != 0
        assert isinstance(result.exception, MetagitError)


def test_main_path(nonempty_repo):
    """`metagit -C` changes the repo path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["status"])
        assert result.exit_code != 0
        assert "not a metagit repository" in result.output
        result = runner.invoke(cli.main, ["-C", str(nonempty_repo.path()), "status"])
        assert result.exit_code == 0
        assert result.output == ""


def test_main_version():
    """Test --version."""
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init():
    """`metagit init` creates a new repo."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        metagit_dir = Path(MetagitRepo.METAGIT_DIR_NAME).resolve()
        assert not metagit_dir.exists()
        result = runner.invoke(cli.main, ["init"])
        assert result.exit_code == 0
        assert "Initialized" in result.output
        assert metagit_dir.is_dir(), result.output


def test_add(repo):
    """`metagit add` tracks a project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        git_repo = git_repo_for_metagit_repo(repo)
        project = MetagitProject.for_path(git_repo.git_dir)
        assert project not in repo.projects()
        result = runner.invoke(cli.main, ["-C", repo.path(), "add", git_repo.git_dir])
        assert result.exit_code == 0
        assert result.output == ""
        assert project in repo.projects()


def test_add_relative(repo):
    """`metagit add` tracks a project specified by relative path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        git_repo = git_repo_for_metagit_repo(repo)
        project = MetagitProject.for_path(git_repo.git_dir)
        assert project not in repo.projects()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli.main,
                ["-C", repo.path(), "add", os.path.relpath(git_repo.git_dir)],
            )
            assert result.exit_code == 0
            assert result.output == ""
        assert project in repo.projects()


def test_rm(nonempty_repo):
    """`metagit rm` untracks a project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        project = next(nonempty_repo.projects())
        result = runner.invoke(
            cli.main,
            ["-C", nonempty_repo.path(), "rm", str(project.path)],
        )
        assert result.exit_code == 0
        assert result.output == ""
        assert project not in nonempty_repo.projects()


def test_rm_relative(nonempty_repo):
    """`metagit rm` untracks a project specified by relative path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        project = next(nonempty_repo.projects())
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli.main,
                ["-C", nonempty_repo.path(), "rm", os.path.relpath(project.path)],
            )
            assert result.exit_code == 0
            assert result.output == ""
        assert project not in nonempty_repo.projects()


def test_restore(nonempty_repo):
    """`metagit restore` overwrites un-added changes to a project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        project = non_metagit_dir_project(nonempty_repo)
        rm_rf(project.path)
        assert nonempty_repo.diff_project(project)
        result = runner.invoke(
            cli.main,
            ["-C", nonempty_repo.path(), "restore", str(project.path)],
        )
        assert result.exit_code == 0
        assert result.output == ""
        assert not nonempty_repo.diff_project(project)


def test_restore_relative(nonempty_repo):
    """`metagit restore` restores a project specified by relative path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        project = non_metagit_dir_project(nonempty_repo)
        rm_rf(project.path)
        assert nonempty_repo.diff_project(project)
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli.main,
                ["-C", nonempty_repo.path(), "restore", os.path.relpath(project.path)],
            )
            assert result.exit_code == 0
            assert result.output == ""
        assert not nonempty_repo.diff_project(project)


def test_diff_clean(repo):
    """`metagit diff` produces no output in a clean repository."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["-C", repo.path(), "diff"])
        assert result.exit_code == 0


def test_diff_dirty(nonempty_repo):
    """`metagit diff` produces output in a dirty repository."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_path = nonempty_repo.path()
        project = non_metagit_dir_project(nonempty_repo)
        rm_rf(project.path)
        result = runner.invoke(cli.main, ["-C", repo_path, "diff"])
        assert result.exit_code == 0
        assert project.path.name in result.output


def test_status_clean_empty(empty_repo):
    """`metagit status` produces output in a clean, empty repository."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["-C", empty_repo.path(), "status"])
        assert result.exit_code == 0
        assert "No projects" in result.output
        assert "Changes" not in result.output
        assert "Untracked" in result.output
        assert MetagitRepo.METAGIT_DIR_NAME in result.output


def test_status_clean(nonempty_repo):
    """`metagit status` produces no output in a clean, nonempty repository."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli.main, ["-C", nonempty_repo.path(), "status"])
        assert result.exit_code == 0
        assert result.output == ""


def test_status_deleted(nonempty_repo):
    """`metagit status` produces output if a project has been deleted."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_path = nonempty_repo.path()
        project = non_metagit_dir_project(nonempty_repo)
        rm_rf(project.path)
        result = runner.invoke(cli.main, ["-C", repo_path, "status"])
        assert result.exit_code == 0
        assert "Changes" in result.output
        assert "deleted" in result.output
        assert project.path.name in result.output
        assert "modified" not in result.output
        assert "Untracked" not in result.output


def test_status_modified(nonempty_repo):
    """`metagit status` produces output if a project has been modified."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        repo_path = nonempty_repo.path()
        project = non_metagit_dir_project(nonempty_repo)
        rm_rf(project.path / ".git" / "config")
        result = runner.invoke(cli.main, ["-C", repo_path, "status"])
        assert result.exit_code == 0
        assert "Changes" in result.output
        assert "deleted" not in result.output
        assert "modified" in result.output
        assert project.path.name in result.output
        assert "Untracked" not in result.output


def test_status_untracked(repo):
    """`metagit status` produces output if there is an untracked project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        git_repo = git_repo_for_metagit_repo(repo)
        result = runner.invoke(cli.main, ["-C", repo.path(), "status"])
        assert result.exit_code == 0
        assert "Changes" not in result.output
        assert "Untracked" in result.output
        assert any(
            str(parent) in result.output for parent in Path(git_repo.git_dir).parents
        )
