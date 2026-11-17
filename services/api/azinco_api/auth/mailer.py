"""Outgoing e-mail. Local development sends to Mailpit ([MOCK] inbox, nothing leaves the machine).

`capture` mode stores messages in memory for automated tests only ([MOCK]).
"""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from azinco_api.core.config import Settings


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    body: str


CAPTURED: list[OutgoingMail] = []  # [MOCK] test outbox (AZINCO_MAIL_MODE=capture)


def _send_smtp(settings: Settings, mail: OutgoingMail) -> None:
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg.set_content(mail.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(msg)


async def send_mail(settings: Settings, mail: OutgoingMail) -> None:
    if settings.mail_mode == "capture":
        CAPTURED.append(mail)
        return
    await asyncio.to_thread(_send_smtp, settings, mail)


def verification_mail(settings: Settings, to: str, token: str) -> OutgoingMail:
    link = f"{settings.public_web_url.rstrip('/')}/verify-email?token={token}"
    body = (
        "Welcome to AZINCO.\n\n"
        f"Confirm your e-mail address by opening this link (valid for 24 hours):\n{link}\n\n"
        "If you did not create an account, you can ignore this message.\n"
    )
    return OutgoingMail(to=to, subject="Confirm your AZINCO account", body=body)
