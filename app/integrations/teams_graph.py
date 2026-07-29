"""Microsoft Teams (Microsoft Graph) integration.

Reuses the same MSAL public-client app registration and device-code flow as
outlook_graph.py (one Azure app registration covers both Outlook and Teams
scopes -- the user just needs to grant both sets of delegated permissions).

Important limitation (documented here and in the README): reading channel
messages (``ChannelMessage.Read.All``) is an *admin-consent-required*
permission in most work/school (tenant) environments. A personal Microsoft
account, or a work account whose admin hasn't granted consent, will not be
able to use channel reading -- only 1:1/group chat reading
(``Chat.Read``), which is user-consentable, is likely to work everywhere.

This module is written to degrade gracefully: every network/permission
failure is caught and turned into a clear ``TeamsAccessError`` message
rather than an unhandled exception, so the rest of the app keeps working
even if Teams access isn't available in the user's environment. This is
intentionally the roughest of the integrations per the project spec --
correctness of the core app matters more than Teams working everywhere.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from app.integrations.outlook_graph import GRAPH_BASE_URL, GraphAuthError, _graph_get

logger = logging.getLogger(__name__)

# Delegated Graph scopes for Teams. ChannelMessage.Read.All commonly needs
# tenant admin consent -- see module docstring.
TEAMS_SCOPES = ["Chat.Read", "ChannelMessage.Read.All", "offline_access", "User.Read"]


class TeamsAccessError(Exception):
    """Raised (and meant to be caught by UI code) when Teams data can't be
    read -- e.g. missing admin consent, no license, or a network problem.
    Carries a user-friendly message."""


@dataclass
class TeamsMessage:
    id: str
    chat_or_channel: str
    sender: str
    created_at: str
    preview: str


def _safe_graph_get(access_token: str, path: str, params: Optional[dict] = None) -> dict:
    try:
        return _graph_get(access_token, path, params)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TeamsAccessError(
                "Microsoft Graph denied access to Teams data (permission "
                "error). This usually means the delegated permission "
                "(e.g. ChannelMessage.Read.All) needs tenant admin consent "
                "that hasn't been granted, or your account/org disables "
                "this API. Chat.Read (1:1 and group chats) is more likely "
                "to work without admin consent than channel messages. "
                "See README.md 'Teams limitations'."
            ) from exc
        raise TeamsAccessError(f"Microsoft Graph request failed (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise TeamsAccessError(f"Could not reach Microsoft Graph: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TeamsAccessError("Unexpected response from Microsoft Graph.") from exc


def list_recent_chats(access_token: str, top: int = 10) -> List[dict]:
    """List the signed-in user's recent 1:1 / group chats (metadata only)."""
    data = _safe_graph_get(
        access_token,
        "/me/chats",
        params={"$top": str(top)},
    )
    return data.get("value", [])


def list_chat_messages(access_token: str, chat_id: str, top: int = 20) -> List[TeamsMessage]:
    """List recent messages in a given chat. Requires Chat.Read."""
    data = _safe_graph_get(
        access_token,
        f"/chats/{chat_id}/messages",
        params={"$top": str(top)},
    )
    return _parse_messages(data, label=chat_id)


def list_joined_teams(access_token: str) -> List[dict]:
    """List Teams the signed-in user has joined."""
    data = _safe_graph_get(access_token, "/me/joinedTeams")
    return data.get("value", [])


def list_channel_messages(
    access_token: str, team_id: str, channel_id: str, top: int = 20
) -> List[TeamsMessage]:
    """List recent messages in a channel.

    Requires ChannelMessage.Read.All, which frequently needs tenant admin
    consent -- see module docstring. Callers should catch TeamsAccessError
    and show it to the user rather than crash.
    """
    data = _safe_graph_get(
        access_token,
        f"/teams/{team_id}/channels/{channel_id}/messages",
        params={"$top": str(top)},
    )
    return _parse_messages(data, label=f"{team_id}/{channel_id}")


def _parse_messages(data: dict, label: str) -> List[TeamsMessage]:
    messages = []
    for item in data.get("value", []):
        from_field = item.get("from") or {}
        user = (from_field.get("user") or {})
        sender = user.get("displayName", "Unknown")
        body = item.get("body") or {}
        content = body.get("content", "")
        messages.append(
            TeamsMessage(
                id=item.get("id", ""),
                chat_or_channel=label,
                sender=sender,
                created_at=item.get("createdDateTime", ""),
                preview=(content[:280] + "...") if len(content) > 280 else content,
            )
        )
    return messages


def message_to_task_fields(message: TeamsMessage) -> dict:
    """Convert a TeamsMessage into Task field defaults for the task dialog."""
    return {
        "title": f"Follow up: message from {message.sender}",
        "description": f"From: {message.sender}\nWhen: {message.created_at}\n\n{message.preview}",
        "source": "teams",
    }
