import html
import os
import re
import smtplib
from email.message import EmailMessage
from typing import Dict, List
from .config import get_settings


BRAND_BLUE = "#004C86"
BRAND_RED = "#FF1F1F"
BRAND_DARK = "#24313D"
BRAND_MUTED = "#647282"
BRAND_LINE = "#D9E1EA"
BRAND_LIGHT = "#F5F8FB"


class EmailDelivery:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def _clean_plain_text(self, body: str) -> str:
        text = body or ""
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
        text = text.replace("`", "")
        text = re.sub(r"(^|\s)#\s+(?=[A-Za-z])", r"\1Number of ", text)
        text = re.sub(r"(^|\s)#(?=[A-Za-z])", r"\1Number of ", text)
        return text.strip()

    def _body_to_html(self, body: str) -> str:
        lines = self._clean_plain_text(body).splitlines()
        html_lines = []
        list_open = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if list_open:
                    html_lines.append("</ul>")
                    list_open = False
                continue

            bullet = re.match(r"^(?:[-\u2022]|\d+[\.)])\s+(.+)$", line)
            if bullet:
                if not list_open:
                    html_lines.append("<ul>")
                    list_open = True
                html_lines.append(f"<li>{html.escape(bullet.group(1))}</li>")
                continue

            if list_open:
                html_lines.append("</ul>")
                list_open = False

            if line.endswith(":") and len(line) <= 80:
                html_lines.append(f"<h3>{html.escape(line[:-1])}</h3>")
            else:
                html_lines.append(f"<p>{html.escape(line)}</p>")

        if list_open:
            html_lines.append("</ul>")
        return "\n".join(html_lines)

    def _wrap_brand_html(self, subject: str, content_html: str, attachment_path: str = "") -> str:
        logo_html = (
            '<img src="cid:brand-logo" alt="StanforteEdge" '
            'style="display:block;max-width:260px;height:auto;margin:0 0 18px 0;" />'
            if os.path.exists(self.settings.brand_logo_path)
            else f'<div style="font-size:24px;font-weight:800;color:{BRAND_BLUE};">Stanforte<span style="color:{BRAND_RED};">Edge</span></div>'
        )
        attachment_html = ""
        if attachment_path:
            filename = html.escape(os.path.basename(attachment_path))
            attachment_html = f"""
              <div style="margin-top:22px;padding:14px 16px;border:1px solid {BRAND_LINE};background:{BRAND_LIGHT};border-radius:8px;">
                <div style="font-size:12px;color:{BRAND_MUTED};text-transform:uppercase;letter-spacing:.06em;">Attachment</div>
                <div style="font-size:15px;color:{BRAND_DARK};font-weight:700;margin-top:4px;">{filename}</div>
              </div>
            """
        return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#EEF3F7;font-family:Arial,Helvetica,sans-serif;color:{BRAND_DARK};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EEF3F7;padding:28px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="680" cellpadding="0" cellspacing="0" style="width:680px;max-width:94%;background:#FFFFFF;border-radius:10px;overflow:hidden;border:1px solid {BRAND_LINE};">
            <tr>
              <td style="padding:28px 32px 20px 32px;border-top:6px solid {BRAND_BLUE};">
                {logo_html}
                <div style="font-size:12px;color:{BRAND_RED};font-weight:700;text-transform:uppercase;letter-spacing:.08em;">M&amp;E Intelligence</div>
                <h1 style="font-size:22px;line-height:1.28;margin:8px 0 0 0;color:{BRAND_DARK};">{html.escape(subject)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 32px 30px 32px;">
                <div style="font-size:15px;line-height:1.62;color:{BRAND_DARK};">
                  {content_html}
                </div>
                {attachment_html}
              </td>
            </tr>
            <tr>
              <td style="background:{BRAND_BLUE};padding:16px 32px;color:#FFFFFF;font-size:12px;line-height:1.5;">
                StanforteEdge branded automated programme intelligence notification.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    def _attach_inline_logo(self, message: EmailMessage) -> None:
        if not os.path.exists(self.settings.brand_logo_path):
            return
        try:
            html_part = message.get_payload()[1]
            with open(self.settings.brand_logo_path, "rb") as logo:
                html_part.add_related(
                    logo.read(),
                    maintype="image",
                    subtype="png",
                    cid="<brand-logo>",
                    filename="stanforteedge-logo.png",
                )
        except (IndexError, OSError):
            return

    def _build_message(
        self,
        subject: str,
        body: str,
        attachment_path: str,
        recipients: List[str],
        html_body: str = "",
    ) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.email_from
        message["To"] = ", ".join(recipients)
        plain_body = self._clean_plain_text(body)
        content_html = html_body or self._body_to_html(plain_body)
        message.set_content(plain_body)
        message.add_alternative(self._wrap_brand_html(subject, content_html, attachment_path), subtype="html")
        self._attach_inline_logo(message)

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                content = attachment.read()
            message.add_attachment(
                content,
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(attachment_path),
            )
        return message

    def _send_message(self, message: EmailMessage) -> None:
        if self.settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port)
        else:
            server = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
            server.starttls()
        server.login(self.settings.smtp_username, self.settings.smtp_password)
        server.send_message(message)
        server.quit()

    def send_email(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        attachment_path: str = "",
        html_body: str = "",
    ) -> Dict[str, str]:
        if not recipients:
            raise ValueError("No email recipients configured")
        message = self._build_message(subject, body, attachment_path, recipients, html_body)
        self._send_message(message)
        return {"status": "sent", "recipients": ",".join(recipients)}

    def send_report(self, subject: str, body: str, attachment_path: str, recipients: List[str]) -> Dict[str, str]:
        html_body = f"""
          <p style="margin:0 0 14px 0;">{html.escape(self._clean_plain_text(body))}</p>
          <div style="margin-top:16px;padding:14px 16px;border-left:4px solid {BRAND_RED};background:{BRAND_LIGHT};">
            <strong style="color:{BRAND_DARK};">Report delivery note</strong>
            <p style="margin:6px 0 0 0;color:{BRAND_MUTED};">The attached PDF contains the full donor-grade Monitoring &amp; Evaluation intelligence report, including visual dashboards and operational recommendations.</p>
          </div>
        """
        return self.send_email(subject, body, recipients, attachment_path, html_body)
