"""This module contains utility functions for the tests."""


from pathlib import Path
import random
from typing import Union
import uuid

import git

import metagit


def git_repo_for_metagit_repo(repo: metagit.MetagitRepo) -> git.Repo:
    """Get a git.Repo that can be added to a Metagit repository."""
    project_path = repo.path()
    for _ in range(1, random.randint(2, 5)):
        project_path /= str(uuid.uuid4())
    return git.Repo.init(project_path)


def non_metagit_dir_project(repo: metagit.MetagitRepo):
    """Get a MetagitProject that can be deleted."""
    projects = repo.projects()
    project = next(projects)
    if project.path.name == metagit.MetagitRepo.METAGIT_DIR_NAME:
        project = next(projects)
    return project


def rm_rf(path: Union[str, Path]) -> None:
    """Recursively remove a path."""
    path = Path(path)
    try:
        path.unlink()
    except IsADirectoryError:
        for child in path.iterdir():
            rm_rf(child)
        path.rmdir()
