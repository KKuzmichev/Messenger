const API = "http://127.0.0.1:8000";
let TOKEN = localStorage.getItem("token");
let REFRESH_TOKEN = localStorage.getItem("refresh_token");
let CURRENT_USER = null;
let CURRENT_CONV = null;
let CONVERSATIONS_CACHE = {};

async function api(method, path, body = null, extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;
  const isFormData = body instanceof FormData;
  if (body && !isFormData) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let res = await fetch(`${API}${path}`, { method, headers, body });
  if (res.status === 401 && REFRESH_TOKEN) {
    const refreshRes = await fetch(`${API}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: REFRESH_TOKEN }),
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      TOKEN = data.access_token;
      REFRESH_TOKEN = data.refresh_token;
      localStorage.setItem("token", TOKEN);
      localStorage.setItem("refresh_token", REFRESH_TOKEN);
      headers["Authorization"] = `Bearer ${TOKEN}`;
      res = await fetch(`${API}${path}`, { method, headers, body });
    } else {
      logout();
      throw new Error("Session expired");
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.status === 204 ? null : res.json();
}

function $(id) { return document.getElementById(id); }
function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// --- Auth ---
$("show-register").onclick = () => { hide("login-form"); show("register-form"); };
$("show-login").onclick = () => { hide("register-form"); show("login-form"); };

$("register-btn").onclick = async () => {
  const username = $("reg-username").value;
  const password = $("reg-password").value;
  const displayName = $("reg-display-name").value;
  try {
    await CRYPTO.generateKeyPair();
    const publicKey = await CRYPTO.exportPublicKey();
    const res = await api("POST", "/api/auth/register", {
      username, password, display_name: displayName, public_key: publicKey,
    });
    TOKEN = res.access_token;
    REFRESH_TOKEN = res.refresh_token;
    localStorage.setItem("token", TOKEN);
    localStorage.setItem("refresh_token", REFRESH_TOKEN);
    localStorage.setItem("keygen_done", "1");
    await loadApp();
  } catch (e) { alert(e.message); }
};

$("login-btn").onclick = async () => {
  const username = $("login-username").value;
  const password = $("login-password").value;
  try {
    const res = await api("POST", "/api/auth/login", { username, password });
    TOKEN = res.access_token;
    REFRESH_TOKEN = res.refresh_token;
    localStorage.setItem("token", TOKEN);
    localStorage.setItem("refresh_token", REFRESH_TOKEN);
    if (!localStorage.getItem("keygen_done")) {
      await CRYPTO.generateKeyPair();
      localStorage.setItem("keygen_done", "1");
    }
    await loadApp();
  } catch (e) { alert(e.message); }
};

function logout() {
  TOKEN = null;
  REFRESH_TOKEN = null;
  CURRENT_USER = null;
  CURRENT_CONV = null;
  localStorage.clear();
  hide("app");
  hide("chat-placeholder");
  hide("messages-list");
  hide("send-area");
  show("auth");
  hide("register-form");
  show("login-form");
}
$("logout-btn").onclick = logout;

// --- App ---
async function loadApp() {
  if (!(await CRYPTO.loadPrivateKey())) {
    await CRYPTO.generateKeyPair();
    const pub = await CRYPTO.exportPublicKey();
    await api("PUT", "/api/users/me", { public_key: pub });
  }
  hide("auth");
  show("app");
  hide("chat-placeholder");
  hide("messages-list");
  hide("send-area");
  CURRENT_USER = await api("GET", "/api/users/me");
  $("current-user").textContent = CURRENT_USER.display_name;
  await loadConversations();
  await loadUsers();
}

// --- Users search ---
let _usersAbort;
async function loadUsers() {
  if (_usersAbort) _usersAbort.abort();
  _usersAbort = new AbortController();
  const list = $("users-list");
  list.innerHTML = "";
  const query = $("user-search").value.trim();
  if (!query) return;
  try {
    const users = await api("GET", `/api/users?q=${encodeURIComponent(query)}`);
    for (const u of users) {
      if (u.id === CURRENT_USER.id) continue;
      const div = document.createElement("div");
      div.className = "user-item";
      div.innerHTML = `<span>${escapeHtml(u.display_name)} (@${escapeHtml(u.username)})</span>`;
      div.onclick = async () => {
        const conv = await api("POST", "/api/conversations", {
          type: "direct", member_ids: [u.id],
        });
        await loadConversations(conv.id);
      };
      list.appendChild(div);
    }
  } catch {}
}
$("user-search").oninput = debounce(loadUsers, 300);

// --- Conversations ---
async function loadConversations(selectId = null) {
  const convs = await api("GET", "/api/conversations");
  CONVERSATIONS_CACHE = {};
  const list = $("conversations-list");
  list.innerHTML = "";
  for (const c of convs) {
    CONVERSATIONS_CACHE[c.id] = c;
    const div = document.createElement("div");
    div.className = "conv-item" + (c.id === selectId ? " active" : "");
    div.dataset.convId = c.id;
    const members = await api("GET", `/api/conversations/${c.id}`);
    const myId = CURRENT_USER?.id;
    const names = await Promise.all(
      members.member_ids
        .filter(id => id !== myId)
        .slice(0, 3)
        .map(async id => {
          try { const u = await api("GET", `/api/users/${id}`); return u.display_name; }
          catch { return "?"; }
        })
    );
    const lastMsg = c.last_message
      ? new Date(c.last_message.created_at).toLocaleTimeString()
      : "";
    const icon = c.type === "self" ? "⭐ " : c.type === "direct" ? "" : "👥 ";
    div.innerHTML = `<span>${icon}${escapeHtml(c.type === "self" ? "Избранное" : names.join(", ") || "Empty group")}</span>
      <span class="conv-time">${lastMsg}</span>`;
    div.onclick = () => openConversation(c.id);
    list.appendChild(div);
  }
  if (selectId) openConversation(selectId);
}

async function openConversation(id) {
  CURRENT_CONV = id;
  document.querySelectorAll(".conv-item").forEach(el => el.classList.remove("active"));
  const el = document.querySelector(`.conv-item[data-conv-id="${id}"]`);
  if (el) el.classList.add("active");

  hide("chat-placeholder");
  show("messages-list");
  show("send-area");

  const conv = await api("GET", `/api/conversations/${id}`);
  const names = await Promise.all(
    conv.member_ids
      .filter(mid => mid !== CURRENT_USER.id)
      .map(async mid => {
        try { const u = await api("GET", `/api/users/${mid}`); return u.display_name; }
        catch { return "?"; }
      })
  );
  $("chat-title").textContent = names.join(", ") || "Group chat";
  await loadMessages();
}

async function loadMessages() {
  if (!CURRENT_CONV) return;
  const data = await api("GET", `/api/conversations/${CURRENT_CONV}/messages?limit=100`);
  const list = $("messages-list");
  list.innerHTML = "";

  if (data.items.length === 0) {
    list.innerHTML = '<div style="text-align:center;color:#999;padding:40px;">No messages yet. Send one!</div>';
    return;
  }

  for (const msg of data.items.reverse()) {
    const div = document.createElement("div");
    const isMine = msg.sender_id === CURRENT_USER.id;
    div.className = `message ${isMine ? "mine" : "theirs"}`;

    let displayText = "🔒 Encrypted";
    try {
      const sender = await api("GET", `/api/users/${msg.sender_id}`);
      if (sender.public_key) {
        const decrypted = await CRYPTO.decryptMessage(msg.ciphertext, msg.iv, sender.public_key);
        displayText = decrypted;
      }
    } catch {}

    div.innerHTML = `<div class="msg-text">${escapeHtml(displayText)}</div>
      <div class="msg-time">${new Date(msg.created_at).toLocaleTimeString()}</div>`;

    if (msg.attachments && msg.attachments.length) {
      const attDiv = document.createElement("div");
      attDiv.className = "msg-attachments";
      for (const a of msg.attachments) {
        attDiv.innerHTML += `<span class="att-badge">📎 ${escapeHtml(a.filename)} (${a.mime_type})</span>`;
      }
      div.appendChild(attDiv);
    }
    list.appendChild(div);
  }
  list.scrollTop = list.scrollHeight;
}

// --- Send message ---
$("send-btn").onclick = sendMessage;
$("message-input").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } };

async function sendMessage() {
  const input = $("message-input");
  const text = input.value.trim();
  if (!text || !CURRENT_CONV) return;
  input.value = "";

  let ciphertext, iv, salt;
  try {
    const conv = await api("GET", `/api/conversations/${CURRENT_CONV}`);
    const otherIds = conv.member_ids.filter(id => id !== CURRENT_USER.id);
    const targetId = otherIds.length > 0 ? otherIds[0] : CURRENT_USER.id;
    const target = await api("GET", `/api/users/${targetId}`);
    if (target.public_key) {
      const encrypted = await CRYPTO.encryptMessage(text, target.public_key);
      ciphertext = encrypted.ciphertext;
      iv = encrypted.iv;
      salt = encrypted.salt;
    }
  } catch (e) { console.warn("Encryption failed, sending unencrypted:", e); }

  if (!ciphertext) {
    const encoded = new TextEncoder().encode(text);
    ciphertext = Array.from(encoded).map(b => b.toString(16).padStart(2, "0")).join("");
    iv = "00".repeat(12);
    salt = "00".repeat(16);
  }

  await api("POST", `/api/conversations/${CURRENT_CONV}/messages`, {
    ciphertext, iv, salt,
    ephemeral_key: "",
    key_id: "1",
    attachment_ids: [],
  });
  await loadMessages();
}

// --- Attachment upload ---
$("attach-btn").onclick = async () => {
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.onchange = async () => {
    const file = fileInput.files[0];
    if (!file || !CURRENT_CONV) return;
    try {
      const enc = await CRYPTO.encryptFile(file);
      const formData = new FormData();
      formData.append("file", enc.encryptedBlob, enc.filename);
      formData.append("content_hash", enc.plaintextHash);
      formData.append("iv", enc.iv);
      formData.append("salt", enc.key);
      const att = await api("POST", "/api/attachments", formData);

      const msgText = prompt("Message text (optional):", "") || "";
      let ciphertext = "", iv2 = "", salt2 = "";
      if (msgText) {
        try {
          const conv = await api("GET", `/api/conversations/${CURRENT_CONV}`);
          const otherIds = conv.member_ids.filter(id => id !== CURRENT_USER.id);
          const targetId = otherIds.length > 0 ? otherIds[0] : CURRENT_USER.id;
          const target = await api("GET", `/api/users/${targetId}`);
          if (target.public_key) {
            const enc2 = await CRYPTO.encryptMessage(msgText, target.public_key);
            ciphertext = enc2.ciphertext; iv2 = enc2.iv; salt2 = enc2.salt;
          }
        } catch (e) { console.warn("File msg encrypt failed:", e); }
      }

      await api("POST", `/api/conversations/${CURRENT_CONV}/messages`, {
        ciphertext: ciphertext || "0".repeat(32),
        iv: iv2 || "0".repeat(24),
        salt: salt2 || "0".repeat(32),
        ephemeral_key: "", key_id: "1",
        attachment_ids: [att.id],
      });
      await loadMessages();
    } catch (e) { alert("Upload failed: " + e.message); }
  };
  fileInput.click();
};

// --- Favorites (self chat) ---
$("favorites-btn").onclick = async () => {
  try {
    const conv = await api("POST", "/api/conversations", {
      type: "self", member_ids: [],
    });
    await loadConversations(conv.id);
  } catch (e) { alert("Failed to open Favorites: " + e.message); }
};

// --- Create group ---
$("create-group-btn").onclick = async () => {
  const names = prompt("Enter usernames to add (comma-separated):");
  if (!names) return;
  const parts = names.split(",").map(s => s.trim()).filter(Boolean);
  const ids = [];
  for (const n of parts) {
    const users = await api("GET", `/api/users?q=${encodeURIComponent(n)}`);
    if (users.length > 0) ids.push(users[0].id);
  }
  if (ids.length < 1) return alert("No users found");
  await api("POST", "/api/conversations", { type: "group", member_ids: ids });
  await loadConversations();
};

function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

// --- Init ---
if (TOKEN) loadApp().catch(() => logout());
