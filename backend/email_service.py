"""Resend transactional email helper (used for password-reset emails)."""
import os
import asyncio
import logging
import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_email(to: str, subject: str, html: str) -> dict:
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY missing — email not sent")
        return {"skipped": True}
    params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
    try:
        res = await asyncio.to_thread(resend.Emails.send, params)
        return {"id": res.get("id") if isinstance(res, dict) else getattr(res, "id", None)}
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        raise


def reset_email_html(pseudo: str, reset_url: str) -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e14;padding:32px 0;font-family:Arial,Helvetica,sans-serif;">
      <tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0" style="background:#11161f;border:1px solid #1f2a37;border-radius:8px;overflow:hidden;">
          <tr><td style="padding:28px 32px;border-bottom:1px solid #1f2a37;">
            <span style="color:#6fe5c5;font-size:20px;font-weight:bold;letter-spacing:1px;">ReadyUp Arena</span>
          </td></tr>
          <tr><td style="padding:32px;">
            <h1 style="color:#ffffff;font-size:22px;margin:0 0 16px;">Réinitialisation du mot de passe</h1>
            <p style="color:#9fb0c0;font-size:15px;line-height:1.6;margin:0 0 24px;">
              Bonjour {pseudo}, vous avez demandé la réinitialisation de votre mot de passe.
              Ce lien expire dans 1 heure.
            </p>
            <a href="{reset_url}" style="display:inline-block;background:#6fe5c5;color:#06231c;text-decoration:none;
               font-weight:bold;padding:14px 28px;border-radius:6px;font-size:15px;">Réinitialiser mon mot de passe</a>
            <p style="color:#5d6b7a;font-size:13px;line-height:1.6;margin:24px 0 0;">
              Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email.
            </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
