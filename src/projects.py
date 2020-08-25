#!/usr/bin/env python3

"""Manage Git projects."""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from typing import Dict, Iterator, List, NoReturn, Optional, Tuple, Union


LOG = logging.getLogger(__name__)


def logging_cli_parser() -> argparse.ArgumentParser:
    """Define logging CLI arguments and options."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-q",
        "--quiet",
        default=False,
        action="store_true",
        help="Supress console output.",
    )
    parser.add_argument(
        "--log-file", type=str, help="Specify a path to log to.",
    )
    parser.add_argument(
        "--log-level",
        help="Specify how verbose logging should be.",
        default="info",
        choices=("debug", "info", "warning", "error", "critical"),
    )
    return parser


def cli_parser() -> argparse.ArgumentParser:
    """Define CLI arguments and options."""
    parser = logging_cli_parser()
    parser.add_argument(
        "--clone", help="clone missing projects", default=False, action="store_true",
    )
    parser.add_argument(
        "--fetch",
        help="update --all remotes (includes --tags and --prune)",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--set-urls",
        help="overwrite remote URLs that do not match the spec",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--git-encoding", help="the encoding git will use", default="utf-8",
    )
    parser.add_argument(
        "--spec", help="the path to a project specification",
    )
    parser.add_argument(
        "--spec-create", help="write the project specification based on what exists",
    )
    parser.add_argument(
        "--spec-create-overwrite",
        help=" ".join(
            [
                "overwrite the project specification if it already exists",
                "(ignored without --spec-create)",
            ],
        ),
        default=False,
        action="store_true",
    )
    projects_path = os.environ.get("PROJECTS")
    parser.add_argument(
        "--projects",
        help="the path to the projects directory",
        default=projects_path,
        required=not projects_path,
    )
    parser.add_argument(
        "--sync",
        help="an alias for --clone, --fetch, and --set-urls",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "pattern",
        help="ignore projects that do not match this optional regex",
        default=".*",
        nargs="?",
    )
    return parser


def configure_logging(args: argparse.Namespace) -> None:
    """Configure logging for command-line tools."""
    logging.getLogger().setLevel(logging.getLevelName(args.log_level.upper()))
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    if not args.quiet:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
    if args.log_file:
        logfile_handler = logging.FileHandler(args.log_file)
        logfile_handler.setFormatter(formatter)
        logging.getLogger().addHandler(logfile_handler)


_REMOTE_MODE_URL_TYPE = Dict[str, Dict[str, str]]
_REMOTE_MODE_URL_RETURN_TYPE = Union[
    _REMOTE_MODE_URL_TYPE, subprocess.CalledProcessError,
]


def _remote_mode_url(path: str, encoding: str) -> _REMOTE_MODE_URL_RETURN_TYPE:
    try:
        stdout = subprocess.check_output(
            ["git", "-C", path, "remote", "-v"],
            stderr=subprocess.PIPE,
            encoding=encoding,
        )
    except subprocess.CalledProcessError as exc:
        return exc
    remote_mode_url: _REMOTE_MODE_URL_TYPE = {}
    for line in stdout.split("\n"):
        if not line:
            continue
        remote, _, url_mode = line.rpartition("\t")
        mode_url = remote_mode_url.get(remote, {})
        url, _, mode = url_mode.rpartition(" ")
        mode_url[mode.strip("()")] = url
        remote_mode_url[remote] = mode_url
    return remote_mode_url


def _fetchable_remote_urls(
    remote_mode_url: _REMOTE_MODE_URL_TYPE,
) -> Iterator[Tuple[str, str]]:
    for remote, mode_url in remote_mode_url.items():
        fetch_url = mode_url.get("fetch")
        if fetch_url:
            yield remote, fetch_url


def main(argv: Optional[List[str]] = None) -> NoReturn:
    """Parse and execute commands."""
    if argv is None:
        argv = sys.argv[1:]
    parser = cli_parser()
    args = parser.parse_args(argv)
    configure_logging(args)

    if args.sync:
        args.clone = True
        args.fetch = True
        args.set_urls = True

    # Check for existing projects (observed),
    # and parse the specification (expected), if there is one:
    try:
        observed = {
            project: _remote_mode_url(
                os.path.join(args.projects, project), encoding=args.git_encoding,
            )
            for project in os.listdir(args.projects)
        }
    except OSError as exc:
        parser.error(f"--projects: can't list '{args.projects}': {exc}")
    if args.spec is None:
        expected = observed
    else:
        LOG.debug("loading spec from '%s'...", args.spec)
        try:
            with open(args.spec) as json_f:
                expected = json.load(json_f)
        except OSError as exc:
            parser.error(f"--spec: can't open '{args.spec}': {exc}")
        except json.JSONDecodeError as exc:
            parser.error(f"--spec: can't decode JSON from '{args.spec}': {exc}")

    # Check every project (specified or not):
    for project in sorted(set(expected).union(observed)):
        prefix = f"[{project}]"

        try:
            if not re.search(args.pattern, project):
                LOG.debug("%s ignoring...", prefix)
                continue
        except re.error as exc:
            parser.error(f"pattern: invalid regex '{args.pattern}': {exc}")

        path = os.path.join(args.projects, project)
        LOG.debug("%s %s", prefix, path)
        git = ["git", "-C", path]

        expected_remote_mode_url = expected.get(project)
        observed_remote_mode_url = observed.get(project)

        # not expected, not observed -> n/a
        # not expected,     observed -> warn,                branches, stash, untracked
        #     expected, not observed -> clone, sync remotes, branches, stash, untracked
        #     expected,     observed ->        sync remotes, branches, stash, untracked

        if isinstance(observed_remote_mode_url, subprocess.CalledProcessError):
            LOG.error("%s %s", prefix, observed_remote_mode_url.stderr.strip())
            continue
        assert not isinstance(expected_remote_mode_url, subprocess.CalledProcessError)

        if project not in expected:
            LOG.warning("%s unexpected project", prefix)

        elif expected_remote_mode_url != observed_remote_mode_url:
            LOG.debug("%s project sync needed", prefix)
            assert expected_remote_mode_url is not None

            # Clone, if needed:
            if project not in observed:
                if not args.clone:
                    LOG.warning("%s skipping (rerun with --clone)...", prefix)
                    continue
                LOG.info("%s cloning...", prefix)

                # Try cloning from any fetch-mode remote URL:
                for remote, url in _fetchable_remote_urls(expected_remote_mode_url):
                    remote_prefix = prefix + f" [{remote}]"
                    result = subprocess.run(
                        ["git", "clone", "--origin", remote, url, path],
                        encoding=args.git_encoding,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if result.returncode:
                        LOG.warning(
                            "%s clone from '%s' failed:\n%s",
                            remote_prefix,
                            url,
                            result.stderr,
                        )
                        continue
                    LOG.info(
                        "%s clone from '%s' complete:\n%s",
                        remote_prefix,
                        url,
                        result.stderr,
                    )
                    observed_remote_mode_url = observed[project] = {
                        remote: {"fetch": url, "push": url},
                    }
                    break
                else:
                    LOG.error("%s unable to clone from expected remotes", prefix)
                    continue

            LOG.debug("%s clone exists", prefix)
            assert observed_remote_mode_url is not None

            # Sync remotes:
            for remote in sorted(
                set(expected_remote_mode_url).union(observed_remote_mode_url),
            ):
                remote_prefix = prefix + f" [{remote}]"

                expected_mode_url = expected_remote_mode_url.get(remote)
                observed_mode_url = observed_remote_mode_url.get(remote)

                # not expected, not observed -> n/a
                # not expected,     observed -> warn
                #     expected, not observed -> add remote
                #     expected,     observed -> mismatch

                if not expected_mode_url:
                    LOG.warning("%s unexpected remote", remote_prefix)

                elif expected_mode_url != observed_mode_url:
                    LOG.debug("%s remote sync needed", remote_prefix)

                    if remote not in observed_remote_mode_url:
                        if not args.set_urls:
                            LOG.warning(
                                "%s skipping (rerun with --set-urls)...", remote_prefix,
                            )
                            continue
                        LOG.info("%s adding...", remote_prefix)
                        for url in expected_mode_url.values():
                            subprocess.run(
                                git + ["remote", "add", remote, url], check=True,
                            )
                            observed_mode_url = observed_remote_mode_url[remote] = {
                                "fetch": url,
                                "push": url,
                            }
                            break
                        else:
                            LOG.error(
                                "%s unable to add remote from expected modes",
                                remote_prefix,
                            )
                            continue

                    LOG.debug("%s remote exists", remote_prefix)
                    assert observed_mode_url is not None

                    # Set mimatched URLs, if needed:
                    for mode in sorted(set(expected_mode_url).union(observed_mode_url)):
                        mode_remote_prefix = remote_prefix + f" [{mode}]"

                        expected_url = expected_mode_url.get(mode)
                        observed_url = observed_mode_url.get(mode)

                        # not expected, not observed -> n/a
                        # not expected,     observed -> warn
                        #     expected, not observed -> set-url
                        #     expected,     observed -> mismatch

                        if not expected_url:
                            LOG.warning("%s unexpected mode", mode_remote_prefix)

                        elif expected_url != observed_url:
                            LOG.debug("%s mode sync needed", mode_remote_prefix)
                            if not args.set_urls:
                                LOG.warning(
                                    "%s skipping (rerun with --set-urls)...",
                                    mode_remote_prefix,
                                )
                                continue
                            LOG.info(
                                "%s changing '%s' to '%s'...",
                                mode_remote_prefix,
                                observed_url,
                                expected_url,
                            )
                            git_remote_set_url = git + ["remote", "set-url"]
                            if mode == "push":
                                git_remote_set_url.append("--push")
                            subprocess.run(
                                git_remote_set_url + [remote, expected_url], check=True,
                            )
                            observed_url = observed_mode_url[mode] = expected_url

        if args.fetch:
            LOG.info("%s fetching all remotes...", prefix)
            result = subprocess.run(
                git + ["fetch", "--all", "--tags", "--prune"],
                encoding=args.git_encoding,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.stdout:
                LOG.info("%s fetched updates:\n%s", prefix, result.stdout)
            if result.returncode:
                LOG.warning("%s fetch failed:\n%s", prefix, result.stderr)

        LOG.debug("%s checking for branches...", prefix)
        result = subprocess.run(
            git + ["show-ref", "--heads"],
            stdout=subprocess.PIPE,
            encoding=args.git_encoding,
        )
        if result.returncode == 0:
            LOG.info("%s local branches:\n%s", prefix, result.stdout)

        LOG.debug("%s checking for stashed changes...", prefix)
        stdout = subprocess.check_output(
            git + ["stash", "list"], encoding=args.git_encoding,
        )
        if stdout:
            LOG.info("%s stashed changes:\n%s", prefix, stdout)

        LOG.debug("%s checking for untracked files...", prefix)
        stdout = subprocess.check_output(
            git
            + [
                "ls-files",
                "--directory",
                "--exclude-standard",
                "--no-empty-directory",
                "--other",
            ],
            encoding=args.git_encoding,
        )
        if stdout:
            LOG.info("%s untracked files:\n%s", prefix, stdout)

    if args.spec_create is not None:
        LOG.info("writing spec to '%s'...", args.spec_create)
        try:
            with open(
                args.spec_create, mode="w" if args.spec_create_overwrite else "x",
            ) as spec_f:
                json.dump(
                    {
                        project: remote_mode_url
                        for project, remote_mode_url in expected.items()
                        if not isinstance(
                            remote_mode_url, subprocess.CalledProcessError,
                        )
                    },
                    spec_f,
                    sort_keys=True,
                    indent=4,
                )
        except OSError as exc:
            LOG.error(exc)
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
