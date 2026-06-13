# 💬 NexChat — Real-time Chat Application

> A production-grade WebSocket chat app built with **Python (FastAPI)**, **HTML/CSS/JS**, and clean architecture principles.  
> Built to demonstrate **1 year of backend experience** — beyond tutorial-level, built like a real product.

---

## 🚀 What Makes This Unique

| Feature | Most "Chat Apps" | NexChat |
|---|---|---|
| Architecture | Single file / Flask spaghetti | Layered: Router → Service → DB |
| Auth | Basic / no JWT | JWT Bearer tokens, BCrypt hashing |
| Real-time | Long polling or fake | True WebSocket with event bus |
| Messages | REST only | WS for sending, REST for history |
| Typing indicators | Missing | Yes — real-time, per-room |
| Message threading | Missing | Reply-to support |
| Soft delete | Hard delete | `is_deleted` flag, UI masked |
| Pagination | None | Cursor-based, load-more |
| Tests | None | 14 async tests, full coverage of auth/rooms/messages |
| Frontend | React boilerplate | Vanilla JS, clean MVC, zero deps |

---

## 🏗️ Architecture

```
nexchat/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # HTTP route handlers (thin layer)
│   │   │   ├── auth.py         # Register, Login, Me, Update profile
│   │   │   ├── users.py        # Search users, Get user by ID
│   │   │   ├── rooms.py        # Create direct/group, List rooms, Members
│   │   │   └── messages.py     # Get messages (paginated), Delete
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic Settings (env-driven config)
│   │   │   └── security.py     # JWT, BCrypt, Auth dependency
│   │   ├── db/
│   │   │   └── session.py      # Async SQLAlchemy engine + get_db()
│   │   ├── models/
│   │   │   └── models.py       # SQLAlchemy ORM models
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response schemas
│   │   ├── services/           # ← Business logic lives here
│   │   │   ├── user_service.py
│   │   │   ├── room_service.py
│   │   │   └── message_service.py
│   │   ├── websocket/
│   │   │   ├── manager.py      # ConnectionManager (room + user indexed)
│   │   │   └── router.py       # WS endpoint + event dispatcher
│   │   └── main.py             # FastAPI app, lifespan, CORS, routing
│   ├── tests/
│   │   └── test_app.py         # 14 async tests
│   └── requirements.txt
└── frontend/
    ├── static/
    │   ├── css/style.css       # Custom design system (CSS variables)
    │   └── js/app.js           # Vanilla JS: api client, state, WS, UI
    └── templates/
        └── index.html          # Single page app shell
```

### Design Patterns Used

- **Service Layer Pattern** — All business logic in `services/`, endpoints are thin
- **Repository abstraction** via SQLAlchemy sessions (swappable DB)
- **Dependency Injection** via FastAPI `Depends()` for DB sessions and auth
- **Observer pattern** — WebSocket manager broadcasts to all room subscribers
- **Singleton** — `ConnectionManager` is a module-level singleton
- **DTO Pattern** — Pydantic schemas separate API contracts from DB models

---

## ⚡ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Web Framework** | FastAPI | Async-first, auto OpenAPI, type-safe |
| **WebSockets** | FastAPI + Starlette | Native WS, no extra lib needed |
| **ORM** | SQLAlchemy 2.0 (async) | Modern async ORM, type-mapped models |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Zero config locally, swap via env var |
| **Auth** | JWT (python-jose) + BCrypt (passlib) | Industry standard, stateless |
| **Validation** | Pydantic v2 | Fast, type-safe request/response models |
| **Config** | pydantic-settings | 12-factor app, env-driven |
| **Testing** | pytest-asyncio + httpx | Full async test client |
| **Frontend** | Vanilla JS (no framework) | Zero build step, clean MVC pattern |

---

## 🔌 WebSocket Protocol

WebSocket URL: `ws://localhost:8000/ws/{room_id}?token=<JWT>`

### Client → Server Events

```json
{ "type": "message:send", "payload": { "content": "Hello!", "reply_to_id": null } }
{ "type": "message:delete", "payload": { "message_id": 42 } }
{ "type": "typing:start", "payload": {} }
{ "type": "typing:stop", "payload": {} }
{ "type": "ping", "payload": {} }
```

### Server → Client Events

```json
{ "type": "message:new", "payload": { ...MessageOut } }
{ "type": "message:deleted", "payload": { "message_id": 42, "room_id": 1 } }
{ "type": "typing:start", "payload": { "user_id": 5, "room_id": 1 } }
{ "type": "typing:stop", "payload": { "user_id": 5, "room_id": 1 } }
{ "type": "user_online", "payload": { "user_id": 5 } }
{ "type": "user_offline", "payload": { "user_id": 5 } }
{ "type": "pong", "payload": {} }
{ "type": "error", "payload": { "detail": "..." } }
```

---

## 🗄️ Data Models

```
User ─────────────────────────────────
  id, username (unique), email (unique)
  hashed_password, display_name
  avatar_color, bio, is_online, last_seen

Room ─────────────────────────────────
  id, name, room_type (direct|group)
  description, created_by → User

RoomMember (junction) ────────────────
  room_id → Room, user_id → User
  is_admin, joined_at, last_read_at    ← tracks unread count

Message ──────────────────────────────
  id, room_id → Room, sender_id → User
  content, status (sent|delivered|read)
  reply_to_id → Message (self-ref)
  is_deleted, created_at, updated_at
```

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo>
cd nexchat/backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` → You'll see the chat UI.

### 3. API Docs

```
http://localhost:8000/api/docs       ← Swagger UI
http://localhost:8000/api/redoc      ← ReDoc
```

### 4. Run Tests

```bash
pytest tests/ -v
```

---

## 🌍 Production Deployment

### Environment Variables (`.env`)

```env
SECRET_KEY=your-very-secret-key-here
DATABASE_URL=postgresql+asyncpg://user:password@localhost/nexchat
DEBUG=false
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALLOWED_ORIGINS=["https://yourdomain.com"]
```

### Switch to PostgreSQL

```bash
pip install asyncpg
# Set DATABASE_URL in .env — nothing else changes!
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t nexchat .
docker run -p 8000:8000 nexchat
```

---

## 📋 API Reference

### Auth
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login` | No | Get JWT token |
| GET | `/api/v1/auth/me` | ✅ | Get current user |
| PATCH | `/api/v1/auth/me` | ✅ | Update profile |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/users/search?q=` | ✅ | Search users |
| GET | `/api/v1/users/{id}` | ✅ | Get user profile |

### Rooms
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/rooms/` | ✅ | List my rooms |
| POST | `/api/v1/rooms/direct` | ✅ | Open direct chat |
| POST | `/api/v1/rooms/group` | ✅ | Create group |
| GET | `/api/v1/rooms/{id}/members` | ✅ | List members |
| POST | `/api/v1/rooms/{id}/read` | ✅ | Mark as read |

### Messages
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/rooms/{id}/messages` | ✅ | Paginated history |
| DELETE | `/api/v1/rooms/{id}/messages/{msgId}` | ✅ | Soft delete |

---



## 🛠️ What to Add Next (for even more ✨)

| Feature | Tech | Impact |
|---|---|---|
| PostgreSQL + Alembic migrations | asyncpg, Alembic | Production-ready DB |
| Redis pub/sub for multi-worker WS | redis-py async | Scale to multiple servers |
| Rate limiting | slowapi | Prevent abuse |
| File/image uploads | AWS S3 + boto3 | Real-world feature |
| Push notifications | FCM / APNs | Mobile ready |
| End-to-end encryption | libsodium | Security showcase |
| Docker Compose + Nginx | docker-compose | Deploy-ready |
| Prometheus metrics | prometheus-client | Observability |

---

