import os
import sys

# Ensure backend/ is on sys.path so that top-level imports like
# `from api...` resolve when running tests from repository root.
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
