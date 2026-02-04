# facebook_worker.py
# Scrapes Facebook news pages and extracts highly engaged posts
# Engagement Score = (comments × 2) + reactions

import json
import os
import time
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWSDB_PATH = os.path.join(BASE_DIR, "newsdb.json")
STATUS_PATH = os.path.join(BASE_DIR, "reload_status.json")

# Austrian news pages to monitor
FACEBOOK_PAGES = [
    {
        "name": "Zeitimbild",
        "page_id": "zeitimbild",  # Update with real numeric ID
    },
    {
        "name": "ORF.at",
        "page_id": "orfdotatat",  # Update with real numeric ID
    },
    {
        "name": "Heute",
        "page_id": "heute",  # Update with real numeric ID
    },
    {
        "name": "Der Standard",
        "page_id": "derstandard",  # Update with real numeric ID
    },
]


def load_newsdb() -> dict:
    """Load existing news database."""
    if not os.path.exists(NEWSDB_PATH):
        data = {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
            "chat": [],
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
            "chat": [],
        }
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
            "chat": [],
        }


def save_newsdb(data: dict) -> None:
    """Save news database."""
    if "lists" not in data:
        data["lists"] = {"fundgrube": []}
    if "comments" not in data:
        data["comments"] = []
    if "posts" not in data:
        data["posts"] = []
    
    
