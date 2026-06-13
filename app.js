// ── NexChat Frontend ─────────────────────────────────────────────
// Clean Architecture: API layer → State → UI rendering
// ────────────────────────────────────────────────────────────────

const API_BASE = "/api/v1";

// ── API Client ──────────────────────────────────────────────────
const api = {
  _token: null,

  setToken(token) { this._token = token; },
  clearToken() { this._token = null; },

  async request(method, path, body = null) {
    const headers = { "Content-Type": "application/json" };
    if (this._token) headers["Authorization"] = `Bearer ${this._token}`;
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || "Request failed");
    }
    return res.json();
  },

  get: (path) => api.request("GET", path),
  post: (path, body) => api.request("POST", path, body),
  patch: (path, body) => api.request("PATCH", path, body),
  delete: (path) => api.request("DELETE", path),
};

// ── App State ────────────────────────────────────────────────────
const state = {
  currentUser: null,
  rooms: [],
  activeRoom: null,
  messages: {},       // room_id → []
  pagination: {},     // room_id → { page, hasMore }
  typingUsers: {},    // room_id → Set of user_ids
  replyTo: null,
  ws: null,
};

// ── WebSocket Client ─────────────────────────────────────────────
class WsClient {
  constructor(roomId, token) {
    this.roomId = roomId;
    this._pingInterval = null;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.url = `${proto}://${location.host}/ws/${roomId}?token=${token}`;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log(`[WS] Connected to room ${this.roomId}`);
      this._pingInterval = setInterval(() => this._send("ping", {}), 25000);
    };

    this.ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      wsHandler.handle(event, this.roomId);
    };

    this.ws.onclose = () => {
      clearInterval(this._pingInterval);
      console.log(`[WS] Disconnected from room ${this.roomId}`);
    };

    this.ws.onerror = (err) => console.error("[WS] Error:", err);
  }

  send(type, payload) { this._send(type, payload); }

  _send(type, payload) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    }
  }

  disconnect() {
    clearInterval(this._pingInterval);
    this.ws?.close();
  }
}

// ── WebSocket Event Handler ──────────────────────────────────────
const wsHandler = {
  handle(event, roomId) {
    switch (event.type) {
      case "message:new":
        this._onNewMessage(event.payload, roomId);
        break;
      case "message:deleted":
        this._onMessageDeleted(event.payload, roomId);
        break;
      case "typing:start":
        this._onTyping(event.payload, roomId, true);
        break;
      case "typing:stop":
        this._onTyping(event.payload, roomId, false);
        break;
      case "user_online":
      case "user_offline":
        this._onPresence(event.payload, event.type === "user_online");
        break;
    }
  },

  _onNewMessage(msg, roomId) {
    if (!state.messages[roomId]) state.messages[roomId] = [];
    // Avoid duplicates
    if (!state.messages[roomId].find(m => m.id === msg.id)) {
      state.messages[roomId].push(msg);
    }

    // Update room preview
    const room = state.rooms.find(r => r.id === roomId);
    if (room) {
      room.last_message = msg;
      if (msg.sender_id !== state.currentUser.id && roomId !== state.activeRoom?.id) {
        room.unread_count = (room.unread_count || 0) + 1;
      }
    }

    if (roomId === state.activeRoom?.id) {
      ui.appendMessage(msg);
      ui.scrollToBottom();
      // Mark read
      api.post(`/rooms/${roomId}/read`).catch(() => {});
    }

    ui.renderRoomList();
  },

  _onMessageDeleted({ message_id, room_id }) {
    const msgs = state.messages[room_id];
    if (msgs) {
      const msg = msgs.find(m => m.id === message_id);
      if (msg) {
        msg.is_deleted = true;
        msg.content = "This message was deleted";
      }
    }
    if (room_id === state.activeRoom?.id) ui.renderMessages(room_id);
  },

  _onTyping({ user_id, room_id }, _, isTyping) {
    // fix: roomId passed separately
  },

  _onPresence({ user_id }, isOnline) {
    // Update rooms involving this user
    ui.renderRoomList();
  },
};

// Fix typing handler binding
wsHandler._onTyping = function ({ user_id, room_id }, _roomId, isTyping) {
  if (user_id === state.currentUser?.id) return;
  if (!state.typingUsers[room_id]) state.typingUsers[room_id] = new Set();
  if (isTyping) {
    state.typingUsers[room_id].add(user_id);
  } else {
    state.typingUsers[room_id].delete(user_id);
  }
  if (room_id === state.activeRoom?.id) ui.updateTypingIndicator(room_id);
};

// ── UI Renderer ──────────────────────────────────────────────────
const ui = {
  // ─ Auth ─────────────────────────────────────────────────────
  showError(msg) {
    const el = document.getElementById("auth-error");
    el.textContent = msg;
    el.style.display = "block";
  },
  clearError() { document.getElementById("auth-error").style.display = "none"; },

  showApp(user) {
    state.currentUser = user;
    document.getElementById("auth-screen").style.display = "none";
    document.getElementById("app-screen").classList.add("visible");
    document.getElementById("my-display").textContent = user.display_name;
    document.getElementById("my-avatar").textContent = user.display_name[0].toUpperCase();
    document.getElementById("my-avatar").style.background = user.avatar_color;
  },

  // ─ Room List ─────────────────────────────────────────────────
  renderRoomList() {
    const list = document.getElementById("room-list");
    const q = document.getElementById("sidebar-search").value.toLowerCase();
    const filtered = state.rooms.filter(r =>
      !q || (r.name || "").toLowerCase().includes(q)
    );

    list.innerHTML = filtered.length === 0
      ? `<div class="empty-state" style="padding:30px;font-size:13px;color:var(--text-muted)">No chats yet. Start one!</div>`
      : filtered.map(r => this._roomItemHTML(r)).join("");

    // Attach click handlers
    list.querySelectorAll(".room-item").forEach(el => {
      el.addEventListener("click", () => {
        const roomId = parseInt(el.dataset.roomId);
        const room = state.rooms.find(r => r.id === roomId);
        if (room) this.openRoom(room);
      });
    });
  },

  _roomItemHTML(room) {
    const isActive = state.activeRoom?.id === room.id;
    const initial = (room.name || "?")[0].toUpperCase();
    const color = this._colorFor(room.name || "");
    const preview = room.last_message
      ? (room.last_message.is_deleted ? "🚫 Deleted" : room.last_message.content)
      : "No messages yet";
    const time = room.last_message
      ? this._formatTime(room.last_message.created_at)
      : "";
    const badge = room.unread_count > 0
      ? `<span class="unread-badge">${room.unread_count}</span>` : "";
    const typeIcon = room.room_type === "group" ? "👥 " : "";
    return `
      <div class="room-item ${isActive ? "active" : ""}" data-room-id="${room.id}">
        <div class="room-avatar" style="background:${color}">
          ${typeIcon}${initial}
        </div>
        <div class="room-info">
          <div class="room-name-row">
            <span class="room-name">${this._esc(room.name || "Unknown")}</span>
            <span class="room-time">${time}</span>
          </div>
          <div class="room-preview-row">
            <span class="room-preview">${this._esc(preview.slice(0, 60))}</span>
            ${badge}
          </div>
        </div>
      </div>`;
  },

  async openRoom(room) {
    // Disconnect previous WS
    if (state.ws) { state.ws.disconnect(); state.ws = null; }

    state.activeRoom = room;
    state.replyTo = null;
    this._hideReplyBar();

    // Reset unread
    room.unread_count = 0;
    this.renderRoomList();

    // Render chat header
    document.getElementById("chat-header-name").textContent = room.name || "Chat";
    document.getElementById("chat-header-status").textContent =
      room.room_type === "group" ? `${room.member_count} members` : "Direct message";

    document.getElementById("empty-state").style.display = "none";
    document.getElementById("chat-main").style.display = "flex";

    // Load messages
    if (!state.messages[room.id]) {
      await this._loadMessages(room.id);
    } else {
      this.renderMessages(room.id);
    }

    // Connect WebSocket
    state.ws = new WsClient(room.id, api._token);
    state.ws.connect();

    // Mark read
    api.post(`/rooms/${room.id}/read`).catch(() => {});
    this.scrollToBottom();
  },

  async _loadMessages(roomId, page = 1) {
    const data = await api.get(`/rooms/${roomId}/messages?page=${page}&page_size=50`);
    if (page === 1) {
      state.messages[roomId] = data.messages;
    } else {
      state.messages[roomId] = [...data.messages, ...(state.messages[roomId] || [])];
    }
    state.pagination[roomId] = { page: data.page, hasMore: data.has_more };
    this.renderMessages(roomId);
  },

  renderMessages(roomId) {
    const container = document.getElementById("messages-container");
    container.innerHTML = "";

    const msgs = state.messages[roomId] || [];
    const pagination = state.pagination[roomId];

    if (pagination?.hasMore) {
      const btn = document.createElement("button");
      btn.className = "load-more-btn";
      btn.textContent = "Load older messages";
      btn.onclick = async () => {
        btn.textContent = "Loading...";
        btn.disabled = true;
        await this._loadMessages(roomId, (pagination.page || 1) + 1);
      };
      container.appendChild(btn);
    }

    let lastDate = null;
    let lastSenderId = null;

    msgs.forEach((msg, idx) => {
      const msgDate = new Date(msg.created_at).toLocaleDateString();
      if (msgDate !== lastDate) {
        container.appendChild(this._dateDivider(msg.created_at));
        lastDate = msgDate;
        lastSenderId = null;
      }

      const isOwn = msg.sender_id === state.currentUser.id;
      const isSameSender = lastSenderId === msg.sender_id;
      container.appendChild(this._messageBubble(msg, isOwn, isSameSender));
      lastSenderId = msg.sender_id;
    });
  },

  appendMessage(msg) {
    const container = document.getElementById("messages-container");
    const isOwn = msg.sender_id === state.currentUser.id;
    const msgs = state.messages[state.activeRoom?.id] || [];
    const prev = msgs[msgs.length - 2]; // last before this new one
    const isSameSender = prev && prev.sender_id === msg.sender_id;
    container.appendChild(this._messageBubble(msg, isOwn, isSameSender));
  },

  _dateDivider(dateStr) {
    const el = document.createElement("div");
    el.className = "date-divider";
    const d = new Date(dateStr);
    const today = new Date();
    const isToday = d.toDateString() === today.toDateString();
    el.innerHTML = `<span>${isToday ? "Today" : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>`;
    return el;
  },

  _messageBubble(msg, isOwn, isSameSender) {
    const group = document.createElement("div");
    group.className = `message-group ${isOwn ? "own" : ""}`;
    group.dataset.msgId = msg.id;

    const avatarEl = document.createElement("div");
    avatarEl.className = `msg-avatar ${isSameSender ? "hidden" : ""}`;
    avatarEl.style.background = msg.sender_avatar_color || "#7c6af7";
    avatarEl.textContent = msg.sender_display_name?.[0]?.toUpperCase() || "?";

    const bubblesEl = document.createElement("div");
    bubblesEl.className = "msg-bubbles";

    if (!isSameSender && !isOwn) {
      const meta = document.createElement("div");
      meta.className = "bubble-meta";
      meta.innerHTML = `<span class="sender-name">${this._esc(msg.sender_display_name)}</span>`;
      bubblesEl.appendChild(meta);
    }

    const bubble = document.createElement("div");
    bubble.className = `bubble ${isOwn ? "mine" : "theirs"} ${msg.is_deleted ? "deleted" : ""}`;

    if (msg.reply_to_id) {
      const replyBar = document.createElement("div");
      replyBar.className = "reply-preview";
      replyBar.textContent = "↩ Replying to a message";
      bubble.appendChild(replyBar);
    }

    const contentEl = document.createElement("span");
    contentEl.textContent = msg.content;
    bubble.appendChild(contentEl);

    const timeMeta = document.createElement("div");
    timeMeta.className = "bubble-meta";
    timeMeta.innerHTML = `<span class="msg-time">${this._formatTime(msg.created_at)}</span>`;

    if (!msg.is_deleted) {
      // Right-click to reply
      bubble.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        this._setReply(msg);
      });
      // Double-click to reply (mobile friendly)
      bubble.addEventListener("dblclick", () => this._setReply(msg));
    }

    bubblesEl.appendChild(bubble);
    bubblesEl.appendChild(timeMeta);
    group.appendChild(avatarEl);
    group.appendChild(bubblesEl);
    return group;
  },

  _setReply(msg) {
    state.replyTo = msg;
    document.getElementById("reply-bar").classList.add("visible");
    document.getElementById("reply-preview-text").innerHTML =
      `<strong>${this._esc(msg.sender_display_name)}</strong>: ${this._esc(msg.content.slice(0, 60))}`;
    document.getElementById("message-input").focus();
  },

  _hideReplyBar() {
    state.replyTo = null;
    document.getElementById("reply-bar").classList.remove("visible");
  },

  scrollToBottom() {
    const c = document.getElementById("messages-container");
    c.scrollTop = c.scrollHeight;
  },

  updateTypingIndicator(roomId) {
    const typing = state.typingUsers[roomId] || new Set();
    const el = document.getElementById("typing-indicator");
    if (typing.size > 0) {
      el.classList.add("visible");
      el.querySelector(".typing-text").textContent =
        typing.size === 1 ? "Someone is typing..." : `${typing.size} people are typing...`;
    } else {
      el.classList.remove("visible");
    }
  },

  // ─ Helpers ────────────────────────────────────────────────────
  _esc(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  },

  _formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  },

  _colorFor(name) {
    const colors = ["#7c6af7","#3fb950","#d29922","#f85149","#58a6ff","#bc8cff","#ff7b72","#79c0ff"];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return colors[Math.abs(h) % colors.length];
  },
};

// ── Controller ────────────────────────────────────────────────────
const app = {
  async init() {
    // Check stored session
    const token = localStorage.getItem("nexchat_token");
    const userStr = localStorage.getItem("nexchat_user");
    if (token && userStr) {
      api.setToken(token);
      ui.showApp(JSON.parse(userStr));
      await this.loadRooms();
    }
    this._bindEvents();
  },

  _bindEvents() {
    // Auth tabs
    document.querySelectorAll(".auth-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById("login-form").style.display =
          tab.dataset.tab === "login" ? "block" : "none";
        document.getElementById("register-form").style.display =
          tab.dataset.tab === "register" ? "block" : "none";
        ui.clearError();
      });
    });

    // Login
    document.getElementById("login-btn").addEventListener("click", () => this.login());
    document.getElementById("login-password").addEventListener("keydown", e => {
      if (e.key === "Enter") this.login();
    });

    // Register
    document.getElementById("register-btn").addEventListener("click", () => this.register());

    // Sidebar search
    document.getElementById("sidebar-search").addEventListener("input", () => ui.renderRoomList());

    // New chat button
    document.getElementById("new-chat-btn").addEventListener("click", () => {
      document.getElementById("user-search-modal").classList.add("visible");
      document.getElementById("user-search-input").focus();
    });

    // New group button
    document.getElementById("new-group-btn").addEventListener("click", () => {
      document.getElementById("group-modal").classList.add("visible");
    });

    // Close modals
    document.querySelectorAll(".modal-close").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("visible"));
      });
    });

    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.remove("visible");
      });
    });

    // User search
    document.getElementById("user-search-input").addEventListener("input",
      this._debounce(() => this.searchUsers(), 300)
    );

    // Send message
    document.getElementById("send-btn").addEventListener("click", () => this.sendMessage());
    document.getElementById("message-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Typing indicator
    let typingTimeout;
    document.getElementById("message-input").addEventListener("input", () => {
      if (state.ws) {
        state.ws.send("typing:start", {});
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => state.ws?.send("typing:stop", {}), 2000);
      }
    });

    // Reply cancel
    document.getElementById("reply-cancel").addEventListener("click", () => ui._hideReplyBar());

    // Create group
    document.getElementById("create-group-btn").addEventListener("click", () => this.createGroup());

    // Logout
    document.getElementById("logout-btn").addEventListener("click", () => this.logout());
  },

  async login() {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    if (!username || !password) return ui.showError("Fill in all fields");
    ui.clearError();
    document.getElementById("login-btn").disabled = true;
    try {
      const data = await api.post("/auth/login", { username, password });
      api.setToken(data.access_token);
      localStorage.setItem("nexchat_token", data.access_token);
      localStorage.setItem("nexchat_user", JSON.stringify(data.user));
      ui.showApp(data.user);
      await this.loadRooms();
    } catch (e) {
      ui.showError(e.message);
    } finally {
      document.getElementById("login-btn").disabled = false;
    }
  },

  async register() {
    const username = document.getElementById("reg-username").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const display_name = document.getElementById("reg-display").value.trim();
    const password = document.getElementById("reg-password").value;
    if (!username || !email || !password || !display_name) return ui.showError("Fill in all fields");
    ui.clearError();
    document.getElementById("register-btn").disabled = true;
    try {
      const data = await api.post("/auth/register", { username, email, password, display_name });
      api.setToken(data.access_token);
      localStorage.setItem("nexchat_token", data.access_token);
      localStorage.setItem("nexchat_user", JSON.stringify(data.user));
      ui.showApp(data.user);
      await this.loadRooms();
    } catch (e) {
      ui.showError(e.message);
    } finally {
      document.getElementById("register-btn").disabled = false;
    }
  },

  async loadRooms() {
    try {
      state.rooms = await api.get("/rooms/");
      ui.renderRoomList();
    } catch (e) {
      console.error("Failed to load rooms", e);
    }
  },

  async searchUsers() {
    const q = document.getElementById("user-search-input").value.trim();
    const results = document.getElementById("user-search-results");
    if (!q) { results.innerHTML = ""; return; }
    try {
      const users = await api.get(`/users/search?q=${encodeURIComponent(q)}`);
      results.innerHTML = users.length === 0
        ? `<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:13px">No users found</div>`
        : users.map(u => `
            <div class="user-result-item" data-uid="${u.id}">
              <div class="room-avatar" style="background:${u.avatar_color};width:38px;height:38px;font-size:15px">${u.display_name[0].toUpperCase()}</div>
              <div class="user-result-info">
                <div class="name">${ui._esc(u.display_name)}</div>
                <div class="username">@${ui._esc(u.username)}</div>
              </div>
            </div>`).join("");

      results.querySelectorAll(".user-result-item").forEach(el => {
        el.addEventListener("click", async () => {
          const uid = parseInt(el.dataset.uid);
          document.getElementById("user-search-modal").classList.remove("visible");
          await this.startDirect(uid);
        });
      });
    } catch (e) {
      console.error(e);
    }
  },

  async startDirect(targetId) {
    try {
      const room = await api.post("/rooms/direct", { target_user_id: targetId });
      await this.loadRooms();
      const roomObj = state.rooms.find(r => r.id === room.id);
      if (roomObj) ui.openRoom(roomObj);
    } catch (e) {
      console.error(e);
    }
  },

  async createGroup() {
    const name = document.getElementById("group-name-input").value.trim();
    if (!name) return;
    // For simplicity, create group with just yourself (others can be added later)
    try {
      const room = await api.post("/rooms/group", { name, member_ids: [] });
      document.getElementById("group-modal").classList.remove("visible");
      document.getElementById("group-name-input").value = "";
      await this.loadRooms();
      const roomObj = state.rooms.find(r => r.id === room.id);
      if (roomObj) ui.openRoom(roomObj);
    } catch (e) {
      console.error(e);
    }
  },

  sendMessage() {
    const input = document.getElementById("message-input");
    const content = input.value.trim();
    if (!content || !state.ws) return;

    state.ws.send("message:send", {
      content,
      reply_to_id: state.replyTo?.id || null,
    });

    input.value = "";
    ui._hideReplyBar();
    state.ws.send("typing:stop", {});
  },

  logout() {
    if (state.ws) { state.ws.disconnect(); state.ws = null; }
    api.clearToken();
    localStorage.removeItem("nexchat_token");
    localStorage.removeItem("nexchat_user");
    state.currentUser = null;
    state.rooms = [];
    state.activeRoom = null;
    state.messages = {};
    document.getElementById("app-screen").classList.remove("visible");
    document.getElementById("auth-screen").style.display = "flex";
  },

  _debounce(fn, delay) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
  },
};

document.addEventListener("DOMContentLoaded", () => app.init());
