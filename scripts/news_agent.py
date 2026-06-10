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
from calendar import timegm
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
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
        "google", "microsoft", "apple", "meta", "xiaomi", "samsung", "tesla",
        "android", "iphone", "tiktok", "red social", "redes sociales", "plataforma",
        "computación", "computacion", "algoritmo", "algoritmos", "automatización",
        "automatizacion", "programación", "programacion", "desarrollador", "desarrollo",
        "innovación", "innovacion", "electrónico", "electronico", "dispositivo", "dispositivos",
    ],
    "ciencia": [
        "ciencia", "científico", "cientifica", "científicos", "cientificos", "investigación",
        "investigacion", "estudio", "laboratorio", "espacio", "nasa", "salud", "medicina",
        "biología", "biologia", "física", "fisica", "química", "quimica", "genética", "genetica",
        "astronomía", "astronomia", "vacuna", "vacunas", "planeta", "universo", "descubrimiento",
        "experimento", "cientifica", "cientifico", "científicamente", "investigador", "investigadora",
    ],
    "politica": [
        "política", "politica", "gobierno", "presidente", "presidencia", "asamblea",
        "diputado", "diputada", "diputados", "diputadas", "congreso", "elecciones",
        "canciller", "ministro", "ministra", "decreto", "ley", "reforma", "partido",
        "alcalde", "alcaldesa", "municipalidad", "poder ejecutivo", "poder legislativo",
        "tribunal supremo de elecciones", "tse", "parlamento", "senado", "senador", "senadora",
        "campaña", "campana", "candidato", "candidata", "oposición", "oposicion",
    ],
}

TECH_SOURCE_HINTS = [
    "tecnologia", "tecnologia y ciencia", "technology", "tech", "tecnología y gadgets",
    "tecnología y innovación", "tecnología e innovación", "innovation", "startups", "ai",
    "artificial intelligence", "ciencia y tecnologia", "science and technology",
]

SCIENCE_SOURCE_HINTS = [
    "ciencia", "science", "salud", "health", "espacio", "space", "investigacion",
    "investigación", "science and technology", "ciencia y tecnologia",
]

POLITICS_SOURCE_HINTS = [
    "politica", "política", "government", "gobierno", "elections", "elecciones",
    "congreso", "parlamento",
]

NEWS_SOURCES = {
    "es": {
        "costa_rica": [
            {"name": "Delfino.cr", "url": "https://delfino.cr/feed"},
            {"name": "Despertar.cr", "url": "https://despertar.opennemas.com/rss/all.xml"},
            {"name": "Diario Extra", "url": "https://www.diarioextra.com/RSS"},
            {"name": "La Nación", "url": "https://www.nacion.com/arcio/rss/category/tecnologia/"},
            {"name": "CRHoy", "url": "https://www.crhoy.com/feed/"},
        ],
        "mundo": [
            {"name": "BBC Mundo", "url": "https://feeds.bbci.co.uk/mundo/rss.xml"},
            {"name": "El País", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
            {"name": "CNN en Español", "url": "http://cnnespanol.cnn.com/feed/"},
            {"name": "Xataka", "url": "https://www.xataka.com/feedburner.xml"},
            {"name": "Hipertextual", "url": "https://hipertextual.com/feed"},
            {"name": "Muy Interesante", "url": "https://www.muyinteresante.com/feed/rss2/"},
            {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
        ],
    },
    "en": {
        "costa_rica": [],
        "mundo": [
            {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/rss.xml"},
            {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews"},
            {"name": "AP News", "url": "https://rsshub.app/apnews/topics/apf-topnews"},
            {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
            {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
            {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
            {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
            {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
            {"name": "ScienceDaily", "url": "https://www.sciencedaily.com/rss/top.xml"},
        ],
    },
}

LANGUAGE = os.environ.get("NEWS_LANGUAGE", "es")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "20"))
MAX_PER_TOPIC = {
    "tecnologia": int(os.environ.get("MAX_TECHNOLOGY", "10")),
    "ciencia": int(os.environ.get("MAX_SCIENCE", "6")),
    "politica": int(os.environ.get("MAX_POLITICS", "2")),
}
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int = 220) -> str:
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


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    return f"{masked_local}@{domain}"


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


def _entry_date(entry: dict) -> date | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc).date()
    return None


def _is_today_entry(entry: dict) -> bool:
    published_date = _entry_date(entry)
    if published_date is None:
        return False
    return published_date == datetime.now(timezone.utc).date()


def _source_bias(source_name: str, categories: list[str], topic: str) -> int:
    combined = _normalize(f"{source_name} {' '.join(categories)}")
    hints_map = {
        "tecnologia": TECH_SOURCE_HINTS,
        "ciencia": SCIENCE_SOURCE_HINTS,
        "politica": POLITICS_SOURCE_HINTS,
    }
    score = 0
    for hint in hints_map[topic]:
        if _normalize(hint) in combined:
            score += 12 if topic == "tecnologia" else 8
    return score


def _topic_score(source_name: str, title: str, summary: str, categories: list[str]) -> tuple[int, str] | None:
    title_text = _normalize(title)
    summary_text = _normalize(summary)
    categories_text = _normalize(" ".join(categories))

    scores = defaultdict(int)
    for topic in TOPIC_PRIORITY:
        title_weight = 9 if topic == "tecnologia" else 5
        summary_weight = 4 if topic == "tecnologia" else 2
        category_weight = 10 if topic == "tecnologia" else 6
        for keyword in TOPIC_KEYWORDS[topic]:
            scores[topic] += _count_keyword_matches(title_text, keyword) * title_weight
            scores[topic] += _count_keyword_matches(summary_text, keyword) * summary_weight
            scores[topic] += _count_keyword_matches(categories_text, keyword) * category_weight
        scores[topic] += _source_bias(source_name, categories, topic)

    if scores["tecnologia"] > 0 and scores["tecnologia"] >= scores["ciencia"]:
        return scores["tecnologia"], "tecnologia"
    if scores["ciencia"] > 0 and scores["ciencia"] >= scores["politica"]:
        return scores["ciencia"], "ciencia"
    if scores["politica"] > 0:
        return scores["politica"], "politica"
    return None


def _dedupe_articles(articles: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for article in articles:
        key = (_normalize(article["title"]), article["link"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def _apply_topic_limits(articles: list[dict]) -> list[dict]:
    topic_buckets = {topic: [] for topic in TOPIC_PRIORITY}
    for article in articles:
        topic_buckets[article["topic"]].append(article)

    limited_articles = []
    technology_articles = topic_buckets["tecnologia"][: MAX_PER_TOPIC["tecnologia"]]
    science_articles = topic_buckets["ciencia"][: MAX_PER_TOPIC["ciencia"]]
    politics_articles = topic_buckets["politica"][: MAX_PER_TOPIC["politica"]]

    limited_articles.extend(technology_articles)
    limited_articles.extend(science_articles)

    if len(technology_articles) >= max(1, MAX_PER_TOPIC["tecnologia"] // 2):
        limited_articles.extend(politics_articles)

    return _dedupe_articles(limited_articles)


def fetch_articles(sources: list[dict], max_per_source: int, region: str) -> list[dict]:
    """Fetch, classify, and prioritize articles from a list of RSS feed sources."""
    articles = []
    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            entries = feed.entries[:max_per_source]
            print(f"[INFO] Fuente '{source['name']}' devolvió {len(entries)} entradas en {region}.")
            for entry in entries:
                if not _is_today_entry(entry):
                    continue
                raw_summary = (
                    entry.get("summary")
                    or entry.get("description")
                    or entry.get("title", "")
                )
                title = entry.get("title", "(sin título)")
                cleaned_summary = _truncate(raw_summary)
                categories = _extract_categories(entry)
                topic_data = _topic_score(source["name"], title, cleaned_summary, categories)
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
    body {{ font-family: Arial, sans-serif; color: #222; margin: 0; padding: 24px; background: #ffffff; }}
    .wrap {{ max-width: 700px; margin: 0 auto; }}
    h1 {{ font-size: 22px; margin-bottom: 4px; }}
    .intro {{ color: #555; font-size: 14px; margin-bottom: 20px; }}
    .section {{ margin-top: 24px; font-size: 18px; font-weight: bold; }}
    .article {{ margin: 14px 0; padding-bottom: 14px; border-bottom: 1px solid #e5e5e5; }}
    .article-title {{ font-size: 15px; font-weight: bold; margin-bottom: 4px; }}
    .article-meta {{ font-size: 12px; color: #666; margin-bottom: 4px; }}
    .article-summary {{ font-size: 13px; color: #333; margin: 6px 0; }}
    .article-link a {{ color: #0b57d0; text-decoration: none; }}
    .footer {{ margin-top: 24px; font-size: 12px; color: #777; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Noticias de tecnología y ciencia</h1>
    <div class="intro">Resumen automático con foco principal en tecnología, seguido de ciencia y algunas noticias de política cuando son relevantes.</div>
    {content}
    <div class="footer">Enviado automáticamente por GitHub Actions.</div>
  </div>
</body>
</html>
"""


def _render_html(articles: list[dict]) -> str:
    if not articles:
        return "<p>No se encontraron noticias relevantes hoy.</p>"

    blocks = []
    current_region = None
    region_titles = {
        "costa_rica": "Costa Rica",
        "mundo": "Internacionales",
    }

    for art in articles:
        if art["region"] != current_region:
            current_region = art["region"]
            blocks.append(f'<div class="section">{region_titles.get(current_region, current_region)}</div>')
        blocks.append(
            f'<div class="article">'
            f'  <div class="article-title">[{TOPIC_LABELS[art["topic"]]}] {art["title"]}</div>'
            f'  <div class="article-meta">{art["source"]} · {art["published"]}</div>'
            f'  <div class="article-summary">{art["summary"]}</div>'
            f'  <div class="article-link"><a href="{art["link"]}" target="_blank">Ver noticia</a></div>'
            f'</div>'
        )

    return _HTML_TEMPLATE.format(lang=LANGUAGE, content="\n".join(blocks))


def _render_plain(articles: list[dict]) -> str:
    if not articles:
        return "No se encontraron noticias relevantes hoy."

    lines = [
        f"Noticias de tecnología y ciencia – {date.today()}",
        "Resumen automático con foco principal en tecnología.",
        "=" * 50,
    ]
    current_region = None
    region_titles = {
        "costa_rica": "Costa Rica",
        "mundo": "Internacionales",
    }

    for art in articles:
        if art["region"] != current_region:
            current_region = art["region"]
            lines.append(f"\n\n## {region_titles.get(current_region, current_region)}")
        lines.append(f"\n- [{TOPIC_LABELS[art['topic']]}] {art['title']}")
        lines.append(f"  Fuente: {art['source']}")
        if art["summary"]:
            lines.append(f"  {art['summary']}")
        lines.append(f"  {art['link']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_email(html_body: str, plain_body: str, article_count: int) -> None:
    today = date.today().strftime("%d/%m/%Y")
    subject = f"Noticias de tecnología y ciencia – {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"[INFO] Preparando envío SMTP desde {_mask_email(EMAIL_SENDER)} hacia {_mask_email(EMAIL_RECIPIENT)}.")
    print(f"[INFO] Asunto: {subject}")
    print(f"[INFO] Artículos en correo: {article_count}")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        send_result = server.sendmail(EMAIL_SENDER, [EMAIL_RECIPIENT], msg.as_string())

    if send_result:
        raise RuntimeError(f"SMTP no aceptó todos los destinatarios: {send_result}")

    print(f"✅ Gmail aceptó el correo para {_mask_email(EMAIL_RECIPIENT)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    language_sources = NEWS_SOURCES.get(LANGUAGE, NEWS_SOURCES["en"])

    print(f"📡 Obteniendo noticias en '{LANGUAGE}' …")
    costa_rica_articles = fetch_articles(language_sources.get("costa_rica", []), MAX_ARTICLES, "costa_rica")
    world_articles = fetch_articles(language_sources.get("mundo", []), MAX_ARTICLES, "mundo")

    articles = _dedupe_articles(costa_rica_articles + world_articles)
    topic_counts = Counter(article["topic"] for article in articles)
    region_counts = Counter(article["region"] for article in articles)

    print(f"[INFO] Artículos finales: {len(articles)}")
    print(f"[INFO] Por región: {dict(region_counts)}")
    print(f"[INFO] Por tema: {dict(topic_counts)}")

    if not articles:
        raise RuntimeError("No se obtuvieron noticias para enviar. Revisa feeds, filtros o clasificación.")

    html_body = _render_html(articles)
    plain_body = _render_plain(articles)
    send_email(html_body, plain_body, len(articles))


if __name__ == "__main__":
    main()
