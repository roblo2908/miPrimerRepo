"""
news_agent.py – Fetches top news from RSS feeds, prioritizes selected topics, and sends an HTML email.

Required environment variables:
  EMAIL_SENDER         – Gmail address used to send (e.g. myaccount@gmail.com)
  EMAIL_PASSWORD       – Gmail App Password (not your normal password)
  EMAIL_RECIPIENT      – Address that will receive the digest
  NEWS_LANGUAGE        – (optional) Language tag for feed selection, default "es"
  MAX_ARTICLES         – (optional) Max articles to inspect per source, default 20
  MAX_TECHNOLOGY       – (optional) Max technology articles per region, default 10
  MAX_SCIENCE          – (optional) Max science articles per region, default 6
  MAX_POLITICS         – (optional) Max politics articles per region, default 4
"""

import os
import re
import smtplib
import textwrap
from collections import defaultdict
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOPIC_PRIORITY = {
    "tecnologia": 0,
    "ciencia": 1,
    "politica": 2,
}

TOPIC_LABELS = {
    "tecnologia": "Tecnología",
    "ciencia": "Ciencia",
    "politica": "Política",
}

TOPIC_KEYWORDS = {
    "tecnologia": [
        "tecnología", "tecnologia", "tech", "startup", "startups", "ia", "ai",
        "inteligencia artificial", "software", "hardware", "app", "apps", "internet",
        "ciberseguridad", "robot", "robots", "gadgets", "digital", "datos", "chip",
        "chips", "semiconductor", "semiconductores", "nube", "cloud", "openai",
        "google", "microsoft", "apple", "meta", "xiaomi", "samsung",
    ],
    "ciencia": [
        "ciencia", "científico", "cientifica", "científicos", "cientificos", "investigación",
        "investigacion", "estudio", "laboratorio", "espacio", "nasa", "salud", "medicina",
        "biología", "biologia", "física", "fisica", "química", "quimica", "genética", "genetica",
        "astronomía", "astronomia", "vacuna", "vacunas", "planeta", "universo", "descubrimiento",
    ],
    "politica": [
        "política", "politica", "gobierno", "presidente", "presidencia", "asamblea",
        "diputado", "diputada", "diputados", "diputadas", "congreso", "elecciones",
        "canciller", "ministro", "ministra", "decreto", "ley", "reforma", "partido",
        "alcalde", "alcaldesa", "municipalidad", "poder ejecutivo", "poder legislativo",
        "tribunal supremo de elecciones", "tse",
    ],
}

NEWS_SOURCES = {
    "es": {
        "costa_rica": [
            {"name": "Delfino.cr", "url": "https://delfino.cr/feed"},
            {"name": "Despertar.cr", "url": "https://despertar.opennemas.com/rss/all.xml"},
            {"name": "Diario Extra", "url": "https://www.diarioextra.com/RSS"},
        ],
        "mundo": [
            {"name": "BBC Mundo", "url": "https://feeds.bbci.co.uk/mundo/rss.xml"},
            {"name": "El País", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
            {"name": "CNN en Español", "url": "http://cnnespanol.cnn.com/feed/"},
        ],
    },
    "en": {
        "costa_rica": [],
        "mundo": [
            {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/rss.xml"},
            {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews"},
            {"name": "AP News", "url": "https://rsshub.app/apnews/topics/apf-topnews"},
        ],
    },
}

LANGUAGE = os.environ.get("NEWS_LANGUAGE", "es")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "20"))
MAX_PER_TOPIC = {
    "tecnologia": int(os.environ.get("MAX_TECHNOLOGY", "10")),
    "ciencia": int(os.environ.get("MAX_SCIENCE", "6")),
    "politica": int(os.environ.get("MAX_POLITICS", "4")),
}
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
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return textwrap.shorten(text, width=max_chars, placeholder=" …")


def _normalize(text: str) -> str:
    text = (text or "").lower()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _extract_categories(entry: dict) -> list[str]:
    categories = []
    for tag in entry.get("tags", []):
        term = tag.get("term") or tag.get("label") or ""
        if term:
            categories.append(term)
    if entry.get("category"):
        categories.append(entry.get("category", ""))
    return categories


def _count_keyword_matches(text: str, keyword: str) -> int:
    normalized_text = f" {_normalize(text)} "
    normalized_keyword = _normalize(keyword).strip()
    if not normalized_keyword:
        return 0
    if " " in normalized_keyword:
        return normalized_text.count(normalized_keyword)
    pattern = rf"\b{re.escape(normalized_keyword)}\b"
    return len(re.findall(pattern, normalized_text))


def _topic_score(title: str, summary: str, categories: list[str]) -> tuple[int, str] | None:
    title_text = _normalize(title)
    summary_text = _normalize(summary)
    categories_text = _normalize(" ".join(categories))

    scores = defaultdict(int)
    for topic in TOPIC_PRIORITY:
        for keyword in TOPIC_KEYWORDS[topic]:
            scores[topic] += _count_keyword_matches(title_text, keyword) * 5
            scores[topic] += _count_keyword_matches(summary_text, keyword) * 2
            scores[topic] += _count_keyword_matches(categories_text, keyword) * 6

    best_topic = None
    best_score = 0
    for topic in TOPIC_PRIORITY:
        score = scores[topic]
        if score > best_score:
            best_topic = topic
            best_score = score
        elif score == best_score and score > 0 and best_topic is not None:
            if TOPIC_PRIORITY[topic] < TOPIC_PRIORITY[best_topic]:
                best_topic = topic

    if not best_topic or best_score == 0:
        return None
    return best_score, best_topic


def _apply_topic_limits(articles: list[dict]) -> list[dict]:
    prioritized_topics = ["tecnologia", "ciencia", "politica"]
    topic_buckets = {topic: [] for topic in prioritized_topics}
    for article in articles:
        topic_buckets[article["topic"]].append(article)

    limited_articles = []
    for topic in prioritized_topics:
        limited_articles.extend(topic_buckets[topic][: MAX_PER_TOPIC[topic]])
    return limited_articles


def fetch_articles(sources: list[dict], max_per_source: int, region: str) -> list[dict]:
    """Fetch, classify, and prioritize articles from a list of RSS feed sources."""
    articles = []
    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            entries = feed.entries[:max_per_source]
            for entry in entries:
                raw_summary = (
                    entry.get("summary")
                    or entry.get("description")
                    or entry.get("title", "")
                )
                title = entry.get("title", "(sin título)")
                cleaned_summary = _truncate(raw_summary)
                categories = _extract_categories(entry)
                topic_data = _topic_score(title, cleaned_summary, categories)
                if not topic_data:
                    continue
                relevance_score, topic_name = topic_data
                articles.append(
                    {
                        "region": region,
                        "source": source["name"],
                        "title": title,
                        "link": entry.get("link", "#"),
                        "summary": cleaned_summary,
                        "published": entry.get("published", ""),
                        "topic": topic_name,
                        "topic_order": TOPIC_PRIORITY[topic_name],
                        "score": relevance_score,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Could not fetch {source['name']}: {exc}")

    articles.sort(key=lambda article: (article["topic_order"], -article["score"], article["source"]))
    return _apply_topic_limits(articles)


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
    .section {{ margin: 20px 0 10px; font-size: 18px; font-weight: bold; color: #202124; }}
    .src  {{ margin: 20px 0 8px; font-size: 13px; font-weight: bold; color: #1a73e8;
             text-transform: uppercase; letter-spacing: .5px; }}
    .topic {{ display: inline-block; margin-bottom: 6px; font-size: 11px; font-weight: bold;
              color: #0b57d0; background: #e8f0fe; border-radius: 999px; padding: 4px 8px;
              text-transform: uppercase; }}
    .card {{ border-left: 3px solid #1a73e8; padding: 10px 14px; margin-bottom: 14px;
             background: #f8f9fa; border-radius: 0 4px 4px 0; }}
    .card h2 {{ margin: 0 0 6px; font-size: 15px; }}
    .card h2 a {{ color: #1a1a1a; text-decoration: none; }}
    .card h2 a:hover {{ text-decoration: underline; }}
    .card p  {{ margin: 0; font-size: 13px; color: #555; line-height: 1.5; }}
    .card .meta {{ font-size: 11px; color: #999; margin-top: 6px; }}
    .read-link {{ margin-top: 8px; font-size: 12px; }}
    .read-link a {{ color: #1a73e8; font-weight: bold; text-decoration: none; }}
    .read-link a:hover {{ text-decoration: underline; }}
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
        return "<p>No se encontraron noticias hoy en las categorías seleccionadas.</p>"

    blocks: list[str] = []
    current_region = None
    current_source = None
    region_titles = {
        "costa_rica": "Costa Rica",
        "mundo": "Resto del mundo",
    }

    for art in articles:
        if art["region"] != current_region:
            current_region = art["region"]
            current_source = None
            blocks.append(f'<div class="section">{region_titles.get(current_region, current_region)}</div>')
        if art["source"] != current_source:
            current_source = art["source"]
            blocks.append(f'<div class="src">{current_source}</div>')
        blocks.append(
            f'<div class="card">'
            f'  <div class="topic">{TOPIC_LABELS[art["topic"]]}</div>'
            f'  <h2><a href="{art["link"]}" target="_blank">{art["title"]}</a></h2>'
            f'  <p>{art["summary"]}</p>'
            f'  <div class="meta">{art["published"]}</div>'
            f'  <div class="read-link"><a href="{art["link"]}" target="_blank">Leer noticia</a></div>'
            f"</div>"
        )

    content = "\n".join(blocks)
    today = date.today().strftime("%A, %d de %B de %Y")
    return _HTML_TEMPLATE.format(lang=LANGUAGE, date=today, content=content)


def _render_plain(articles: list[dict]) -> str:
    """Build a plain-text fallback body."""
    if not articles:
        return "No se encontraron noticias hoy en las categorías seleccionadas."

    lines = [f"Resumen de Noticias – {date.today()}\n{'=' * 40}"]
    current_region = None
    current_source = None
    region_titles = {
        "costa_rica": "Costa Rica",
        "mundo": "Resto del mundo",
    }

    for art in articles:
        if art["region"] != current_region:
            current_region = art["region"]
            current_source = None
            lines.append(f"\n\n## {region_titles.get(current_region, current_region)}")
        if art["source"] != current_source:
            current_source = art["source"]
            lines.append(f"\n[{current_source}]")
        lines.append(f"\n• ({TOPIC_LABELS[art['topic']]}) {art['title']}")
        if art["summary"]:
            lines.append(f"  {art['summary']}")
        lines.append(f"  Leer noticia: {art['link']}")
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
    language_sources = NEWS_SOURCES.get(LANGUAGE, NEWS_SOURCES["en"])

    print(f"📡 Obteniendo noticias en '{LANGUAGE}' …")
    costa_rica_articles = fetch_articles(language_sources.get("costa_rica", []), MAX_ARTICLES, "costa_rica")
    world_articles = fetch_articles(language_sources.get("mundo", []), MAX_ARTICLES, "mundo")

    articles = costa_rica_articles + world_articles
    print(
        "📰 "
        f"{len(articles)} artículos obtenidos con prioridad fuerte para Tecnología y Ciencia "
        f"(límites por región: Tecnología={MAX_PER_TOPIC['tecnologia']}, "
        f"Ciencia={MAX_PER_TOPIC['ciencia']}, Política={MAX_PER_TOPIC['politica']})."
    )

    html_body = _render_html(articles)
    plain_body = _render_plain(articles)
    send_email(html_body, plain_body)


if __name__ == "__main__":
    main()
