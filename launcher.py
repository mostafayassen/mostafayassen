"""Windows launcher entrypoint used by PyInstaller to build TaskOrganizer.exe.

Kept as a standalone script outside the `app` package (rather than pointing
PyInstaller at app/main.py directly) so the package-relative imports inside
app/*.py keep resolving the same way they do when running `python -m app.main`.
"""

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
