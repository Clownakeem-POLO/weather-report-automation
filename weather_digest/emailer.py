"""Optional SMTP emailing of the report.

Credentials come from environment variables only. If they are not all set, I skip
emailing and return a reason, so the automation still produces local files.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipients: list[str]
    use_tls: bool = True

    @classmethod
    def from_env(cls, env: dict | None = None) -> "SmtpSettings | None":
        """Read SMTP settings from the environment.

        Returns None when a required variable is missing, which is the signal to
        skip emailing rather than crash.
        """

        env = env if env is not None else os.environ
        host = env.get("SMTP_HOST")
        username = env.get("SMTP_USERNAME")
        password = env.get("SMTP_PASSWORD")
        sender = env.get("SMTP_FROM") or username
        recipients_raw = env.get("SMTP_TO", "")
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

        if not host or not username or not password or not recipients:
            return None

        return cls(
            host=host,
            port=int(env.get("SMTP_PORT", "587")),
            username=username,
            password=password,
            sender=sender,
            recipients=recipients,
            use_tls=env.get("SMTP_USE_TLS", "true").lower() != "false",
        )


def build_message(
    settings: SmtpSettings,
    subject: str,
    html_body: str,
    attachments: list[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message["Subject"] = subject
    message.set_content(
        "This report is formatted as HTML. See the attached files for the digest."
    )
    message.add_alternative(html_body, subtype="html")

    for path in attachments:
        path = Path(path)
        data = path.read_bytes()
        message.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=path.name,
        )
    return message


def send_report(
    settings: SmtpSettings,
    subject: str,
    html_body: str,
    attachments: list[Path],
) -> None:
    """Send the email over SMTP with STARTTLS by default."""

    message = build_message(settings, subject, html_body, attachments)
    context = ssl.create_default_context()

    with smtplib.SMTP(settings.host, settings.port, timeout=30) as server:
        if settings.use_tls:
            server.starttls(context=context)
        server.login(settings.username, settings.password)
        server.send_message(message)
