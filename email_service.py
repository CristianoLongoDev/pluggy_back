import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger(__name__)


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not is_smtp_configured():
        logger.error("SMTP não configurado — verifique SMTP_HOST, SMTP_USER e SMTP_PASSWORD")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"E-mail enviado para {to_email}")
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail para {to_email}: {e}")
        return False


def send_password_reset_email(to_email: str, user_name: str, reset_token: str, frontend_url: str, ttl_minutes: int) -> bool:
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    subject = "Redefinição de senha — Plugger BI"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; background-color:#f4f5f7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7; padding:40px 20px;">
            <tr>
                <td align="center">
                    <table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <tr>
                            <td style="background-color:#1a1a2e; padding:28px 32px; text-align:center;">
                                <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:600;">Plugger BI</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:32px;">
                                <p style="margin:0 0 16px; color:#333; font-size:15px; line-height:1.5;">
                                    Olá{f' {user_name}' if user_name else ''},
                                </p>
                                <p style="margin:0 0 24px; color:#333; font-size:15px; line-height:1.5;">
                                    Recebemos uma solicitação para redefinir a senha da sua conta. Clique no botão abaixo para criar uma nova senha:
                                </p>
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding:8px 0 24px;">
                                            <a href="{reset_link}"
                                               style="display:inline-block; background-color:#4f46e5; color:#ffffff; text-decoration:none; padding:12px 32px; border-radius:6px; font-size:15px; font-weight:600;">
                                                Redefinir minha senha
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <p style="margin:0 0 16px; color:#666; font-size:13px; line-height:1.5;">
                                    Este link expira em <strong>{ttl_minutes} minutos</strong>. Se você não solicitou a redefinição, ignore este e-mail.
                                </p>
                                <hr style="border:none; border-top:1px solid #e5e7eb; margin:24px 0 16px;">
                                <p style="margin:0; color:#999; font-size:12px; line-height:1.5;">
                                    Se o botão não funcionar, copie e cole este link no navegador:<br>
                                    <a href="{reset_link}" style="color:#4f46e5; word-break:break-all;">{reset_link}</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return send_email(to_email, subject, html_body)
