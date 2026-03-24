import os
import sys
from pathlib import Path

# Use the offscreen Qt platform so tests run headlessly without a display or EGL.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Untracked helper modules (logging_config, version) live in the main repo
# working directory, not in this worktree. Add that directory so they are
# importable from tests.
_main_repo = Path(__file__).parent.parent.parent
if str(_main_repo) not in sys.path:
    sys.path.insert(0, str(_main_repo))
