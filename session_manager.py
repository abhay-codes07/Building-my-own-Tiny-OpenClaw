"""
session_manager.py — per-user conversation history.

Each unique (channel, client_id) pair gets its own session.  Sessions
are stored in SESSIONS.json so history survives restarts.  The session
ID format is "{channel}:{client_id}" (e.g. "telegram:123456789").
"""

import json
import os
import time

from logger import get_logger

log = get_logger(__name__)

# Maximum number of messages to keep per session (older ones are pruned)
MAX_HISTORY_LENGTH = 100


class SessionManager:
    """Manages per-user conversation sessions with JSON persistence."""

    def __init__(self, path: str = "SESSIONS.json"):
        self.path = path
        self._sessions: dict = {}

        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._sessions = json.load(f)
            log.info(
                "Restored %d session(s) from %s",
                len(self._sessions),
                path,
            )
        else:
            log.info("No session file found at %s — starting fresh", path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create_session(self, client_id: str, channel: str) -> str:
        """Return an existing session ID or create a brand-new session."""
        session_id = f"{channel}:{client_id}"

        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "client_id": client_id,
                "channel": channel,
                "created_at": time.time(),
                "history": [],
            }
            log.info("New session created: %s", session_id)
            self._save()

        return session_id

    def add_message(self, session_id: str, message: dict) -> None:
        """Append a message to the session history and persist."""
        session = self._sessions.get(session_id)
        if not session:
            log.warning("add_message called for unknown session: %s", session_id)
            return

        session["history"].append(message)

        # Prune oldest messages if history grows too large
        if len(session["history"]) > MAX_HISTORY_LENGTH:
            excess = len(session["history"]) - MAX_HISTORY_LENGTH
            session["history"] = session["history"][excess:]
            log.debug("Pruned %d old messages from session %s", excess, session_id)

        self._save()

    def get_history(self, session_id: str) -> list[dict]:
        """Return the full conversation history for a session."""
        session = self._sessions.get(session_id)
        return session["history"] if session else []

    def clear_history(self, session_id: str) -> bool:
        """Wipe conversation history for a session (keeps the session itself)."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session["history"] = []
        self._save()
        log.info("Cleared history for session %s", session_id)
        return True

    def session_info(self, session_id: str) -> dict | None:
        """Return session metadata without the full history."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "client_id": session["client_id"],
            "channel": session["channel"],
            "created_at": session["created_at"],
            "message_count": len(session["history"]),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._sessions, f, indent=2, default=str)
