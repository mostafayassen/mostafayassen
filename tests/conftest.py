"""Pytest configuration: make sure the repo root (which contains the `app`
package) is importable regardless of the working directory pytest is
invoked from."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
