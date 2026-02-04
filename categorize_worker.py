# categorize_worker.py This programm scores and categorizes articles based on keywords.
import json
import os
import time
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWSDB_PATH = os.path.join(BASE_DIR, "newsdb.json")
STATUS_PATH = os.path.join(BASE_DIR, "reload_status.json")

MAX_PER_RUN = 5000


def load_newsdb() -> dict:
    if not os.path.exists(NEWSDB_PATH):
        data = {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
        }
        with open(NEWSDB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    with open(NEWSDB_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
        }
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
        }


def save_newsdb(data: dict) -> None:
    if "lists" not in data:
        data["lists"] = {"fundgrube": []}
    if "comments" not in data:
        data["comments"] = []
    with open(NEWSDB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def save_status(step, percent, error=None, current_title=None):
    data = {
        "step": step,
        "percent": percent,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error,
        "current_title": current_title,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ----------------------------
# Keyword-JSON laden
# ----------------------------

def load_keyword_file(filename: str) -> dict[str, float]:
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {str(k).lower(): float(v) for k, v in data.items()}
    except Exception:
        print(f"Warnung: Konnte Keyword-Datei {filename} nicht laden oder parsen.")
        return {}


KEYWORDS_AT = load_keyword_file("keywords_austria.json")
KEYWORDS_INT = load_keyword_file("keywords_international.json")
KEYWORDS_GOOD = load_keyword_file("keywords_good_news.json")
KEYWORDS_INV = load_keyword_file("keywords_investigativ.json")


def keyword_score_from_json(title: str, desc: str, category: str) -> int:
    """
    Nutzt deine JSON-Keywords pro Kategorie.
    Score = Summe(weight * 100) für jedes Keyword, das im Text vorkommt.
    """
    text = f"{title} {desc}".lower()

    if category == "austria":
        mapping = KEYWORDS_AT
    elif category == "international":
        mapping = KEYWORDS_INT
    elif category == "good_news":
        mapping = KEYWORDS_GOOD
    elif category == "investigativ":
        mapping = KEYWORDS_INV
    else:
        mapping = {}

    score = 0.0
    for word, weight in mapping.items():
        if word in text:
            score += weight * 100.0
    return int(score)


def compute_points(title: str, desc: str, url: str, likes: int, category: str, created_at: int) -> int:
    # Basis: Likes (inkl. Reddit-Ups + User-Likes)
    score = max(0, int(likes)) * 100

    # Themen-Boost über JSON-Keywords
    score += keyword_score_from_json(title, desc, category)

    # Frische-Bonus
    if created_at:
        age_hours = max(0, (datetime.now().timestamp() - created_at) / 3600.0)
        freshness = max(0, 200 - int(age_hours * 10))  # nach ~20h ist der Bonus weg
        score += freshness

    return score


# ----------------------------
# Harte Obergrenze: max. 3 Artikel pro Quelle
# ----------------------------

def pick_per_source(posts: list[dict], max_per_source: int = 3) -> list[dict]:
    """
    Harte Obergrenze: max_per_source Artikel pro Quelle und Kategorie.
    Wenn eine Quelle weniger Artikel hat, werden alle genommen.
    """
    by_source = defaultdict(list)
    for p in posts:
        src = p.get("source") or "unknown"
        by_source[src].append(p)

    selected = []
    for src, lst in by_source.items():
        lst_sorted = sorted(lst, key=lambda x: x.get("auto_score", 0), reverse=True)
        chosen = lst_sorted[:max_per_source]  # HIER harte Obergrenze
        selected.extend(chosen)

    selected.sort(key=lambda p: p.get("auto_score", 0), reverse=True)
    return selected


# ----------------------------
# main
# ----------------------------

def main():
    db = load_newsdb()
    posts = db.get("posts", [])

    if not posts:
        print("Keine Artikel in newsdb.json.")
        save_status("Keine Artikel gefunden", 100, None, None)
        return

    total = len(posts)
    print(f"Bewerte {total} Artikel …")
    save_status("Bewertung gestartet …", 60, None, None)

    for i, post in enumerate(posts[:MAX_PER_RUN]):
        title = post.get("title", "") or ""
        desc = post.get("description", "") or ""
        url = post.get("url", "") or ""
        likes = int(post.get("likes") or 0)
        category = post.get("auto_category") or "international"
        created_at = int(post.get("created_at") or 0)

        score = compute_points(title, desc, url, likes, category, created_at)
        post["auto_score"] = int(score)

        short_title = title[:80]
        progress = 60 + int(((i + 1) / max(1, min(total, MAX_PER_RUN))) * 40)
        if progress >= 100 and i + 1 < total:
            progress = 99
        save_status("Bewertung läuft …", progress, None, short_title)
        time.sleep(0.002)

    # Nach Punkten sortieren (absteigend)
    posts.sort(key=lambda p: p.get("auto_score", 0), reverse=True)

    # Pro Kategorie harte Obergrenze 3 Artikel pro Quelle
    by_cat = defaultdict(list)
    for p in posts:
        by_cat[p.get("auto_category") or "international"].append(p)

    final_posts = []
    for cat, plist in by_cat.items():
        picked = pick_per_source(plist, max_per_source=3)

        # Debug: Kontrolle, dass keine Quelle >3 hat
        src_counts = defaultdict(int)
        for p in picked:
            src_counts[p.get("source") or "unknown"] += 1
        print(f"Kategorie {cat}: {len(picked)} Artikel nach pick_per_source (max 3 pro Quelle)")
        for src, cnt in sorted(src_counts.items()):
            print(f"  {src}: {cnt}")

        final_posts.extend(picked)

    db["posts"] = final_posts
    save_newsdb(db)
    save_status("Bewertung abgeschlossen", 100, None, None)
    print("Fertig, Punkte neu gesetzt, JSON-Keywords genutzt und harte Obergrenze 3 Artikel pro Quelle.")


if __name__ == "__main__":
    main()
