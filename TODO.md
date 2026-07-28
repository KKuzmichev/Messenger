# Messenger — Build Plan

## Stack
- **Backend:** Python 3.12+ / FastAPI
- **Database:** PostgreSQL (via asyncpg + SQLAlchemy async)
- **Migrations:** Alembic
- **Realtime:** WebSockets (FastAPI native)
- **Auth:** JWT (access + refresh tokens)
- **E2EE:** Client-side (Web Crypto API) — server never sees plaintext
- **Deployment:** Docker + Docker Compose

## E2EE Design (simplified)
- On registration: client generates ECDH keypair (X25519), stores private key in IndexedDB, uploads public key to server
- 1:1 chat: sender fetches recipient's public key, computes shared secret via ECDH, encrypts message with AES-GCM
- Group chat: symmetric group key shared encrypted under each member's public key
- Server stores only `ciphertext + iv + salt + ephemeral_public_key` — can never decrypt

## Attachment Dedup
- Client computes SHA-256 of **plaintext** file, encrypts client-side, sends `content_hash` + encrypted blob
- If `content_hash` already exists → server returns existing attachment ID (skips storage)
- Tradeoff: server learns which files are identical across users, but never sees plaintext

---

## Phases

### Phase 0 — Foundation
- [ ] Python project: pyproject.toml, ruff, mypy, pre-commit
- [ ] Dockerfile + docker-compose.yml (app, postgres)
- [ ] FastAPI app scaffold (lifespan, CORS, settings via pydantic-settings)
- [ ] Async SQLAlchemy engine + session factory
- [ ] Alembic setup + initial migration
- [ ] Health-check endpoint (GET /health)

### Phase 1 — Auth & Key Management
- [ ] POST /api/auth/register (username, password, public_key)
- [ ] POST /api/auth/login (returns JWT access + refresh tokens)
- [ ] POST /api/auth/refresh (refresh token rotation)
- [ ] Users DB schema: id, username, display_name, password_hash, public_key, created_at
- [ ] GET /api/users?q= (search by username)
- [ ] GET /api/users/{id} (profile)
- [ ] GET /api/users/{id}/key (public key)

### Phase 2 — Conversations
- [ ] Conversations schema: id, type (direct|group), created_at
- [ ] Participants schema: conversation_id, user_id, joined_at
- [ ] POST /api/conversations (create direct or group)
- [ ] GET /api/conversations (list mine with last message preview)
- [ ] GET /api/conversations/{id} (detail)
- [ ] POST /api/conversations/{id}/members (add members)
- [ ] DELETE /api/conversations/{id}/members (remove / leave)

### Phase 3 — Messaging (E2EE)
- [ ] Messages schema: id, conversation_id, sender_id, ciphertext, iv, salt, ephemeral_key, key_id, created_at
- [ ] MessageAttachments join table
- [ ] POST /api/conversations/{id}/messages (store encrypted blob + attachment_ids)
- [ ] GET /api/conversations/{id}/messages (cursor-paginated, encrypted blobs + attachment meta)
- [ ] Client-side E2EE stubs: keygen, encrypt, decrypt

### Phase 4 — Realtime
- [ ] WebSocket endpoint (WS /ws?token={jwt})
- [ ] Connection manager (track online users)
- [ ] Push new messages to conversation members
- [ ] Presence: online / offline / typing events
- [ ] Read receipts schema + POST /api/conversations/{id}/messages/{mid}/read

### Phase 5 — Attachments
- [ ] Attachments schema: id, content_hash (UNIQUE), filename, mime_type, size, ciphertext, iv, salt, uploader_id, created_at
- [ ] POST /api/attachments (multipart: upload encrypted file + metadata, dedup by hash)
- [ ] GET /api/attachments/{id} (download encrypted blob + decryption metadata)
- [ ] GET /api/attachments/{id}/meta (filename, mime_type, size, hash — no ciphertext)

### Phase 6 — Polish
- [ ] Rate limiting (slowapi)
- [ ] Input validation (Pydantic models)
- [ ] Consistent error response format
- [ ] CORS lockdown for production
- [ ] Logging (structlog)
- [ ] JWT rotation / refresh token rotation
- [ ] Indexes for performance (conversation_id + created_at on messages)

### Phase 7 — Testing
- [ ] Unit tests (auth, conversation logic)
- [ ] Integration tests (pytest + httpx + test DB)
- [ ] E2E flow: register → login → create conversation → send/receive messages

### Phase 8 — Deployment
- [ ] Docker Compose for production
- [ ] Health check + graceful shutdown
- [ ] Environment variable management (.env.example)
- [ ] DB backup strategy (pg_dump)

---

## API Routes Summary

```
Auth
  POST /api/auth/register            — create account + upload public key
  POST /api/auth/login               — returns JWT pair
  POST /api/auth/refresh             — refresh access token

Users
  GET  /api/users?q=                 — search users
  GET  /api/users/{id}               — user profile
  GET  /api/users/{id}/key           — user's public key

Conversations
  POST   /api/conversations          — create (body: members[], type)
  GET    /api/conversations          — list mine
  GET    /api/conversations/{id}     — detail
  POST   /api/conversations/{id}/members — add members
  DELETE /api/conversations/{id}/members — remove / leave

Messages
  GET  /api/conversations/{id}/messages       — cursor-paginated
  POST /api/conversations/{id}/messages       — store encrypted message
  POST /api/conversations/{id}/messages/{mid}/read — mark read

Attachments (standalone — dedup by content_hash)
  POST /api/attachments             — upload encrypted file (return id or existing id)
  GET  /api/attachments/{id}        — download encrypted blob + metadata
  GET  /api/attachments/{id}/meta   — metadata only

Realtime
  WS   /ws?token={jwt}              — receive messages, presence, typing events
```

## DB Schema

```sql
users (
  id UUID PK,
  username VARCHAR UNIQUE,
  display_name VARCHAR,
  password_hash VARCHAR,
  public_key BYTEA,       -- X25519 public key (raw)
  created_at TIMESTAMPTZ
)

conversations (
  id UUID PK,
  type VARCHAR,           -- 'direct' | 'group'
  created_at TIMESTAMPTZ
)

participants (
  conversation_id UUID FK,
  user_id UUID FK,
  joined_at TIMESTAMPTZ,
  PRIMARY KEY (conversation_id, user_id)
)

messages (
  id UUID PK,
  conversation_id UUID FK,
  sender_id UUID FK,
  ciphertext BYTEA,
  iv BYTEA,
  salt BYTEA,
  ephemeral_key BYTEA,     -- sender's ephemeral public key (for ECDH)
  key_id VARCHAR,           -- which of recipient's keys was used
  created_at TIMESTAMPTZ
)

attachments (
  id UUID PK,
  content_hash BYTEA UNIQUE,  -- SHA-256 of plaintext
  filename VARCHAR,
  mime_type VARCHAR,
  size BIGINT,
  ciphertext BYTEA,
  iv BYTEA,
  salt BYTEA,
  uploader_id UUID FK,
  created_at TIMESTAMPTZ
)

message_attachments (
  message_id UUID FK,
  attachment_id UUID FK,
  PRIMARY KEY (message_id, attachment_id)
)

read_receipts (
  user_id UUID FK,
  message_id UUID FK,
  read_at TIMESTAMPTZ,
  PRIMARY KEY (user_id, message_id)
)
```
