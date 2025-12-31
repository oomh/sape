"""
Test configuration for pytest.

This prepends the repository root to `sys.path` so tests can import the
`src` package when running under pytest.
"""

import sys
from pathlib import Path


def _prepend_project_root_to_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


_prepend_project_root_to_syspath()
