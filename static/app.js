async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function tsToDate(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString("de-AT", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function trimToWords(text, maxWords) {
  if (!text) return "";
  const words = text.split(/\s+/);
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(" ") + " …";
}

let currentView = "austria";

function labelForCategory(cat) {
  switch (cat) {
    case "austria": return "Österreich";
    case "international": return "International";
    case "good_news": return "Good News";
    case "investigativ": return "Investigativ";
    case "reddit_politics": return "Reddit";
    case "fundgrube": return "Fundgrube";
    default: return cat || "";
  }
}

// ---------- Likes ----------

function hasLiked(id) {
  const liked = JSON.parse(localStorage.getItem("liked_posts") || "[]");
  return liked.includes(id);
}

function markLiked(id) {
  const liked = JSON.parse(localStorage.getItem("liked_posts") || "[]");
  if (!liked.includes(id)) {
    liked.push(id);
    localStorage.setItem("liked_posts", JSON.stringify(liked));
  }
}

async function likePost(id, btn) {
  if (hasLiked(id)) return;
  const card = btn.closest(".card");
  try {
    btn.disabled = true;
    await fetchJSON(`/api/posts/${encodeURIComponent(id)}/like`, { method: "POST" });
    markLiked(id);
    btn.textContent = "Geliked";
    btn.classList.add("liked");
    if (card) card.classList.add("liked");
    await loadStatus();
  } catch (e) {
    console.error(e);
    btn.disabled = false;
  }
}

// ---------- Status & Posts ----------

async function loadStatus() {
  try {
    const status = await fetchJSON("/api/status");
    const el = document.getElementById("status-text");
    el.textContent = `${status.posts_count} Artikel · ${status.fundgrube_count} Fundgrube`;
  } catch (e) {
    console.error(e);
  }
}

async function loadPosts(view) {
  currentView = view;
  const container = document.getElementById("posts-container");
  container.innerHTML = '<div class="loading">Lade …</div>';

  const addBtn = document.getElementById("fundgrube-add-btn");
  if (addBtn) {
    addBtn.classList.toggle("hidden", view !== "fundgrube");
  }

  if (view === "fundgrube") {
    await renderFundgrube();
    return;
  }

  let url = "/api/posts";
  if (view) {
    const params = new URLSearchParams({ category: view });
    url += "?" + params.toString();
  }

  try {
    const posts = await fetchJSON(url);
    if (!posts.length) {
      container.innerHTML = '<p class="empty-text">Keine Artikel gefunden.</p>';
      return;
    }

    const itemsHtml = posts.map(p => {
      const title = p.title || "(ohne Titel)";
      const score = p.auto_score || 0;
      const likes = p.likes || 0;
      const source = p.source || "";
      const date = tsToDate(p.created_at);
      const liked = hasLiked(p.id);
      const catLabel = labelForCategory(p.auto_category || "");
      const showThumb = (currentView !== "reddit_politics") && p.thumb;
      const commentCount = p.comment_count || 0;

      return `
        <article class="card ${liked ? "liked" : ""}">
          <div class="card-main">
            <header class="card-header">
              <div class="card-source">${source || "unbekannt"}</div>
              <div class="card-meta-right">
                ${date ? `<span>${date}</span>` : ""}
                <span>Punkte: ${score}</span>
              </div>
            </header>
            <a class="card-title" href="${p.url}" target="_blank" rel="noopener">
              ${title}
            </a>
            ${showThumb ? `<img class="card-thumb" src="${showThumb}" alt="" loading="lazy">` : ""}
            <p class="card-desc"></p>
          </div>
          <footer class="card-footer">
            <div class="card-footer-left">
              <span class="chip">${catLabel}</span>
              <span class="chip">Likes: ${likes}</span>
              <span class="chip chip-comments"
                    data-post-id="${p.id}"
                    data-count="${commentCount}">
                ${commentCount} Kommentare
              </span>
            </div>
            <div class="card-footer-right">
              <button class="like-btn ${liked ? "liked" : ""}" data-id="${p.id}" ${liked ? "disabled" : ""}>
                ${liked ? "Geliked" : "+100"}
              </button>
              <button class="comment-btn" data-id="${p.id}" data-title="${title}">
                Kommentar
              </button>
            </div>
          </footer>
        </article>
      `;
    }).join("");

    container.innerHTML = itemsHtml;

    const descNodes = container.querySelectorAll(".card-desc");
    posts.forEach((p, idx) => {
      let raw = p.description || "";
      raw = raw.replace(/submitted by[\s\S]*$/i, " ");
      raw = raw.replace(/<[^>]+>/g, " ");
      const desc = trimToWords(raw, 80);
      if (descNodes[idx]) descNodes[idx].textContent = desc;
    });

    container.querySelectorAll(".like-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        if (!hasLiked(id)) likePost(id, btn);
      });
    });

    // Bild-Zoom
    container.querySelectorAll(".card-thumb").forEach(img => {
      img.addEventListener("click", (e) => {
        e.preventDefault();
        const modal = document.getElementById("image-modal");
        const modalImg = document.getElementById("image-modal-img");
        modalImg.src = img.src;
        modal.classList.remove("hidden");
      });
    });
  } catch (e) {
    console.error(e);
    container.innerHTML = '<p class="empty-text">Fehler beim Laden der Artikel.</p>';
  }
}

// ---------- Kommentare ----------

async function fetchComments(postId) {
  return fetchJSON(`/api/comments?post_id=${encodeURIComponent(postId)}`);
}

async function sendComment(postId, text) {
  await fetchJSON("/api/comments", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ post_id: postId, text })
  });
}

async function populateComments(postId) {
  const list = document.getElementById("comment-list");
  list.innerHTML = '<div class="loading">Lade …</div>';
  const comments = await fetchComments(postId);
  if (!comments.length) {
    list.innerHTML = '<p class="empty-text">Noch keine Kommentare.</p>';
    return;
  }
  list.innerHTML = comments.map(c => `
    <div class="comment-item">
      <div class="comment-meta">
        <span>${c.author}</span>
        <span>${tsToDate(c.created_at)}</span>
      </div>
      <div class="comment-text">${c.text}</div>
    </div>
  `).join("");
}

function setupCommentsUI() {
  const modal = document.getElementById("comment-modal");
  const closeBtn = document.getElementById("comment-modal-close");
  const cancelBtn = document.getElementById("comment-cancel");
  const form = document.getElementById("comment-form");

  function close() {
    modal.classList.add("hidden");
    form.reset();
    document.getElementById("comment-list").innerHTML = "";
  }

  closeBtn.onclick = cancelBtn.onclick = close;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const postId = document.getElementById("comment-post-id").value;
    const text = document.getElementById("comment-text").value.trim();
    if (!text) return;
    try {
      await sendComment(postId, text);
      await populateComments(postId);
      form.reset();

      // Kommentar-Badge aktualisieren
      const chip = document.querySelector(
        `.chip-comments[data-post-id="${postId}"]`
      );
      if (chip) {
        const current = parseInt(chip.dataset.count || "0", 10);
        const next = current + 1;
        chip.dataset.count = String(next);
        chip.textContent = `${next} Kommentare`;
      }
    } catch {
      alert("Fehler beim Speichern.");
    }
  });

  document.getElementById("posts-container").addEventListener("click", (e) => {
    const btn = e.target.closest(".comment-btn");
    if (!btn) return;
    const id = btn.dataset.id;
    const title = btn.dataset.title || "Kommentare";
    document.getElementById("comment-post-id").value = id;
    document.getElementById("comment-modal-title").textContent = title;
    modal.classList.remove("hidden");
    populateComments(id);
  });
}

// ---------- Fundgrube ----------

async function renderFundgrube() {
  const container = document.getElementById("posts-container");
  container.innerHTML = '<div class="loading">Lade …</div>';
  try {
    const lists = await fetchJSON("/api/lists");
    const fund = lists.fundgrube || [];
    if (!fund.length) {
      container.innerHTML = '<p class="empty-text">Noch keine Einträge.</p>';
      return;
    }
    container.innerHTML = fund.map(item => `
      <article class="card">
        <div class="card-main">
          <a class="card-title" href="${item.url}" target="_blank" rel="noopener">
            ${item.title || item.url}
          </a>
          ${item.image ? `<img class="card-thumb" src="${item.image}" alt="">` : ""}
        </div>
        <div class="card-footer">
          <div class="card-footer-left">
            <span class="chip">${item.author || "Unbekannt"}</span>
            <span class="chip">${tsToDate(item.created_at)}</span>
          </div>
        </div>
      </article>
    `).join("");
  } catch (e) {
    console.error(e);
    container.innerHTML = '<p class="empty-text">Fehler beim Laden der Fundgrube.</p>';
  }
}

function setupFundgrubeAdd() {
  const iconBtn = document.getElementById("fundgrube-add-btn");
  const modal = document.getElementById("fundgrube-modal");
  const form = document.getElementById("fundgrube-form");
  const closeBtn = document.getElementById("fundgrube-close");
  const cancelBtn = document.getElementById("fundgrube-cancel");

  function openModal() { modal.classList.remove("hidden"); }
  function closeModal() {
    modal.classList.add("hidden");
    form.reset();
  }

  iconBtn.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    try {
      const res = await fetch("/api/fundgrube/add", {
        method: "POST",
        body: fd
      });
      if (res.status === 401) {
        alert("Session abgelaufen. Bitte neu einloggen.");
        window.location.href = "/login";
        return;
      }
      if (!res.ok) {
        alert("Fehler beim Speichern.");
        return;
      }
      closeModal();
      await renderFundgrube();
      await loadStatus();
    } catch (err) {
      console.error(err);
    }
  });
}

// ---------- Bild-Modal ----------

function setupImageModal() {
  const modal = document.getElementById("image-modal");
  if (!modal) return;
  const closeBtn = document.getElementById("image-modal-close");

  function close() {
    modal.classList.add("hidden");
    document.getElementById("image-modal-img").src = "";
  }

  closeBtn.addEventListener("click", close);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) close();
  });
}

// ---------- Reload ----------

async function reloadAll() {
  const btn = document.getElementById("reload-btn");
  btn.disabled = true;
  btn.textContent = "Aktualisiere …";
  try {
    await fetchJSON("/api/reload", { method: "POST" });
    await loadStatus();
    await loadPosts(currentView);
    await loadChat();
  } catch (e) {
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.textContent = "Liste aktualisieren";
  }
}

// ---------- Chat ----------

async function loadChat() {
  const box = document.getElementById("chat-messages");
  if (!box) return;
  try {
    const res = await fetch("/api/chat");
    if (!res.ok) {
      if (res.status === 401) {
        box.innerHTML = '<p class="empty-text">Session abgelaufen. Bitte neu laden.</p>';
      }
      return;
    }
    const msgs = await res.json();
    if (!msgs.length) {
      box.innerHTML = '<p class="empty-text">Noch keine Nachrichten.</p>';
      return;
    }
    box.innerHTML = msgs.map(m => `
      <div class="activity-item">
        <div class="activity-meta">
          <span>${m.author}</span>
          <span>${tsToDate(m.created_at)}</span>
        </div>
        <div class="activity-text">${m.text}</div>
      </div>
    `).join("");
  } catch (e) {
    console.error(e);
    box.innerHTML = '<p class="empty-text">Fehler beim Laden.</p>';
  }
}

function setupChat() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!form || !input) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ text })
      });
      if (res.status === 401) {
        alert("Session abgelaufen. Bitte neu einloggen.");
        window.location.href = "/login";
        return;
      }
      if (!res.ok) {
        alert("Fehler beim Senden.");
        return;
      }
      input.value = "";
      await loadChat();
    } catch (err) {
      console.error(err);
    }
  });

  setInterval(loadChat, 10000);
  loadChat();
}

// ---------- Tabs ----------

function setupTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const view = btn.dataset.view;
      document.getElementById("view-title").textContent = labelForCategory(view);
      loadPosts(view);
    });
  });
}

// ---------- Init ----------

window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("reload-btn").addEventListener("click", reloadAll);
  setupTabs();
  setupCommentsUI();
  setupFundgrubeAdd();
  setupChat();
  setupImageModal();
  await loadStatus();
  await loadPosts("austria");
});
