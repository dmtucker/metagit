"""Test the metagit API."""


import os
from pathlib import Path

import git
import pytest

import metagit as api

from util import git_repo_for_metagit_repo, non_metagit_dir_project, rm_rf


def test_error_invalid_project(tmp_path):
    """Ensure InvalidProjectError says the project is not valid."""
    assert "not a metagit project" in str(api.InvalidProjectError(tmp_path))


def test_error_invalid_repo(tmp_path):
    """Ensure InvalidRepoError says the path is not a metagit repository."""
    assert "not a metagit repository" in str(api.InvalidRepoError(tmp_path))


def test_error_invalid_repo_path(tmp_path):
    """Ensure InvalidRepoPathError says the path is not in a metagit repository."""
    error_str = str(api.InvalidRepoPathError(tmp_path))
    assert "not a metagit repository" in error_str
    assert "parent" in error_str


def test_error_not_in_repo(tmp_path, repo):
    """Ensure NotInRepoError mentions the problematic path and repo."""
    error_str = str(api.NotInRepoError(tmp_path, repo))
    assert str(tmp_path) in error_str
    assert str(repo.path()) in error_str


def test_project_eq(project):
    """Distinct MetagitProject instances for the same project are equal."""
    assert project == api.MetagitProject(project.path)


def test_project_for_path_absolute(project, path_type):
    """MetagitProject.for_path succeeds on good, absolute paths."""
    assert project == api.MetagitProject.for_path(path_type(project.path))


@pytest.mark.parametrize(
    "child",
    [
        # nonproject, nonexistent:
        Path("/tmp") / "nonexistent" / "subdir",
        # nonproject, exists:
        Path("/tmp"),
        # project, nonexistent:
        Path(".git") / "nonexistent" / "subdir",
        # project, exists:
        Path(".git") / "config",
    ],
)
def test_project_for_path_absolute_fail(project, child, path_type):
    """MetagitProject.for_path fails on absolute, non-project paths."""
    path = project.path / child
    with pytest.raises(api.InvalidProjectError, match=str(path)):
        api.MetagitProject.for_path(path_type(path))


def test_project_for_path_relative(project, monkeypatch, tmp_path, path_type):
    """MetagitProject.for_path succeeds on good, relative paths."""
    monkeypatch.chdir(tmp_path)
    assert project == api.MetagitProject.for_path(
        path_type(os.path.relpath(project.path)),
    )


@pytest.mark.parametrize(
    "child",
    [
        # nonproject, nonexistent:
        Path("/tmp") / "nonexistent" / "subdir",
        # nonproject, exists:
        Path("/tmp"),
        # project, nonexistent:
        Path(".git") / "nonexistent" / "subdir",
        # project, exists:
        Path(".git") / "config",
    ],
)
def test_project_for_path_relative_fail(
    project,
    child,
    monkeypatch,
    tmp_path,
    path_type,
):
    """MetagitProject.for_path fails on relative, non-project paths."""
    monkeypatch.chdir(tmp_path)
    path = os.path.relpath(project.path / child)
    with pytest.raises(api.InvalidProjectError, match=str(path)):
        api.MetagitProject.for_path(path_type(path))


def test_project_get_config_empty(project):
    """MetagitProject.get_config equates a missing .git/config and a blank one."""
    (project.path / ".git" / "config").unlink()
    assert project.get_config() == b""


def test_project_get_config_invalid(tmp_path):
    """MetagitProject.get_config raises an exception for invalid projects."""
    with pytest.raises(api.InvalidProjectError, match=str(tmp_path)):
        api.MetagitProject(tmp_path).get_config()


def test_project_get_config_remote(project):
    """MetagitProject.get_config results change if a remote is added to the project."""
    config = project.get_config()
    git.Repo(project.path).create_remote("test_project_get_config_remote", "a@b.c:d")
    assert config != project.get_config()


def test_project_hash(project):
    """A MetagitProject is hashable."""
    assert isinstance(hash(project), int)


def test_project_set_config_create(project):
    """MetagitRepo.restore_project creates nonexistent projects."""
    config = project.get_config()
    rm_rf(project.path)
    project.set_config(config)
    assert config == project.get_config()


def test_project_set_config_fail(project):
    """MetagitProject.set_config raises an appropriate exception on failure."""
    rm_rf(project.path)
    project.path.mkdir(0o555)
    with pytest.raises(api.InvalidProjectError, match=str(project.path)):
        project.set_config(b"")


def test_repo_add_project(request):
    """MetagitRepo.add_project succeeds when adding a valid Git repo."""
    assert any(request.getfixturevalue("nonempty_repo").projects())


def test_repo_add_project_invalid_repo(tmp_path, project_type):
    """MetagitRepo.add_project raises an exception if the repo is not valid."""
    repo = api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME)
    git_repo = git_repo_for_metagit_repo(repo)
    with pytest.raises(api.InvalidRepoError, match=str(repo.metagit_dir)):
        repo.add_project(project_type(git_repo.git_dir))


def test_repo_add_project_nonexistent(repo, project_type):
    """MetagitRepo.add_project raises an exception if the path does not exist."""
    path = repo.path() / "nonexistent"
    with pytest.raises(api.InvalidProjectError, match=str(path)):
        repo.add_project(project_type(path))


def test_repo_add_project_nongit(repo, project_type):
    """MetagitRepo.add_project raises an exception if the path is not a git repo."""
    path = repo.path() / "nongit"
    path.mkdir()
    with pytest.raises(api.InvalidProjectError, match=str(path)):
        repo.add_project(project_type(path))


def test_repo_add_project_not_in_repo(empty_repo, nonempty_repo, project_type):
    """MetagitRepo.add_project raises an exception if the path is not in the repo."""
    path = next(nonempty_repo.projects()).path
    with pytest.raises(api.NotInRepoError, match=str(path)):
        empty_repo.add_project(project_type(path))


def test_repo_diff_project(nonempty_repo, project_type):
    """MetagitRepo.diff_project returns an empty string if the project is clean."""
    assert "" == nonempty_repo.diff_project(
        project_type(next(nonempty_repo.projects()).path),
    )


def test_repo_diff_project_changed(nonempty_repo, project_type):
    """MetagitRepo.diff_project returns an empty string if the project is clean."""
    project = next(nonempty_repo.projects())
    git.Repo(project.path).create_remote("test_repo_diff_project_changed", "a@b.c:d")
    assert nonempty_repo.diff_project(project_type(project.path)) != ""


def test_repo_diff_project_invalid_repo(tmp_path, project_type):
    """MetagitRepo.diff_project raises an exception if the repo is not valid."""
    repo = api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME)
    git_repo = git_repo_for_metagit_repo(repo)
    with pytest.raises(api.InvalidRepoError, match=str(tmp_path)):
        repo.diff_project(project_type(git_repo.git_dir))


def test_repo_diff_project_nonexistent(repo, project_type):
    """MetagitRepo.diff_project raises an exception for a nonexistent project."""
    path = repo.path() / "nonexistent"
    with pytest.raises(api.UntrackedProjectError, match=str(path)):
        repo.diff_project(project_type(path))


def test_repo_diff_project_not_in_repo(repo, tmp_path, project_type):
    """MetagitRepo.diff_project raises an exception if a project is not in the repo."""
    git_repo = git_repo_for_metagit_repo(
        api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME),
    )
    with pytest.raises(api.NotInRepoError, match=str(tmp_path)):
        repo.diff_project(project_type(git_repo.git_dir))


def test_repo_diff_project_relative(nonempty_repo, project_type):
    """MetagitRepo.diff_project works on relative paths."""
    project = next(nonempty_repo.projects())
    git.Repo(project.path).create_remote("test_repo_diff_project_changed", "a@b.c:d")
    assert nonempty_repo.diff_project(project_type(os.path.relpath(project.path))) != ""


def test_repo_diff_project_untracked(repo, tmp_path, project_type):
    """MetagitRepo.diff_project raises an exception for an untracked project."""
    git_repo = git_repo_for_metagit_repo(repo)
    with pytest.raises(api.UntrackedProjectError, match=git_repo.git_dir):
        repo.diff_project(project_type(git_repo.git_dir))


def test_repo_eq(repo):
    """Distinct MetagitRepo instances for the same repo are equal."""
    assert repo == api.MetagitRepo(repo.metagit_dir)


def test_repo_for_path(repo, path_type, search_parent_directories):
    """MetagitRepo.for_path works for paths to the repo."""
    assert repo == api.MetagitRepo.for_path(
        path_type(repo.path()),
        search_parent_directories=search_parent_directories,
    )


def test_repo_for_path_metagit(repo, path_type):
    """MetagitRepo.for_path works for paths to the .metagit directory."""
    assert repo == api.MetagitRepo.for_path(
        path_type(repo.metagit_dir),
        search_parent_directories=True,
    )


def test_repo_for_path_not_in_repo(
    tmp_path_factory,
    path_type,
    search_parent_directories,
):
    """MetagitRepo.for_path raises an exception for paths not in a repo."""
    path = tmp_path_factory.mktemp("projects")
    with pytest.raises(api.InvalidRepoError, match=str(path)):
        api.MetagitRepo.for_path(
            path_type(path),
            search_parent_directories=search_parent_directories,
        )


def test_repo_for_path_search_parent_directories(repo, path_type):
    """MetagitRepo.for_path finds repos in parent directories when requested."""
    child_path = repo.path() / "child"
    with pytest.raises(api.InvalidRepoError, match=str(child_path)):
        api.MetagitRepo.for_path(
            path_type(child_path),
            search_parent_directories=False,
        )
    assert repo == api.MetagitRepo.for_path(
        child_path,
        search_parent_directories=True,
    )


def test_repo_for_path_search_parent_directories_fail(tmp_path, path_type):
    """MetagitRepo.for_path raises an exception if no parents are a valid repo."""
    with pytest.raises(api.InvalidRepoPathError, match=str(tmp_path)):
        api.MetagitRepo.for_path(path_type(tmp_path), search_parent_directories=True)


def test_repo_hash(repo):
    """A MetagitRepo is hashable."""
    assert isinstance(hash(repo), int)


def test_repo_init(tmp_path_factory, path_type):
    """MetagitRepo.init creates a repo."""
    repo = api.MetagitRepo.init(path_type(tmp_path_factory.mktemp("test_repo_init")))
    git.Repo(repo.metagit_dir, search_parent_directories=False)


def test_repo_init_exists(repo, path_type):
    """MetagitRepo.init succeeds when called on an existing repo."""
    assert repo == api.MetagitRepo.init(path_type(repo.path()))


def test_repo_init_fail(monkeypatch, tmp_path_factory, path_type):
    """MetagitRepo.init raises an exception if initialization fails."""

    def raise_git_error(*args, **kwargs):
        raise git.GitError

    monkeypatch.setattr(git.Repo, "init", raise_git_error)
    path = (
        tmp_path_factory.mktemp("test_repo_init_fail")
        / api.MetagitRepo.METAGIT_DIR_NAME
    )
    with pytest.raises(api.InvalidRepoError, match=str(path)):
        api.MetagitRepo.init(path_type(path))


def test_repo_init_nonexistent(tmp_path, path_type):
    """MetagitRepo.init creates a new repo, even for nonexistent paths."""
    api.MetagitRepo.init(path_type(tmp_path / "nonexistent" / "subdir"))


def test_repo_projects_corrupt(repo):
    """MetagitRepo.projects raises InvalidRepoError if the metagit_dir is corrupt."""
    rm_rf(repo.metagit_dir / ".git")
    with pytest.raises(api.InvalidRepoError, match=str(repo.metagit_dir)):
        any(repo.projects())


def test_repo_projects_deleted(nonempty_repo):
    """MetagitRepo.projects includes tracked projects that have been deleted."""
    projects = set(nonempty_repo.projects())
    rm_rf(non_metagit_dir_project(nonempty_repo).path)
    assert projects == set(nonempty_repo.projects())


def test_repo_projects_empty(empty_repo):
    """MetagitRepo.projects yields nothing for an empty repo."""
    assert not any(empty_repo.projects())


def test_repo_projects_no_commits(repo):
    """MetagitRepo.projects yields nothing if the .metagit project has no commits."""
    rm_rf(repo.metagit_dir)
    git.Repo.init(repo.metagit_dir)
    assert not any(repo.projects())


def test_repo_projects_relative(repo):
    """MetagitRepo.projects are all under the project root."""
    assert all(project.path.relative_to(repo.path()) for project in repo.projects())


def test_repo_remove_project_absolute(nonempty_repo, project_type):
    """MetagitRepo.remove_project untracks a valid project with an absolute path."""
    project = next(nonempty_repo.projects())
    nonempty_repo.remove_project(project_type(project.path))
    assert project not in nonempty_repo.projects()


def test_repo_remove_project_invalid_repo(tmp_path, project_type):
    """MetagitRepo.remove_project raises an exception if the repo is invalid."""
    repo = api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME)
    git_repo = git_repo_for_metagit_repo(repo)
    with pytest.raises(api.InvalidRepoError, match=str(repo.metagit_dir)):
        repo.remove_project(project_type(git_repo.git_dir))


def test_repo_remove_project_nonexistent(nonempty_repo, project_type):
    """MetagitRepo.remove_project stops tracking projects that don't exist anymore."""
    project = non_metagit_dir_project(nonempty_repo)
    rm_rf(project.path)
    nonempty_repo.remove_project(project_type(project.path))
    assert project not in nonempty_repo.projects()


def test_repo_remove_project_nongit(nonempty_repo, project_type):
    """MetagitRepo.remove_project stops tracking projects that aren't Git repos."""
    project = non_metagit_dir_project(nonempty_repo)
    rm_rf(project.path)
    project.path.mkdir()
    nonempty_repo.remove_project(project_type(project.path))
    assert project not in nonempty_repo.projects()


def test_repo_remove_project_not_in_repo(empty_repo, nonempty_repo, project_type):
    """MetagitRepo.remove_project raises an exception if the path isn't in the repo."""
    path = next(nonempty_repo.projects()).path
    with pytest.raises(api.NotInRepoError, match=str(path)):
        empty_repo.remove_project(project_type(path))


def test_repo_remove_project_relative(nonempty_repo, project_type):
    """MetagitRepo.remove_project untracks a valid project with a cwd-relative path."""
    project = next(nonempty_repo.projects())
    nonempty_repo.remove_project(project_type(os.path.relpath(project.path)))
    assert project not in nonempty_repo.projects()


def test_repo_remove_project_untracked(repo, project_type):
    """MetagitRepo.remove_project raises an exception if the path is not tracked."""
    dir_path = repo.path() / "untracked_dir"
    dir_path.mkdir()
    with pytest.raises(api.UntrackedProjectError, match=str(dir_path)):
        repo.remove_project(project_type(dir_path))


def test_repo_restore_project(nonempty_repo, project_type):
    """MetagitRepo.restore_project overwrites un-added changes."""
    project = next(nonempty_repo.projects())
    git_repo = git.Repo(project.path)
    remote_name = "test_repo_restore_project"
    git_repo.create_remote(remote_name, "a@b.c:d")
    assert remote_name in git_repo.remotes
    nonempty_repo.restore_project(project_type(project.path))
    assert remote_name not in git_repo.remotes


def test_repo_restore_project_deleted(nonempty_repo, project_type):
    """MetagitRepo.restore_project re-creates deleted projects."""
    project = non_metagit_dir_project(nonempty_repo)
    config = project.get_config()
    rm_rf(project.path)
    nonempty_repo.restore_project(project_type(project.path))
    assert config == project.get_config()


def test_repo_restore_project_invalid_repo(tmp_path, project_type):
    """MetagitRepo.restore_project raises an exception if the repo is invalid."""
    repo = api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME)
    git_repo = git_repo_for_metagit_repo(repo)
    with pytest.raises(api.InvalidRepoError, match=str(repo.metagit_dir)):
        repo.restore_project(project_type(git_repo.git_dir))


def test_repo_restore_project_not_in_repo(empty_repo, nonempty_repo, project_type):
    """MetagitRepo.restore_project raises an exception if the path isn't in the repo."""
    path = next(nonempty_repo.projects()).path
    with pytest.raises(api.NotInRepoError, match=str(path)):
        empty_repo.restore_project(project_type(path))


def test_repo_restore_untracked(empty_repo, project_type):
    """MetagitRepo.restore_project does NOT overwrite changes to untracked projects."""
    git_repo = git_repo_for_metagit_repo(empty_repo)
    with pytest.raises(api.UntrackedProjectError, match=git_repo.git_dir):
        empty_repo.restore_project(project_type(git_repo.git_dir))


def test_repo_status(nonempty_repo):
    """MetagitRepo.status returns empty results in a clean repo."""
    assert not any(nonempty_repo.status())


def test_repo_status_deleted(nonempty_repo):
    """MetagitRepo.status discovers deleted projects."""
    project = non_metagit_dir_project(nonempty_repo)
    rm_rf(project.path)
    deleted, modified, untracked = nonempty_repo.status()
    assert project in deleted
    assert len(deleted) == 1
    assert not modified
    assert not untracked


def test_repo_status_deleted_nongit(nonempty_repo):
    """MetagitRepo.status discovers projects that are no longer Git repos."""
    project = non_metagit_dir_project(nonempty_repo)
    rm_rf(project.path)
    project.path.mkdir()
    deleted, modified, untracked = nonempty_repo.status()
    assert project in deleted
    assert len(deleted) == 1
    assert not modified
    assert not untracked


def test_repo_status_deleted_nongit_config(nonempty_repo, tmp_path):
    """MetagitRepo.status discovers non-Git projects that have a .git/config."""
    project = non_metagit_dir_project(nonempty_repo)
    git_dir = Path(git.Repo(project.path).git_dir)
    tmp_config = tmp_path / "config"
    git_dir_config = git_dir / "config"
    os.link(git_dir_config, tmp_config)
    rm_rf(git_dir)
    git_dir.mkdir()
    tmp_config.rename(git_dir_config)
    deleted, modified, untracked = nonempty_repo.status()
    assert project in deleted
    assert len(deleted) == 1
    assert not modified
    assert not untracked


def test_repo_status_invalid_repo(tmp_path):
    """MetagitRepo.status raises an exception if the repo is invalid."""
    repo = api.MetagitRepo(tmp_path / api.MetagitRepo.METAGIT_DIR_NAME)
    with pytest.raises(api.InvalidRepoError, match=str(repo.metagit_dir)):
        repo.status()


def test_repo_status_modified(nonempty_repo):
    """MetagitRepo.status discovers projects that have been modified."""
    project = next(nonempty_repo.projects())
    git.Repo(project.path).create_remote("test_repo_status_modified", "a@b.c:d")
    deleted, modified, untracked = nonempty_repo.status()
    assert not deleted
    assert project in modified
    assert len(modified) == 1
    assert not untracked


def test_repo_status_modified_no_config(nonempty_repo):
    """MetagitRepo.status discovers projects that have no config file."""
    project = next(nonempty_repo.projects())
    (Path(git.Repo(project.path).git_dir) / "config").unlink()
    deleted, modified, untracked = nonempty_repo.status()
    assert not deleted
    assert project in modified
    assert len(modified) == 1
    assert not untracked


def test_repo_status_no_commits(empty_repo):
    """MetagitRepo.status discovers untracked paths if there are no .metagit commits."""
    rm_rf(empty_repo.metagit_dir)
    git.Repo.init(empty_repo.metagit_dir)
    deleted, modified, untracked = empty_repo.status()
    assert not deleted
    assert not modified
    assert empty_repo.metagit_dir in untracked
    assert len(untracked) == 1


def test_repo_status_untracked(empty_repo):
    """MetagitRepo.status discovers untracked paths in the repo."""
    deleted, modified, untracked = empty_repo.status()
    assert not deleted
    assert not modified
    assert empty_repo.metagit_dir in untracked
    assert len(untracked) == 1
