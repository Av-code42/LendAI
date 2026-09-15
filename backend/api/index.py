"""
Vercel Python entrypoint. Vercel's @vercel/python builder detects an ASGI
app exported as `app` and serves it directly -- everything else lives in
the normal app/ package, this file only exists to satisfy Vercel's
file-based routing convention (api/*.py -> serverless function).
"""

import sys
from pathlib import Path

# So `import app...` resolves the same way it does when running locally
# from the backend/ directory (Vercel's build working directory is the
# project root, i.e. backend/, so this is normally a no-op -- kept for
# safety since Python's import path setup on Vercel's Python runtime has
# varied across versions).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
