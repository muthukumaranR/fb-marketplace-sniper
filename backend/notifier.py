import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from backend.config import settings


def send_deal_email(
    item_name: str,
    listing_title: str,
    listing_price: float,
    fair_price: float,
    discount_pct: float,
    deal_quality: str,
    link: str,
    thumbnail: str | None = None,
):
    """Send email notification for a deal."""
    if not settings.smtp_user or not settings.smtp_pass:
        logger.warning("SMTP not configured, skipping email notification")
        return

    subject = f"{'🔥' if deal_quality == 'great' else '👍'} {deal_quality.upper()} DEAL: {item_name} - ${listing_price:.0f} ({discount_pct:.0f}% off)"

    thumbnail_html = ""
    if thumbnail:
        thumbnail_html = f'<img src="{thumbnail}" style="max-width:300px;border-radius:8px;margin:12px 0;" /><br>'

    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: {'#dc2626' if deal_quality == 'great' else '#f59e0b'};">
            {deal_quality.upper()} DEAL Found!
        </h2>
        <div style="background: #f9fafb; border-radius: 12px; padding: 16px; margin: 16px 0;">
            {thumbnail_html}
            <h3 style="margin: 0 0 8px 0;">{listing_title}</h3>
            <p style="font-size: 24px; font-weight: bold; color: #16a34a; margin: 4px 0;">
                ${listing_price:.2f}
            </p>
            <p style="color: #6b7280; margin: 4px 0;">
                Fair price: ${fair_price:.2f} &mdash; <strong>{discount_pct:.0f}% off</strong>
            </p>
            <p style="color: #6b7280; margin: 4px 0;">
                Watching: {item_name}
            </p>
        </div>
        <a href="{link}" style="display:inline-block; background:#1877f2; color:white; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:bold; margin-top:8px;">
            View on Facebook Marketplace
        </a>
        <p style="color: #9ca3af; font-size: 12px; margin-top: 24px;">
            FB Marketplace Sniper
        </p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notify_email
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
            server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        logger.info("Deal email sent for: {} @ ${:.2f}", listing_title, listing_price)
    except Exception as e:
        logger.error("Failed to send email: {}", e)
        raise
