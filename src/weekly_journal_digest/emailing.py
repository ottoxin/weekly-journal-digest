from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


@dataclass(slots=True)
class GmailSettings:
    credentials_file: Path
    token_file: Path
    sender: str | None = None


class GmailSender:
    def __init__(self, settings: GmailSettings):
        self.settings = settings

    @classmethod
    def from_env(cls) -> "GmailSender":
        credentials_file = os.environ.get("WJD_GMAIL_CREDENTIALS_FILE")
        token_file = os.environ.get("WJD_GMAIL_TOKEN_FILE")
        sender = os.environ.get("WJD_GMAIL_SENDER")
        if not credentials_file:
            raise ValueError("WJD_GMAIL_CREDENTIALS_FILE is required.")
        if not token_file:
            raise ValueError("WJD_GMAIL_TOKEN_FILE is required.")
        return cls(
            GmailSettings(
                credentials_file=Path(credentials_file),
                token_file=Path(token_file),
                sender=sender,
            )
        )

    def send_markdown(self, to_address: str, subject: str, markdown_body: str) -> str | None:
        service = self._build_service()
        message = MIMEText(markdown_body, _charset="utf-8")
        message["to"] = to_address
        if self.settings.sender:
            message["from"] = self.settings.sender
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        response = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return response.get("id")

    def _build_service(self):
        creds = None
        if self.settings.token_file.exists():
            creds = Credentials.from_authorized_user_file(self.settings.token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.settings.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            self.settings.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings.token_file.write_text(creds.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)


def extract_subject(markdown_body: str) -> tuple[str | None, str]:
    lines = markdown_body.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip()
        return subject, body
    return None, markdown_body
