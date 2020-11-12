"""Test the projects module."""


import subprocess
import sys

import projects


def test_python_m():
    """Test python -m."""
    command = [sys.executable, "-m", projects.__name__, "--help"]
    assert subprocess.run(command, check=False).returncode == 0
