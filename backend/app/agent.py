"""ADK-discoverable ScopeLock agent entry point.

ADK's ``adk run app`` and ``adk web`` commands look for ``app.agent.root_agent``.
Keep this module thin; business validation and audit capture belong in the
application runner/services.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from backend.app.agents.requirement_analyzer import build_adk_agent


# When ADK is launched from ``backend``, the project-level .env is one level up.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

root_agent = build_adk_agent()

