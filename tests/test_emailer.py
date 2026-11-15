from __future__ import annotations

from pathlib import Path

from weather_digest.emailer import SmtpSettings, build_message


def test_from_env_returns_none_when_incomplete():
    # No SMTP vars means emailing is skipped, not an error.
    assert SmtpSettings.from_env({}) is None
    assert SmtpSettings.from_env({"SMTP_HOST": "x"}) is None


def test_from_env_reads_full_settings():
    env = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "2525",
        "SMTP_USERNAME": "user@example.com",
        "SMTP_PASSWORD": "secret",
        "SMTP_TO": "a@example.com, b@example.com",
    }
    settings = SmtpSettings.from_env(env)
    assert settings is not None
    assert settings.host == "smtp.example.com"
    assert settings.port == 2525
    # Sender falls back to the username when SMTP_FROM is absent.
    assert settings.sender == "user@example.com"
    assert settings.recipients == ["a@example.com", "b@example.com"]


def test_build_message_attaches_files(tmp_path):
    attachment = tmp_path / "report.xlsx"
    attachment.write_bytes(b"fake-excel-bytes")

    settings = SmtpSettings(
        host="h",
        port=587,
        username="u@example.com",
        password="p",
        sender="u@example.com",
        recipients=["to@example.com"],
    )
    message = build_message(settings, "Subject", "<p>hi</p>", [Path(attachment)])

    assert message["Subject"] == "Subject"
    assert message["To"] == "to@example.com"
    filenames = [part.get_filename() for part in message.iter_attachments()]
    assert "report.xlsx" in filenames
