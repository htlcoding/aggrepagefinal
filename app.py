# app.py This is the main Flask application for the news aggregation platform.
import json
import os
import subprocess
import time

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    session,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWSDB_PATH = os.path.join(BASE_DIR, "newsdb.json")
USERS_PATH = os.path.join(BASE_DIR, "users.json")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ----------------- Helpers -----------------


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_db():
    if not os.path.exists(NEWSDB_PATH):
        return {
            "posts": [],
            "comments": [],
            "lists": {"fundgrube": []},
            "chat": [],
        }
    with open(NEWSDB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("posts", [])
    db.setdefault("comments", [])
    db.setdefault("lists", {"fundgrube": []})
    db.setdefault("chat", [])
    return db


def save_db(db):
    db.setdefault("posts", [])
    db.setdefault("comments", [])
    db.setdefault("lists", {"fundgrube": []})
    db.setdefault("chat", [])
    with open(NEWSDB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def load_users():
    if not os.path.exists(USERS_PATH):
        return {"users": []}
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_user(username):
    users = load_users().get("users", [])
    for u in users:
        if u.get("username") == username:
            return u
    return None


def require_login():
    return "user" in session


# ----------------- Login & HTML -----------------


@app.get("/login")
def login_get():
    if "user" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/login")
def login_post():
    data = request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    user = find_user(username)
    if not user or user.get("password") != password:
        return render_template("login.html")

    session["user"] = username
    return redirect(url_for("index"))


@app.get("/logout")
def logout_html():
    session.pop("user", None)
    return redirect(url_for("login_get"))


@app.get("/")
def index():
    if "user" not in session:
        return redirect(url_for("login_get"))
    return render_template("index.html")


# ----------------- API: Status & Reload -----------------


@app.get("/api/status")
def api_status():
    if not require_login():
        return jsonify({}), 401
    db = load_db()
    return jsonify({
        "posts_count": len(db.get("posts", [])),
        "fundgrube_count": len(db.get("lists", {}).get("fundgrube", [])),
    })


@app.post("/api/reload")
def api_reload():
    if not require_login():
        return jsonify({"ok": False, "error": "auth required"}), 401
    try:
        subprocess.run(
            ["python", os.path.join(BASE_DIR, "scrape_worker.py")],
            check=True,
        )
        subprocess.run(
            ["python", os.path.join(BASE_DIR, "categorize_worker.py")],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


# ----------------- API: Posts & Likes -----------------


@app.get("/api/posts")
def api_posts():
    if not require_login():
        return jsonify([]), 401

    db = load_db()
    posts = db.get("posts", [])
    comments = db.get("comments", [])

    # Kommentar-Anzahlen pro Post
    comment_counts = {}
    for c in comments:
        pid = c.get("post_id")
        if not pid:
            continue
        comment_counts[pid] = comment_counts.get(pid, 0) + 1

    category = request.args.get("category")
    if category:
        posts = [p for p in posts if p.get("auto_category") == category]

    for p in posts:
        p["comment_count"] = comment_counts.get(p.get("id"), 0)

    posts = sorted(posts, key=lambda p: p.get("auto_score", 0), reverse=True)
    return jsonify(posts[:50])


@app.post("/api/posts/<path:post_id>/like")
def api_like(post_id):
    if not require_login():
        return jsonify({"ok": False, "error": "auth required"}), 401

    db = load_db()
    posts = db.get("posts", [])
    updated_post = None

    from categorize_worker import compute_points

    for p in posts:
        if p.get("id") == post_id:
            likes = int(p.get("likes") or 0) + 1
            p["likes"] = likes

            title = p.get("title", "") or ""
            desc = p.get("description", "") or ""
            url = p.get("url", "") or ""
            category = p.get("auto_category") or "international"
            created_at = int(p.get("created_at") or 0)

            score = compute_points(title, desc, url, likes, category, created_at)
            p["auto_score"] = int(score)

            updated_post = p
            break

    if not updated_post:
        return jsonify({"ok": False, "error": "post not found"}), 404

    db["posts"] = posts
    save_db(db)
    return jsonify({"ok": True, "post": updated_post})


# ----------------- API: Kommentare pro Eintrag -----------------


@app.get("/api/comments")
def api_get_comments():
    if not require_login():
        return jsonify([]), 401

    post_id = request.args.get("post_id")
    if not post_id:
        return jsonify([])

    db = load_db()
    comments = [c for c in db["comments"] if c.get("post_id") == post_id]
    comments.sort(key=lambda c: c.get("created_at", 0))
    return jsonify(comments)


@app.post("/api/comments")
def api_add_comment():
    if not require_login():
        return jsonify({"ok": False, "error": "auth required"}), 401

    data = request.get_json(force=True) or {}
    post_id = (data.get("post_id") or "").strip()
    text = (data.get("text") or "").strip()
    if not post_id or not text:
        return jsonify({"ok": False, "error": "post_id and text required"}), 400

    db = load_db()
    db["comments"].append({
        "post_id": post_id,
        "author": session.get("user"),
        "text": text,
        "created_at": int(time.time()),
    })
    save_db(db)
    return jsonify({"ok": True})


# ----------------- API: Fundgrube (mit Bild) -----------------


@app.get("/api/lists")
def api_lists():
    if not require_login():
        return jsonify({}), 401

    db = load_db()
    return jsonify(db.get("lists", {"fundgrube": []}))


@app.post("/api/fundgrube/add")
def api_fundgrube_add():
    if not require_login():
        return jsonify({"ok": False, "error": "auth required"}), 401

    url_val = (request.form.get("url") or "").strip()
    title_val = (request.form.get("title") or "").strip() or url_val
    image_url = None

    file = request.files.get("image")
    if file and file.filename and allowed_file(file.filename):
        fname = f"{int(time.time())}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
        file.save(save_path)
        image_url = f"/static/uploads/{fname}"

    if not url_val:
        return jsonify({"ok": False, "error": "url required"}), 400

    db = load_db()
    lists = db.setdefault("lists", {})
    fund = lists.setdefault("fundgrube", [])
    fund.append({
        "id": f"user_{len(fund) + 1}",
        "title": title_val,
        "url": url_val,
        "image": image_url,
        "created_at": int(time.time()),
        "author": session.get("user"),
    })
    save_db(db)
    return jsonify({"ok": True})


# ----------------- API: Team-Chat -----------------


@app.get("/api/chat")
def api_chat_get():
    if not require_login():
        return jsonify([]), 401

    db = load_db()
    msgs = db.get("chat", [])
    msgs = sorted(msgs, key=lambda m: m.get("created_at", 0), reverse=True)[:50]
    return jsonify(list(reversed(msgs)))


@app.post("/api/chat")
def api_chat_post():
    if not require_login():
        return jsonify({"ok": False, "error": "auth required"}), 401

    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400

    db = load_db()
    chat = db.setdefault("chat", [])
    chat.append({
        "author": session.get("user"),
        "text": text,
        "created_at": int(time.time()),
    })
    save_db(db)
    return jsonify({"ok": True})


# ----------------- Debug -----------------


@app.get("/api/newsdb")
def api_newsdb():
    if not require_login():
        return jsonify({}), 401
    return jsonify(load_db())


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
