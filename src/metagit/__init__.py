"""Define MetagitRepo and MetagitProject."""


from contextlib import suppress
from pathlib import Path
from typing import Iterator, Set, Tuple, Type, TypeVar, Union

import attr
import git
from pkg_resources import get_distribution


__all__ = [
    "__version__",
    "InvalidPathError",
    "InvalidProjectError",
    "InvalidRepoError",
    "InvalidRepoPathError",
    "MetagitError",
    "MetagitProject",
    "MetagitRepo",
    "NotInRepoError",
    "UntrackedProjectError",
]
__version__ = get_distribution(__name__).version


class MetagitError(Exception):
    """All Metagit errors are based on this Exception."""


class InvalidPathError(MetagitError):
    """The path (args[0]) is not valid."""


class InvalidProjectError(InvalidPathError):
    """The path (args[0]) is not a project that Metagit can track."""

    def __str__(self) -> str:
        """Emulate `git -C /tmp status` (without parent search)."""
        return super().__str__() + " is not a metagit project"


class InvalidRepoError(InvalidPathError):
    """The path (args[0]) is not a metagit repository."""

    def __str__(self) -> str:
        """Emulate `git -C /tmp status` (without parent search)."""
        return super().__str__() + " is not a metagit repository"


class InvalidRepoPathError(InvalidRepoError):
    """Neither the path (args[0]) nor its parents are a metagit repository."""

    def __str__(self) -> str:
        """Emulate `git -C /tmp status`."""
        return super().__str__() + " (or any of the parent directories)"


class NotInRepoError(InvalidPathError):
    """The path (args[0]) is not in the metagit repository (args[1])."""

    def __str__(self) -> str:
        """Create an error message from self.args."""
        path, repo = self.args
        return f"'{path}' is not in the metagit repository at '{repo.path()}'"


class UntrackedProjectError(InvalidPathError):
    """The path (args[0]) is a trackable project, but it is not being tracked."""

    def __str__(self) -> str:
        """Create an error message from self.args."""
        return super().__str__() + " is not being tracked by metagit"


@attr.s(frozen=True)
class _GitRepo:

    _git_path_attr = "path"
    _git_repo_exc = InvalidPathError
    _git_checkout_exc = InvalidPathError

    def _git_checkout(self, relative_path: Union[str, Path]) -> None:
        """Restore a file from the HEAD commit."""
        head = self._git_repo().head
        try:
            commit = head.commit
        except ValueError as exc:
            raise self._git_checkout_exc(relative_path) from exc
        try:
            blob = commit.tree[str(relative_path)]
        except KeyError as exc:
            raise self._git_checkout_exc(relative_path) from exc
        path = getattr(self, self._git_path_attr) / relative_path
        blob.stream_data(path.open("wb"))

    # https://github.com/gitpython-developers/GitPython/issues/1349
    def _git_repo(self, *, init: bool = False) -> git.Repo:  # type: ignore
        """Get a git.Repo."""
        path = getattr(self, self._git_path_attr)
        try:
            if init:
                # https://github.com/gitpython-developers/GitPython/issues/1349
                return git.Repo.init(path)  # type: ignore
            else:
                # https://github.com/gitpython-developers/GitPython/issues/1349
                return git.Repo(path, search_parent_directories=False)  # type: ignore
        except git.GitError as exc:
            raise self._git_repo_exc(path) from exc


_MetagitProject = TypeVar("_MetagitProject", bound="MetagitProject")


@attr.s(frozen=True)
class MetagitProject(_GitRepo):
    """Manage a Metagit Project."""

    path: Path = attr.ib(converter=Path)
    _git_repo_exc = InvalidProjectError

    @classmethod
    def for_path(cls: Type[_MetagitProject], path: Union[str, Path]) -> _MetagitProject:
        """
        Get a MetagitProject for an existing project.

        InvalidProjectError is raised if path does not refer to a valid project.
        """
        return cls(Path(cls(path)._git_repo().git_dir).parent)

    def get_config(self) -> bytes:
        """
        Read project data that can be restored with set_config().

        InvalidProjectError is raised if self.path does not refer to a valid project.

        OSError is raised if config cannot be read (e.g. due to permissions).
        """
        git_repo = self._git_repo()
        try:
            return (Path(git_repo.git_dir) / "config").read_bytes()
        except FileNotFoundError:
            # git seems to be fine with a repo missing its .git/config file...
            # Call it equivalent to an empty one:
            return b""

    def set_config(self, config: bytes) -> None:
        """
        Restore project data returned from get_config().

        InvalidProjectError is raised if the project cannot be restored at self.path.

        OSError is raised if config cannot be written (e.g. due to permissions).
        """
        git_repo = self._git_repo(init=True)
        (Path(git_repo.git_dir) / "config").write_bytes(config)


_MetagitRepo = TypeVar("_MetagitRepo", bound="MetagitRepo")


@attr.s(frozen=True)
class MetagitRepo(_GitRepo):
    """Manage a Metagit repository."""

    METAGIT_DIR_NAME = ".metagit"
    metagit_dir: Path = attr.ib(converter=Path)
    _git_path_attr = "metagit_dir"
    _git_repo_exc = InvalidRepoError
    _git_checkout_exc = UntrackedProjectError

    def _repo_relative_path(self, path: Union[str, Path]) -> Path:
        """
        Get the path to a project relative to the Metagit repository.

        The path does not have to exist, nor does it have to refer to a tracked project.
        NotInRepoError is raised if path is not in self.path().
        """
        try:
            return Path(path).resolve().relative_to(self.path())
        except ValueError as exc:
            raise NotInRepoError(path, self) from exc

    def _sync_project(self, project: MetagitProject) -> None:
        """
        Ensure that the project path contents match the actual project config.

        The project does NOT need to be tracked (so as to allow syncing pre-add).

        NotInRepoError is raised if a passed project is not in the repo.
        InvalidProjectError is raised if a passed project is not valid.
        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        path = self.metagit_dir / self._repo_relative_path(project.path)
        try:
            config = project.get_config()
        except InvalidProjectError:
            # project is untracked, deleted, or no longer valid.
            with suppress(FileNotFoundError):
                path.unlink()
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(config)

    def add_project(self, project: Union[str, Path, MetagitProject]) -> MetagitProject:
        """
        Add a project to the Metagit repository.

        InvalidProjectError is raised if a passed project is not valid.
        NotInRepoError is raised if a passed project is valid but not in the repo.
        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        # The project must be valid:
        project = MetagitProject.for_path(
            project.path if isinstance(project, MetagitProject) else project,
        )
        # The project must be in the repo:
        relative_path = self._repo_relative_path(project.path)
        # Add the project:
        self._sync_project(project)
        repo = self._git_repo()
        repo.index.add([str(self.metagit_dir / relative_path)])
        repo.index.commit(f"Add {relative_path}")
        return project

    def diff_project(self, project: Union[str, Path, MetagitProject]) -> str:
        """
        Generate a diff between the Metagit repository and the project.

        Passed projects do NOT need to be valid (so as to allow diffing with deleted).

        NotInRepoError is raised if a passed project is not in the repo.
        UntrackedProjectError is raised if a passed project is not being tracked.
        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        project_path = (
            project.path if isinstance(project, MetagitProject) else Path(project)
        )
        project = MetagitProject(project_path.resolve())
        # The project must be in the repo:
        relative_path = self._repo_relative_path(project.path)
        # The project must be tracked:
        if project not in self.projects():
            raise UntrackedProjectError(project.path)
        # Get a diff for the project:
        self._sync_project(project)
        return str(self._git_repo().git.diff("--color", "--", relative_path))

    @classmethod
    def for_path(
        cls: Type[_MetagitRepo],
        path: Union[str, Path],
        *,
        search_parent_directories: bool = False,
    ) -> _MetagitRepo:
        """
        Get a MetagitRepo for an existing Metagit repository.

        InvalidRepoError is raised if path does not refer to a valid repo.
        InvalidRepoPathError is raised if none of path's parents are a valid repo.

        OSError is raised if path parents cannot be read.
        """
        repo_paths = [Path(path).resolve()]
        if search_parent_directories:
            repo_paths.extend(repo_paths[0].parents)
        for repo_path in repo_paths:
            metagit_dir = repo_path / cls.METAGIT_DIR_NAME
            if metagit_dir.is_dir():
                repo = cls(metagit_dir)
                repo._git_repo()
                return repo
        raise (InvalidRepoPathError if search_parent_directories else InvalidRepoError)(
            path,
        )

    @classmethod
    def init(cls: Type[_MetagitRepo], path: Union[str, Path]) -> _MetagitRepo:
        """
        Create/Initialize a Metagit repository.

        InvalidRepoError is raised if the repo cannot be created at self.metagit_dir.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        repo = cls(Path(path).resolve() / cls.METAGIT_DIR_NAME)
        repo.add_project(repo._git_repo(init=True).git_dir)
        return repo

    def path(self) -> Path:
        """Get the canonical path to the repo root."""
        return self.metagit_dir.parent

    def projects(self) -> Iterator[MetagitProject]:
        """
        Iterate through the projects tracked by the Metagit repository.

        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.
        """
        repo_path = self.path()
        head = self._git_repo().head
        try:
            commit = head.commit
        except ValueError:
            return  # no commits == no tracked projects
        for blob_or_tree in commit.tree.traverse():
            # https://github.com/gitpython-developers/GitPython/issues/1349
            if isinstance(blob_or_tree, git.Blob):  # type: ignore
                yield MetagitProject(repo_path / blob_or_tree.path)

    def remove_project(self, path: Union[str, Path, MetagitProject]) -> None:
        """
        Remove a project from the Metagit repository.

        NotInRepoError is raised if path is not in the repo.
        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.
        UntrackedProjectError is raised if a passed project is not being tracked.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        if isinstance(path, MetagitProject):
            path = path.path
        # The project must be in the repo:
        relative_path = self._repo_relative_path(path)
        # The project must be tracked:
        try:
            self._git_checkout(relative_path)
        except self._git_checkout_exc as exc:
            raise self._git_checkout_exc(path) from exc.__cause__
        # Stop tracking the project:
        repo = self._git_repo()
        repo.index.remove([str(relative_path)], working_tree=True)
        repo.index.commit(f"Remove {relative_path}")

    def restore_project(self, path: Union[str, Path, MetagitProject]) -> MetagitProject:
        """
        Restore a project from the Metagit repository.

        NotInRepoError is raised if the project is not in the repo.
        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.
        UntrackedProjectError is raised if a passed project is not being tracked.

        OSError is raised if project config cannot be read or written in .metagit.
        """
        if isinstance(path, MetagitProject):
            path = path.path
        # The project must be in the repo:
        relative_path = self._repo_relative_path(path)
        # The project must be tracked:
        try:
            self._git_checkout(relative_path)
        except self._git_checkout_exc as exc:
            raise self._git_checkout_exc(path) from exc.__cause__
        # Restore the project:
        project = MetagitProject(self.path() / relative_path)
        project.set_config((self.metagit_dir / relative_path).read_bytes())
        return project

    def status(self) -> Tuple[Set[MetagitProject], Set[MetagitProject], Set[Path]]:
        """
        Get deleted and modifed projects and untracked files, respectively.

        InvalidRepoError is raised if self.metagit_dir does not refer to a valid repo.

        OSError is raised if project config cannot be read in .metagit.
        """
        repo_path = self.path()
        git_repo = self._git_repo()

        deleted, modified = set(), set()
        for project in self.projects():
            self._sync_project(project)
            path = self.metagit_dir / project.path.relative_to(repo_path)
            if not path.exists():
                deleted.add(project)
            elif git_repo.is_dirty(path=path):
                modified.add(project)
        try:
            tree = git_repo.head.commit.tree
        except ValueError:
            tree = []
        untracked = {path for path in repo_path.iterdir() if path.name not in tree}
        return deleted, modified, untracked
