from __future__ import annotations

import base64
import os
import socket
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Callable, TypeVar

import httplib2
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException
from requests.exceptions import Timeout as RequestsTimeout
from urllib3.exceptions import HTTPError as Urllib3Error
from urllib3.exceptions import NameResolutionError


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
NETWORK_RETRY_ATTEMPTS = 4
NETWORK_RETRY_BASE_DELAY_SECONDS = 1.0
TRANSIENT_NETWORK_MARKERS = (
    "temporary failure in name resolution",
    "name or service not known",
    "name resolution",
    "nodename nor servname provided",
    "failed to establish a new connection",
    "max retries exceeded",
    "server not found",
    "connection aborted",
    "connection reset by peer",
    "timed out",
    "timeout",
    "temporarily unavailable",
)
T = TypeVar("T")


@dataclass(slots=True)
class GmailSettings:
    credentials_file: Path
    token_file: Path
    sender: str | None = None
    from_name: str = "COMAP Journal Bot"


@dataclass(slots=True)
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str


class GmailDeliveryError(RuntimeError):
    """Raised when Gmail delivery cannot proceed."""


class GmailTransientNetworkError(GmailDeliveryError):
    def __init__(self, operation: str, attempts: int, cause: Exception):
        detail = str(cause).strip() or cause.__class__.__name__
        super().__init__(
            f"Temporary network or DNS failure during {operation} after {attempts} attempts: {detail}"
        )
        self.operation = operation
        self.attempts = attempts
        self.cause = cause


class GmailSender:
    def __init__(self, settings: GmailSettings):
        self.settings = settings

    @classmethod
    def from_env(cls) -> "GmailSender":
        credentials_file = os.environ.get("WJD_GMAIL_CREDENTIALS_FILE")
        token_file = os.environ.get("WJD_GMAIL_TOKEN_FILE")
        sender = os.environ.get("WJD_GMAIL_SENDER")
        from_name = os.environ.get("WJD_GMAIL_FROM_NAME", "COMAP Journal Bot")
        if not credentials_file:
            raise ValueError("WJD_GMAIL_CREDENTIALS_FILE is required.")
        if not token_file:
            raise ValueError("WJD_GMAIL_TOKEN_FILE is required.")
        return cls(
            GmailSettings(
                credentials_file=Path(credentials_file),
                token_file=Path(token_file),
                sender=sender,
                from_name=from_name,
            )
        )

    def send_markdown(self, to_address: str, subject: str, markdown_body: str) -> str | None:
        message = self._base_message(to_address, subject)
        message.set_content(markdown_body)
        return self._send_message(message)

    def send_digest_package(
        self,
        to_address: str,
        subject: str,
        plain_text_body: str,
        html_body: str,
        attachments: list[EmailAttachment],
    ) -> str | None:
        message = self._base_message(to_address, subject)
        message.set_content(plain_text_body)
        message.add_alternative(html_body, subtype="html")
        for attachment in attachments:
            maintype, subtype = attachment.mime_type.split("/", 1)
            message.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )
        return self._send_message(message)

    def _base_message(self, to_address: str, subject: str) -> EmailMessage:
        message = EmailMessage()
        message["to"] = to_address
        if self.settings.sender:
            message["from"] = formataddr((self.settings.from_name, self.settings.sender))
        message["subject"] = subject
        return message

    def _send_message(self, message: EmailMessage) -> str | None:
        service = self._build_service()
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        response = self._call_with_retry(
            lambda: service.users().messages().send(userId="me", body={"raw": raw}).execute(),
            operation="Gmail API send",
        )
        return response.get("id")

    def _build_service(self):
        creds = self._load_credentials()
        return self._call_with_retry(
            lambda: build("gmail", "v1", credentials=creds, cache_discovery=False),
            operation="Gmail API setup",
        )

    def _load_credentials(self) -> Credentials:
        creds = None
        if self.settings.token_file.exists():
            creds = Credentials.from_authorized_user_file(self.settings.token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    self._call_with_retry(
                        lambda: creds.refresh(Request()),
                        operation="Google OAuth credential refresh",
                    )
                except RefreshError as exc:
                    if not is_invalid_grant_error(exc):
                        raise
                    creds = self._run_oauth_flow()
            else:
                creds = self._run_oauth_flow()
            self.settings.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings.token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _run_oauth_flow(self) -> Credentials:
        flow = InstalledAppFlow.from_client_secrets_file(self.settings.credentials_file, SCOPES)
        return flow.run_local_server(port=0)

    def _call_with_retry(self, func: Callable[[], T], operation: str) -> T:
        last_error: Exception | None = None
        for attempt in range(1, NETWORK_RETRY_ATTEMPTS + 1):
            try:
                return func()
            except Exception as exc:
                if not is_transient_network_error(exc):
                    raise
                last_error = exc
                if attempt == NETWORK_RETRY_ATTEMPTS:
                    raise GmailTransientNetworkError(operation, attempt, exc) from exc
                time.sleep(NETWORK_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        raise GmailTransientNetworkError(
            operation,
            NETWORK_RETRY_ATTEMPTS,
            last_error or RuntimeError("unknown network error"),
        )


def is_transient_network_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if isinstance(
            current,
            (
                socket.gaierror,
                TimeoutError,
                ConnectionError,
                RequestsConnectionError,
                RequestsTimeout,
                NameResolutionError,
            ),
        ):
            return True
        if isinstance(current, (TransportError, RequestException, Urllib3Error, httplib2.HttpLib2Error, OSError)):
            message = str(current).lower()
            if any(marker in message for marker in TRANSIENT_NETWORK_MARKERS):
                return True
    return False


def is_invalid_grant_error(exc: BaseException) -> bool:
    return any(
        isinstance(current, RefreshError) and "invalid_grant" in str(current).lower()
        for current in _iter_exception_chain(exc)
    )


def describe_delivery_error(exc: BaseException) -> str:
    if isinstance(exc, GmailDeliveryError):
        return str(exc)
    detail = str(exc).strip()
    return detail or exc.__class__.__name__


def _iter_exception_chain(exc: BaseException):
    pending = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)


def extract_subject(markdown_body: str) -> tuple[str | None, str]:
    lines = markdown_body.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip()
        return subject, body
    return None, markdown_body
