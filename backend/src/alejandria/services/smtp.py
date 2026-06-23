"""SMTP service for Send-to-Kindle."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib

from alejandria.config import get_settings
from alejandria.utils.log import get_logger

logger = get_logger(__name__)


class SMTPService:
    """SMTP client for sending books to Kindle."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_username
            and self.settings.smtp_from_email
        )

    async def send_book(
        self,
        to_email: str,
        book_path: Path,
        *,
        book_title: str,
        author: str = "Unknown",
    ) -> bool:
        """Send a book file as attachment to a Kindle email.

        Amazon Kindle accepts MOBI, AZW3, EPUB, PDF, DOC, DOCX, HTML, RTF, TXT.
        """
        if not self.is_configured:
            logger.error("smtp_not_configured")
            return False

        if not book_path.exists():
            logger.error("book_file_not_found", path=str(book_path))
            return False

        msg = EmailMessage()
        msg["From"] = self.settings.smtp_from_email
        msg["To"] = to_email
        msg["Subject"] = f"Alejandría: {book_title}"
        msg.set_content(
            f"Sent from your Alejandría library.\n\n"
            f"Title: {book_title}\n"
            f"Author: {author}\n\n"
            f"— Configure your Kindle email at Amazon > Settings > Approved Senders."
        )

        # Read file
        file_bytes = book_path.read_bytes()
        fmt = book_path.suffix.lstrip(".").upper() or "EPUB"
        maintype = "application"
        subtype = "octet-stream"
        if fmt == "PDF":
            maintype, subtype = "application", "pdf"
        elif fmt in ("EPUB", "AZW3", "MOBI", "DOCX"):
            maintype, subtype = "application", "zip" if fmt in ("EPUB", "DOCX") else "octet-stream"

        msg.add_attachment(
            file_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=book_path.name,
        )

        try:
            smtp = aiosmtplib.SMTP(
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                use_tls=self.settings.smtp_use_tls,
            )
            await smtp.connect()
            if self.settings.smtp_username and not self.settings.smtp_use_tls:
                await smtp.starttls()
            if self.settings.smtp_username:
                await smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            await smtp.send_message(msg)
            await smtp.quit()
            logger.info("kindle_send_success", to=to_email, book=book_title)
            return True
        except Exception as e:
            logger.error("kindle_send_failed", to=to_email, error=str(e))
            return False
