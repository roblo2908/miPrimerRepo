"""
news_agent.py – Fetches top news from RSS feeds, summarizes them, and sends an HTML email.

Required environment variables:
  EMAIL_SENDER      – Gmail address used to send (e.g. myaccount@gmail.com)
  EMAIL_PASSWORD    – Gmail App Password (not your normal password)
  EMAIL_RECIPIENT   – Address that will receive the digest
  NEWS_LANGUAGE     – (optional) Language tag for feed selection, default "es"
  MAX_ARTICLES      – (optional) Max articles per source, default 5
"""

import os
import smtplib
import textwrap
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEWS_SOURCES = {
    "es": [
        {"name": "BBC Mundo",      "url": "https://feeds.bbci.co.uk/mundo/rss.xml"},
        {"name": "El País",        "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
        {"name": "CNN en Español", "url": "http://cnnespanol.cnn.com/feed/"},
    ],
    "en": [
        {"name": "BBC News",     "url": "http://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "Reuters",      "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "AP News",      "url": "https://rsshub.app/apnews/topics/apf-topnews"},
    ],
}

LANGUAGE = os.environ.get("NEWS_LANGUAGE", "es")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "5"))
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int = 300) -> str:
    """Return a clean excerpt of *text* capped at *max_chars* characters."""
    text = (text or "").strip()
    # Strip basic HTML tags that sometimes appear in RSS descriptions
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return textwrap.shorten(text, width=max_chars, placeholder=" …")


def fetch_articles(sources: list[dict], max_per_source: int) -> list[dict]:
    """Fetch and return articles from a list of RSS feed sources."""
    articles = []
    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            entries = feed.entries[:max_per_source]
            for entry in entries:
                summary = (
                    entry.get("summary")
                    or entry.get("description")
                    or entry.get("title", "")
                )
                articles.append(
                    {
                        "source": source["name"],
                        "title": entry.get("title", "(sin título)"),
                        "link": entry.get("link", "#"),
                        "summary": _truncate(summary),
                        "published": entry.get("published", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Could not fetch {source['name']}: {exc}")
    return articles


# ---------------------------------------------------------------------------
# Email rendering
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8" />
  <style>
    body  {{ font-family: Arial, sans-serif; background: #f4f4f4; color: #333; margin: 0; padding: 0; }}
    .wrap {{ max-width: 680px; margin: 24px auto; background: #fff; border-radius: 8px;
             overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
    .hdr  {{ background: #1a73e8; color: #fff; padding: 20px 28px; }}
    .hdr h1 {{ margin: 0; font-size: 22px; }}
    .hdr p  {{ margin: 4px 0 0; font-size: 13px; opacity: .85; }}
    .body {{ padding: 20px 28px; }}
    .src  {{ margin: 20px 0 8px; font-size: 13px; font-weight: bold; color: #1a73e8;
             text-transform: uppercase; letter-spacing: .5px; }}
    .card {{ border-left: 3px solid #1a73e8; padding: 10px 14px; margin-bottom: 14px;
             background: #f8f9fa; border-radius: 0 4px 4px 0; }}
    .card h2 {{ margin: 0 0 6px; font-size: 15px; }}
    .card h2 a {{ color: #1a1a1a; text-decoration: none; }}
    .card h2 a:hover {{ text-decoration: underline; }}
    .card p  {{ margin: 0; font-size: 13px; color: #555; line-height: 1.5; }}
    .card .meta {{ font-size: 11px; color: #999; margin-top: 6px; }}
    .ftr {{ text-align: center; font-size: 11px; color: #aaa; padding: 14px; }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>📰 Resumen de Noticias</h1>
    <p>{date}</p>
  </div>
  <div class="body">
    {content}
  </div>
  <div class="ftr">Generado automáticamente por tu agente de noticias · GitHub Actions</div>
</div>
</body>
</html>
"""


def _render_html(articles: list[dict]) -> str:
    """Build the full HTML body from a list of article dicts."""
    if not articles:
        return "<p>No se encontraron noticias hoy.</p>"

    blocks: list[str] = []
    current_source = None
    for art in articles:
        if art["source"] != current_source:
            current_source = art["source"]
            blocks.append(f'<div class="src">{current_source}</div>')
        blocks.append(
            f'<div class="card">'
            f'  <h2><a href="{art["link"]}" target="_blank">{art["title"]}</a></h2>'
            f'  <p>{art["summary"]}</p>'
            f'  <div class="meta">{art["published"]}</div>'
            f"</div>"
        )

    content = "\n".join(blocks)
    today = date.today().strftime("%A, %d de %B de %Y")
    return _HTML_TEMPLATE.format(lang=LANGUAGE, date=today, content=content)


def _render_plain(articles: list[dict]) -> str:
    """Build a plain-text fallback body."""
    if not articles:
        return "No se encontraron noticias hoy."
    lines = [f"Resumen de Noticias – {date.today()}\n{'=' * 40}"]
    current_source = None
    for art in articles:
        if art["source"] != current_source:
            current_source = art["source"]
            lines.append(f"\n[{current_source}]")
        lines.append(f"\n• {art['title']}")
        if art["summary"]:
            lines.append(f"  {art['summary']}")
        lines.append(f"  {art['link']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_email(html_body: str, plain_body: str) -> None:
    today = date.today().strftime("%d/%m/%Y")
    subject = f"📰 Resumen de Noticias – {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    print(f"✅ Email enviado a {EMAIL_RECIPIENT}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    sources = NEWS_SOURCES.get(LANGUAGE, NEWS_SOURCES["en"])
    print(f"📡 Obteniendo noticias en '{LANGUAGE}' de {len(sources)} fuentes …")
    articles = fetch_articles(sources, MAX_ARTICLES)
    print(f"📰 {len(articles)} artículos obtenidos.")

    html_body = _render_html(articles)
    plain_body = _render_plain(articles)
    send_email(html_body, plain_body)


if __name__ == "__main__":
    main()
