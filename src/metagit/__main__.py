"""Create and manage a Metagit repository on the command line."""


import contextlib
import os
from typing import cast, Iterator, Tuple, Type, Union

import click

import metagit


@click.group(no_args_is_help=True)
@click.option("--debug/--no-debug", help="Enable debug output.", default=False)
@click.option(
    "path",
    "-C",
    type=click.Path(),
    help=" ".join(
        [
            "Run as if metagit was started in PATH",
            "instead of the current working directory.",
        ],
    ),
    default=os.getcwd,
)
@click.version_option(version=metagit.__version__)
@click.pass_context
def main(ctx: click.Context, debug: bool, path: str) -> None:
    """Manage a Metagit repository."""

    @contextlib.contextmanager
    def debug_manager(*exc_types: Type[Exception]) -> Iterator[None]:
        """Raise expected exceptions if --debug is passed, otherwise print and fail."""
        try:
            yield
        except exc_types as exc:
            if ctx.obj["debug"]:
                raise
            ctx.fail(str(exc))

    ctx.obj = {
        "debug": debug,
        "manager": debug_manager(metagit.MetagitError),
        "path": path,
    }


@main.command()
@click.argument("path", nargs=-1, type=click.Path())
@click.pass_context
def diff(ctx: click.Context, path: Tuple[str]) -> None:
    """Show changes to projects tracked in the Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.for_path(
            ctx.obj["path"],
            search_parent_directories=True,
        )
        for p in path or repo.projects():
            diff = repo.diff_project(p)
            if diff:
                click.echo(diff)


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.init(ctx.obj["path"])
    click.echo(f"Initialized Metagit repository in {repo.path()}")


@main.command()
@click.argument("path", nargs=-1, type=click.Path())
@click.pass_context
def add(ctx: click.Context, path: Tuple[str]) -> None:
    """Add projects to the Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.for_path(
            ctx.obj["path"],
            search_parent_directories=True,
        )
        for p in path:
            repo.add_project(p)


@main.command()
@click.argument("path", nargs=-1, type=click.Path())
@click.pass_context
def rm(ctx: click.Context, path: Tuple[str]) -> None:
    """Remove projects from the Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.for_path(
            ctx.obj["path"],
            search_parent_directories=True,
        )
        for p in path:
            repo.remove_project(p)


@main.command()
@click.option(
    "--all/--not-all",
    "all_",
    help="Restore all tracked projects.",
    default=False,
)
@click.argument("path", nargs=-1, type=click.Path())
@click.pass_context
def restore(ctx: click.Context, all_: bool, path: Tuple[str]) -> None:
    """Restore projects from the Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.for_path(
            ctx.obj["path"],
            search_parent_directories=True,
        )
        for p in repo.projects() if all_ else path:
            repo.restore_project(cast(Union[str, metagit.MetagitProject], p))


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Get information about a Metagit repository."""
    with ctx.obj["manager"]:
        repo = metagit.MetagitRepo.for_path(
            ctx.obj["path"],
            search_parent_directories=True,
        )
        projects = repo.projects()
        deleted, modified, untracked = repo.status()
    if deleted or modified:
        click.echo("Changes")
        click.echo('  (use "metagit add/rm <project>..." to accept changes)')
        click.echo('  (use "metagit restore <project>..." to undo changes)')
        for project in sorted(deleted.union(modified)):
            prefix = "deleted:  " if project in deleted else "modified: "
            relpath = os.path.relpath(project.path, start=ctx.obj["path"])
            click.secho(f"\t{prefix}{relpath}", fg="red")
        click.echo()
    elif not any(projects):
        click.echo("No projects are being tracked yet")
        click.echo()
    if untracked:
        click.echo("Untracked projects")
        click.echo('  (use "metagit add <project>..." to begin tracking)')
        for path in sorted(untracked):
            suffix = "/" if path.is_dir() else ""
            relpath = os.path.relpath(path, start=ctx.obj["path"])
            click.secho(f"\t{relpath}{suffix}", fg="red")
        click.echo()


if __name__ == "__main__":
    main()
