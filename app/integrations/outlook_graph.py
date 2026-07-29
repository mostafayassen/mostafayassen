"""Outlook (Microsoft Graph) integration.

Uses MSAL's device-code flow against a user-registered, free "public
client" Azure AD app registration -- no client secret is needed (or
possible) for a public client, which is what makes this safe to ship in a
desktop app with no backend server and no cost.

Setup required before this works (see README.md "Outlook & Teams setup"
section for the full walkthrough):
  1. Register a free Azure AD app at https://portal.azure.com (Azure Active
     Directory -> App registrations -> New registration).
  2. Under Authentication, enable "Allow public client flows" = Yes.
  3. Under API permissions, add delegated Microsoft Graph permissions:
     Mail.Read (and offline_access, User.Read which MSAL requests
     automatically as needed).
  4. Copy the "Application (client) ID" into Settings in this app (or set
     AZURE_CLIENT_ID below / via environment variable).

This module is fully importable and its functions are correct and ready to
use, but it cannot be exercised end-to-end without a real Azure app
registration and user sign-in -- that step can only be done by the user.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

import msal

logger = logging.getLogger(__name__)

# Placeholder -- the user must fill this in via Settings (settings_view.py)
# or by setting the AZURE_CLIENT_ID environment variable. See README.
AZURE_CLIENT_ID = ""

# "common" allows both personal Microsoft accounts and work/school accounts.
AZURE_AUTHORITY = "https://login.microsoftonline.com/common"

# Delegated Graph scopes needed to read mail. offline_access lets MSAL's
# token cache silently refresh without prompting the user every time.
MAIL_SCOPES = ["Mail.Read", "offline_access", "User.Read"]

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


@dataclass
class EmailMessage:
    id: str
    subject: str
    sender: str
    received_at: str
    preview: str
    body: str = ""


class GraphAuthError(Exception):
    """Raised when authentication/config is missing or fails."""


def _build_app(client_id: str, token_cache: Optional[msal.SerializableTokenCache] = None) -> msal.PublicClientApplication:
    if not client_id:
        raise GraphAuthError(
            "No Azure AD client ID configured. Go to Settings and paste the "
            "Application (client) ID from your free Azure app registration. "
            "See README.md 'Outlook & Teams setup'."
        )
    return msal.PublicClientApplication(
        client_id=client_id,
        authority=AZURE_AUTHORITY,
        token_cache=token_cache,
    )


def acquire_token_device_flow(
    client_id: str,
    scopes: List[str],
    on_code: Callable[[str], None],
    token_cache: Optional[msal.SerializableTokenCache] = None,
) -> dict:
    """Run the device-code OAuth flow and return a token response dict.

    ``on_code`` is called once with the human-readable instructions/URL +
    code the user needs to enter at https://microsoft.com/devicelogin --
    the UI layer is expected to display this (e.g. in a dialog box).

    Raises GraphAuthError on failure. On success returns the dict MSAL
    gives back, which includes "access_token".
    """
    app = _build_app(client_id, token_cache)

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            return result

    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise GraphAuthError(
            f"Failed to start device-code sign-in: {flow.get('error_description', flow)}"
        )

    on_code(flow["message"])

    result = app.acquire_token_by_device_flow(flow)  # blocks until user completes sign-in
    if "access_token" not in result:
        raise GraphAuthError(
            f"Sign-in failed: {result.get('error_description', result)}"
        )
    return result


def _graph_get(access_token: str, path: str, params: Optional[dict] = None) -> dict:
    import urllib.parse
    import urllib.request
    import json

    url = f"{GRAPH_BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {access_token}"}, method="GET"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_recent_emails(access_token: str, top: int = 15) -> List[EmailMessage]:
    """Fetch the user's most recent inbox emails.

    Requires an access token obtained via acquire_token_device_flow with
    MAIL_SCOPES.
    """
    data = _graph_get(
        access_token,
        "/me/mailFolders/inbox/messages",
        params={
            "$top": str(top),
            "$select": "id,subject,from,receivedDateTime,bodyPreview,body",
            "$orderby": "receivedDateTime desc",
        },
    )
    messages = []
    for item in data.get("value", []):
        sender = ""
        from_field = item.get("from") or {}
        email_addr = (from_field.get("emailAddress") or {})
        sender = email_addr.get("name") or email_addr.get("address") or "Unknown"
        body_content = ""
        body = item.get("body") or {}
        if body.get("contentType") == "text":
            body_content = body.get("content", "")
        else:
            body_content = item.get("bodyPreview", "")
        messages.append(
            EmailMessage(
                id=item.get("id", ""),
                subject=item.get("subject") or "(no subject)",
                sender=sender,
                received_at=item.get("receivedDateTime", ""),
                preview=item.get("bodyPreview", ""),
                body=body_content,
            )
        )
    return messages


def email_to_task_fields(email: EmailMessage) -> dict:
    """Convert an EmailMessage into a dict of Task field defaults, ready to
    prefill app.ui.task_dialog.TaskDialog. This is the "manual trigger"
    email-to-task conversion; combine with ai_provider.summarize_email()
    for the AI-assisted version.
    """
    return {
        "title": email.subject,
        "description": f"From: {email.sender}\nReceived: {email.received_at}\n\n{email.preview}",
        "source": "email",
    }
