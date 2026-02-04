# scrape_worker.py This program fetches news articles from various RSS feeds and Reddit.
import json
import os
import time

import feedparser
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWSDB_PATH = os.path.join(BASE_DIR, "newsdb.json")

# ----------------------------
# Feeds pro Kategorie
# ----------------------------

# AT + DACH: nur verlässlich funktionierende Quellen
FEEDS_AT = [
    # nationale / überregionale
    {"name": "ORF.at", "url": "http://rss.orf.at/news.xml"},
    {"name": "Der Standard", "url": "https://www.derstandard.at/rss"},
    {"name": "Die Presse", "url": "https://www.diepresse.com/rss"},
    {"name": "Falter", "url": "https://www.falter.at/rss"},
    {"name": "Datum", "url": "https://www.datum.at/rss"},
    {"name": "Kontrast", "url": "https://kontrast.at/feed/"},
    {"name": "Momentum Institut", "url": "https://www.momentum-institut.at/rss"},
    {"name": "ZackZack", "url": "https://zackzack.at/feed/"},

    # große Boulevard/Regional
    {"name": "Kurier", "url": "https://kurier.at/xml/rssd"},
    {"name": "Kronen Zeitung", "url": "https://api.krone.at/v1/rss/rssfeed-google.xml?id=2311992"},
    {"name": "Tiroler Tageszeitung (Politik)", "url": "https://www.tt.com/rss/politik.xml"},
]

FEEDS_INT = [
     {"name": "BBC News (World)", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "Deutsche Welle (All, EN)", "url": "https://rss.dw.com/rdf/rss-en-all"},
    {"name": "Deutsche Welle (World, EN)", "url": "https://rss.dw.com/rdf/rss-en-world"},

    # International newspapers / pan-european
    {"name": "The Guardian (World)", "url": "https://www.theguardian.com/world/rss"},
    {"name": "Le Monde (International)", "url": "https://monde-diplomatique.de"},
    {"name": "Euronews (World News, MRSS)", "url": "https://www.euronews.com/rss?format=mrss&level=theme&name=news"},
    {"name": "Euronews (My Europe, MRSS)", "url": "https://euronews.com/rss?format=mrss&level=vertical&name=my-europe"},
    {"name": "International Crisis Group (Global feed)", "url": "https://www.crisisgroup.org/rss"},
    {"name": "Council of the EU (Press releases)", "url": "https://www.consilium.europa.eu/en/rss/pressreleases.ashx"},
    {"name": "Council of the EU (Foreign Affairs Council meetings)", "url": "https://www.consilium.europa.eu/en/rss/meetings.ashx?cat=fac"},
    {"name": "European Parliament (External relations)", "url": "https://www.europarl.europa.eu/rss/topic/903/en.xml"},
    {"name": "European Parliament (Press releases)", "url": "https://www.europarl.europa.eu/rss/doc/press-releases/en.xml"},
    {"name": "UN Geneva (Press releases)", "url": "https://www.ungeneva.org/news-media/press-releases-list/rss.xml"},
    {"name": "UN Geneva (Meeting summaries)", "url": "https://www.ungeneva.org/news-media/meeting-summaries-list/rss.xml"},
    {"name": "UN News (Top stories, EN)", "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml"},
]

FEEDS_GOOD = [
    {"name": "Good News Network (All)", "url": "https://www.goodnewsnetwork.org/feed/"},
    {"name": "Positive News", "url": "https://www.positive.news/feed/"},
    {"name": "The Optimist Daily", "url": "https://www.optimistdaily.com/feed/"},
    {"name": "Reasons to be Cheerful", "url": "https://reasonstobecheerful.world/feed/"},
    {"name": "Good Good Good", "url": "https://www.goodgoodgood.co/articles/rss.xml"},
    {"name": "YES! Magazine", "url": "https://www.yesmagazine.org/feed/"},
    {"name": "Sunny Skyz", "url": "https://feeds.feedburner.com/SunnySkyz"},
    {"name": "SA Good News", "url": "https://www.sagoodnews.co.za/feed"},
    {"name": "Not All News is Bad!", "url": "https://notallnewsisbad.com/feed"},
    {"name": "The Good News Movement", "url": "https://thegoodnewsmovement.com/feed"},
    {"name": "Upworthy", "url": "https://upworthy.com/feeds/feed.rss"},
    {"name": "Good Black News", "url": "https://goodblacknews.org/feed"},
    {"name": "Good News Shared", "url": "https://goodnewsshared.com/feed"},
    {"name": "Life Beyond Numbers", "url": "https://lifebeyondnumbers.com/feed"},
    {"name": "Good News Pilipinas", "url": "https://goodnewspilipinas.com/feed"},
    {"name": "Good News EU", "url": "https://goodnews.eu/feed/"}
]

FEEDS_INV = [
    {"name": "ProPublica (Investigativ, USA)", "url": "https://www.propublica.org/feeds/propublica/main"},
    {"name": "ICIJ – International Consortium of Investigative Journalists", "url": "https://www.icij.org/feed/"},
    {"name": "ICIJ – Projekte (RSS)", "url": "https://www.icij.org/feeds/rss/projects.xml"},
    {"name": "OCCRP (Crime & Corruption Investigations)", "url": "https://www.occrp.org/en?format=feed&type=rss"},
    {"name": "Bellingcat (Open-Source Investigations)", "url": "https://www.bellingcat.com/feed/"},
    {"name": "CORRECTIV (Investigativ, DE)", "url": "https://correctiv.org/feed/"},
    {"name": "openDemocracy (Investigativ/Politics)", "url": "https://www.opendemocracy.net/xml/rss/home/index.xml"},
    {"name": "openDemocracy – Dark Money Investigations", "url": "https://www.opendemocracy.net/en/dark-money-investigations/feed"},
    {"name": "The Markup (Tech/Power Investigations)", "url": "https://themarkup.org/feeds/rss.xml"},
    {"name": "The Marshall Project (Criminal Justice Investigations)", "url": "https://www.themarshallproject.org/rss/recent.rss"},
    {"name": "Unearthed (Greenpeace UK Investigations)", "url": "https://unearthed.greenpeace.org/feed"},
    {"name": "Lighthouse Reports (Investigativ, EU)", "url": "https://lighthousereports.nl/feed"},
    {"name": "The Intercept (Investigations/War/Surveillance)", "url": "https://theintercept.com/feed"},
    {"name": "The Intercept – Special Investigations", "url": "https://theintercept.com/special-investigations/feed"},
]

# Subreddits mit Fokus AT/Europa/Politik
REDDIT_SUBS = [
    "Austria",
    "wien",
    "Noesterreich",
    "europe",
    "EuropeanUnion",
    "AskEurope",
    "de",
    "UpliftingNews",
    "worldnews",
    "PoliticalDiscussion",
    "goodnews"
]

CATEGORIES = {
    "austria": FEEDS_AT,
    "international": FEEDS_INT,
    "good_news": FEEDS_GOOD,
    "investigativ": FEEDS_INV,
}

# ----------------------------
# Limits pro Quelle
# ----------------------------

MAX_ENTRIES_BY_SOURCE = {
    # nationale / überregionale – dürfen mehr
    "ORF.at": 80,
    "Der Standard": 120,
    "Die Presse": 80,
    "Falter": 80,
    "Datum": 40,
    "Kontrast": 40,
    "Momentum Institut": 40,
    "ZackZack": 40,

    # regionale / boulevard – stärker begrenzen
    "Kurier": 60,
    "Kronen Zeitung": 60,
    "Tiroler Tageszeitung (Politik)": 60,
}

DEFAULT_MAX_PER_FEED = 50

# ----------------------------
# Reddit-Header
# ----------------------------

REDDIT_HEADERS = {
    "User-Agent": "aggrepage/1.0 by yourname"
}

# ----------------------------
# Hilfsfunktionen
# ----------------------------


def ts_from_entry(entry) -> int:
    if getattr(entry, "published_parsed", None):
        import time as _time
        return int(_time.mktime(entry.published_parsed))
    return int(time.time())


def strip_tags(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", text or "")


def make_post(category: str, source_name: str, title: str, desc: str, url: str, created_ts: int) -> dict:
    return {
        "id": url,
        "source": source_name,
        "title": title,
        "description": desc,  # Plain-Text
        "url": url,
        "created_at": int(created_ts),
        "auto_category": category,
        "auto_score": 0,
        "likes": 0,
        "manual_category": None,
    }


def load_existing_lists_comments() -> dict:
    if not os.path.exists(NEWSDB_PATH):
        return {"lists": {"fundgrube": []}, "comments": []}
    try:
        with open(NEWSDB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "lists": data.get("lists", {"fundgrube": []}),
            "comments": data.get("comments", []),
        }
    except Exception:
        return {"lists": {"fundgrube": []}, "comments": []}


def save_newsdb(posts: list[dict], lists: dict, comments: list[dict]) -> None:
    data = {"posts": posts, "comments": comments, "lists": lists}
    with open(NEWSDB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------
# Feed-Loading mit per-Source-Limit
# ----------------------------


def fetch_category(category: str, feeds: list[dict]) -> list[dict]:
    posts: list[dict] = []
    for src in feeds:
        name = src["name"]
        url = src["url"]
        max_entries = MAX_ENTRIES_BY_SOURCE.get(name, DEFAULT_MAX_PER_FEED)

        try:
            feed = feedparser.parse(url)
        except Exception:
            print(f"Fehler beim Laden von Feed {name} ({url})")
            continue

        entries = getattr(feed, "entries", [])
        print(f"{category} / {name}: {len(entries)} Einträge (verwende max {max_entries})")

        for entry in entries[:max_entries]:
            link = getattr(entry, "link", None)
            if not link:
                continue
            title = getattr(entry, "title", "") or ""
            desc_raw = getattr(entry, "summary", "") or ""
            desc = strip_tags(desc_raw)
            created_ts = ts_from_entry(entry)
            posts.append(make_post(category, name, title, desc, link, created_ts))
    return posts


def get_reddit_thumb(d: dict) -> str:
    thumb = ""
    t = d.get("thumbnail")
    if isinstance(t, str) and t.startswith("http"):
        thumb = t
    if not thumb:
        preview = d.get("preview") or {}
        images = preview.get("images") or []
        if images:
            src = images[0].get("source") or {}
            url = src.get("url") or ""
            if isinstance(url, str) and url.startswith("http"):
                thumb = url
    return thumb


def fetch_reddit_json(subs: list[str]) -> list[dict]:
    posts: list[dict] = []
    blocklist = ["trump", "maga"]  # rausfiltern

    for sub in subs:
        api_url = f"https://www.reddit.com/r/{sub}/top.json?limit=20&t=day&raw_json=1"
        try:
            resp = requests.get(api_url, headers=REDDIT_HEADERS, timeout=10)
            if resp.status_code != 200:
                print(f"Reddit {sub}: HTTP {resp.status_code}")
                continue
            data = resp.json()
        except Exception as e:
            print(f"Fehler beim Laden von Reddit /r/{sub}: {e}")
            continue

        children = data.get("data", {}).get("children", [])
        print(f"reddit_politics / r/{sub}: {len(children)} Einträge")

        for child in children:
            d = child.get("data", {})
            title = d.get("title") or ""
            if any(b.lower() in title.lower() for b in blocklist):
                continue

            thumb = get_reddit_thumb(d)
            selftext = d.get("selftext") or ""
            ups = int(d.get("ups") or 0)
            permalink = d.get("permalink") or ""
            full_url = "https://www.reddit.com" + permalink if permalink else d.get("url") or ""
            created_utc = int(d.get("created_utc") or time.time())
            subreddit = d.get("subreddit") or sub

            text = selftext.strip()
            desc_parts = [f"/r/{subreddit}"]
            if text:
                desc_parts.append(text)
            desc_parts.append(f"Upvotes: {ups}")
            desc = "\n\n".join(desc_parts)

            post = make_post("reddit_politics", f"r/{subreddit}", title, desc, full_url, created_utc)
            post["likes"] = ups
            if thumb:
                post["thumb"] = thumb
            posts.append(post)
    return posts


# ----------------------------
# main
# ----------------------------


def main():
    all_posts: list[dict] = []
    meta = load_existing_lists_comments()
    lists = meta["lists"]
    comments = meta["comments"]

    for cat, feeds in CATEGORIES.items():
        cat_posts = fetch_category(cat, feeds)
        print(f"{cat}: {len(cat_posts)} Artikel (nach Limit)")
        all_posts.extend(cat_posts)

    reddit_posts = fetch_reddit_json(REDDIT_SUBS)
    print(f"reddit_politics: {len(reddit_posts)} Artikel")
    all_posts.extend(reddit_posts)

    # Statistik pro Quelle ausgeben
    from collections import defaultdict
    source_counts = defaultdict(int)
    for p in all_posts:
        src = p.get("source") or "unknown"
        source_counts[src] += 1

    print("\nArtikel pro Quelle (über alle Kategorien, nach Limit):")
    for src, count in sorted(source_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"{src}: {count}")

    save_newsdb(all_posts, lists, comments)
    print(f"\nGesamt {len(all_posts)} Artikel gespeichert.")


if __name__ == "__main__":
    main()
