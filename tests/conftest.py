"""This is a local per-directory Pytest plugin."""


from pathlib import Path
import uuid

import git
import pytest
from pytest_lazyfixture import lazy_fixture

import metagit

from util import git_repo_for_metagit_repo


@pytest.fixture(params=[True, False])
def empty_repo(request, tmp_path_factory):
    """Get an empty MetagitRepo."""
    repo_path = tmp_path_factory.mktemp("empty_projects")
    if request.param:
        # .metagit was removed.
        repo = metagit.MetagitRepo.init(repo_path)
        repo.remove_project(repo.metagit_dir)
    else:
        # .metagit was never committed.
        repo = metagit.MetagitRepo(repo_path / metagit.MetagitRepo.METAGIT_DIR_NAME)
        git.Repo.init(repo.metagit_dir)
    return repo


@pytest.fixture
def nonempty_repo(tmp_path_factory):
    """Get a MetagitRepo that tracks at least one project (in addition to .metagit)."""
    repo = metagit.MetagitRepo.init(tmp_path_factory.mktemp("nonempty_projects"))
    repo.add_project(git_repo_for_metagit_repo(repo).git_dir)
    return repo


@pytest.fixture(params=[str, Path])
def path_type(request):
    """Get all valid types of path."""
    return request.param


@pytest.fixture
def project(tmp_path_factory):
    """Get a MetagitProject that isn't associated with a repo."""
    project_path = tmp_path_factory.mktemp(f"project-{uuid.uuid4()}")
    git.Repo.init(project_path)
    return metagit.MetagitProject(project_path)


@pytest.fixture(params=[str, Path, metagit.MetagitProject])
def project_type(request):
    """Get all valid types of project."""
    return request.param


@pytest.fixture(params=[lazy_fixture("empty_repo"), lazy_fixture("nonempty_repo")])
def repo(request):
    """Get a MetagitRepo."""
    return request.param


@pytest.fixture(params=[True, False])
def search_parent_directories(request):
    """Get all valid values for search_parent_directories."""
    return request.param
