import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape

log = logging.getLogger(__name__)

COMPANY = "CodertechPRO"
TAGLINE = "Algo Trading & Robotics, Kochi"
PHONE = "+91 9037010647"
WHATSAPP_URL = "https://wa.me/919037010647"
PHONE_URL = "tel:+919037010647"
BRAND_COLOR = "#4a4de6"

SUBJECT = "Your question has been answered - CodertechPRO"

# Plain-text version, shown by mail apps that cannot display HTML.
TEXT_BODY = """Hello,

Thank you for your question. Our team has now answered it.

Your question:
{question}

Our answer:
{answer}

If you need anything else, call or WhatsApp us on {phone}.

Regards,
{company}
"""

# HTML version. Table layout and inline styles, because email apps ignore most modern CSS.
HTML_BODY = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__SUBJECT__</title>
</head>
<body style="margin:0;padding:0;background:#f4f5fb;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:#f4f5fb;">Good news! Our team has answered your question.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f5fb;padding:28px 12px;">
<tr><td align="center">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e4e6f2;border-radius:12px;overflow:hidden;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

    <tr><td style="background:__BRAND__;padding:26px 32px;">
      <div style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:.2px;">__COMPANY__</div>
      <div style="font-size:13px;color:#d9dbff;margin-top:4px;">__TAGLINE__</div>
    </td></tr>

    <tr><td style="padding:32px 32px 8px 32px;">
      <div style="font-size:20px;font-weight:700;color:#14143c;margin-bottom:10px;">Your question has been answered</div>
      <div style="font-size:15px;line-height:1.6;color:#4a4d73;">Hello,<br>Thank you for your question. Our team has now answered it. Here are the details:</div>
    </td></tr>

    <tr><td style="padding:20px 32px 0 32px;">
      <div style="font-size:12px;font-weight:700;color:#6b6f93;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px;">Your question</div>
      <div style="background:#f6f7fb;border-radius:8px;padding:14px 16px;font-size:15px;line-height:1.55;color:#14143c;">__QUESTION__</div>
    </td></tr>

    <tr><td style="padding:22px 32px 0 32px;">
      <div style="font-size:12px;font-weight:700;color:#6b6f93;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px;">Our answer</div>
      <div style="border-left:4px solid __BRAND__;background:#f1f1ff;border-radius:0 8px 8px 0;padding:16px 18px;font-size:16px;line-height:1.6;color:#14143c;">__ANSWER__</div>
    </td></tr>

    <tr><td style="padding:30px 32px 8px 32px;">
      <div style="font-size:15px;line-height:1.6;color:#4a4d73;">Still have a question? We are happy to help you personally.</div>
    </td></tr>
    <tr><td style="padding:12px 32px 32px 32px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="border-radius:8px;background:#25a244;"><a href="__WHATSAPP__" style="display:inline-block;padding:12px 22px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">Chat on WhatsApp</a></td>
        <td style="width:12px;"></td>
        <td style="border-radius:8px;border:1px solid __BRAND__;"><a href="__PHONE_URL__" style="display:inline-block;padding:11px 22px;font-size:15px;font-weight:600;color:__BRAND__;text-decoration:none;">Call __PHONE__</a></td>
      </tr></table>
    </td></tr>

    <tr><td style="padding:0 32px;"><div style="border-top:1px solid #e4e6f2;"></div></td></tr>
    <tr><td style="padding:20px 32px 28px 32px;">
      <div style="font-size:13px;line-height:1.6;color:#8b8fb5;">Regards,<br><b style="color:#4a4d73;">__COMPANY__ Team</b></div>
      <div style="font-size:12px;line-height:1.6;color:#a3a6c8;margin-top:14px;">You are receiving this email because you asked to be notified when our team answered your question. &copy; __YEAR__ __COMPANY__, Kochi, India.</div>
    </td></tr>

  </table>
</td></tr>
</table>
</body>
</html>
"""


def _html(text):
    """Escape user text for HTML and keep its line breaks."""
    return escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def build_message(sender, to, question, answer):
    """Build the email: plain-text part plus the HTML template."""
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(TEXT_BODY.format(question=question, answer=answer, phone=PHONE, company=COMPANY))
    page = HTML_BODY
    for key, value in {
        "__SUBJECT__": escape(SUBJECT), "__BRAND__": BRAND_COLOR, "__COMPANY__": COMPANY,
        "__TAGLINE__": escape(TAGLINE), "__WHATSAPP__": WHATSAPP_URL, "__PHONE_URL__": PHONE_URL,
        "__PHONE__": PHONE, "__YEAR__": str(datetime.now().year),
    }.items():
        page = page.replace(key, value)
    # Customer text goes in last, so it can never be mistaken for a placeholder.
    page = page.replace("__QUESTION__", _html(question)).replace("__ANSWER__", _html(answer))
    msg.add_alternative(page, subtype="html")
    return msg


class MailService:
    """Sends emails over SMTP. Disabled (enabled == False) until SMTP_HOST is set."""

    def __init__(self, cfg):
        self.host = cfg.SMTP_HOST
        self.port = cfg.SMTP_PORT
        self.username = cfg.SMTP_USERNAME
        self.password = cfg.SMTP_PASSWORD
        self.sender = cfg.SMTP_FROM or cfg.SMTP_USERNAME
        self.security = cfg.SMTP_SECURITY.lower()  # starttls | ssl | none

    @property
    def enabled(self):
        return bool(self.host and self.sender)

    def _connect(self):
        if self.security == "ssl":
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=20)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=20)
            if self.security == "starttls":
                server.starttls()
        if self.username:
            server.login(self.username, self.password)
        return server

    def send_answer(self, recipients, question, answer):
        """Email the answer to each recipient. Returns the list of addresses that succeeded."""
        sent = []
        try:
            server = self._connect()
        except Exception:
            log.exception("Could not connect to the SMTP server")
            return sent
        try:
            for to in recipients:
                try:
                    server.send_message(build_message(self.sender, to, question, answer))
                    sent.append(to)
                except Exception:
                    log.exception("Email to %s failed", to)
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return sent