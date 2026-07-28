# Messenger — Secure E2EE Messenger

Защищённый мессенджер со сквозным шифрованием (E2EE).  
**Backend:** Python / FastAPI / PostgreSQL  
**Client:** Vanilla JS + Web Crypto API (ECDH + AES-GCM)

---

## 🔧 Быстрый старт

### 1. PostgreSQL

Убедитесь что PostgreSQL запущен:

```bash
pg_isready
```

Создайте базу (если ещё не сделано):

```bash
psql -U postgres -h 127.0.0.1 -c "CREATE ROLE messenger WITH LOGIN PASSWORD 'messenger';"
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE messenger OWNER messenger;"
psql -U postgres -h 127.0.0.1 -d messenger -c "GRANT ALL ON SCHEMA public TO messenger;"
```

### 2. Установка

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### 3. Настройка

Скопируйте `.env.example` в `.env` (уже создан):

```bash
cp .env.example .env
```

Убедитесь что в `.env` указан правильный `DATABASE_URL`:

```
DATABASE_URL=postgresql+asyncpg://messenger:messenger@localhost:5432/messenger
SECRET_KEY=dev-secret-key-change-in-production
```

### 4. Миграции

```bash
.venv/bin/alembic upgrade head
```

### 5. Запуск

**Backend:**
```bash
.venv/bin/uvicorn app.main:app --reload
```

Откроется на `http://127.0.0.1:8000`

**Client:**
Откройте `client/index.html` в браузере (или через любой HTTP-сервер):

```bash
python3 -m http.server 8080 --directory client
```

И перейдите на `http://127.0.0.1:8080`

---

## 🧪 Тесты

```bash
.venv/bin/pytest tests/ -v
```

Для тестов нужна отдельная база `messenger_test`:

```bash
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE messenger_test OWNER messenger;"
psql -U postgres -h 127.0.0.1 -d messenger_test -c "GRANT ALL ON SCHEMA public TO messenger;"
```

---

## 🐳 Docker

```bash
docker compose up --build
```

---

## 📱 Как пользоваться (Client)

### Регистрация
1. Откройте `client/index.html`
2. Введите username, display name и пароль
3. Нажмите **Create Account**
4. Браузер сгенерирует ECDH-ключи — приватный ключ сохраняется в IndexedDB (никогда не покидает устройство)

### Поиск пользователей
- Введите имя в поле поиска (левая панель)
- Нажмите на пользователя — создастся direct-чат

### Отправка сообщений
- Выберите чат слева
- Напишите сообщение и нажмите Enter или Send
- Сообщение шифруется **на клиенте** AES-GCM + ECDH
- Сервер получает только зашифрованный blob

### Отправка файлов
- Нажмите 📎
- Выберите файл
- Файл шифруется на клиенте, вычисляется SHA-256 хеш
- Сервер проверяет хеш — если такой файл уже есть, он не загружается повторно (dedup)
- Одиннаковые файлы у разных пользователей хранятся 1 раз

### Создание группы
- Нажмите **+ New Group**
- Введите username участников через запятую

### Расшифровка сообщений
- При открытии чата клиент запрашивает публичный ключ собеседника
- Вычисляется общий секрет (ECDH) и расшифровывается сообщение
- Если расшифровка не удалась — показывается `🔒 Encrypted`

---

## 📚 API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/register` | Регистрация (включая public_key) |
| POST | `/api/auth/login` | Вход (JWT пара) |
| POST | `/api/auth/refresh` | Обновление токена |
| GET | `/api/users/me` | Текущий пользователь |
| GET | `/api/users?q=` | Поиск пользователей |
| GET | `/api/users/{id}` | Профиль |
| GET | `/api/users/{id}/key` | Публичный ключ |
| POST | `/api/conversations` | Создать чат |
| GET | `/api/conversations` | Список чатов |
| GET | `/api/conversations/{id}` | Детали чата |
| POST | `/api/conversations/{id}/messages` | Отправить сообщение |
| GET | `/api/conversations/{id}/messages` | Получить сообщения (cursor pagination) |
| POST | `/api/conversations/{id}/messages/{mid}/read` | Отметить прочитанным |
| POST | `/api/attachments` | Загрузить файл (dedup по hash) |
| GET | `/api/attachments/{id}` | Скачать файл |
| GET | `/api/attachments/{id}/meta` | Метаданные файла |
| WS | `/ws?token={jwt}` | WebSocket (presence, typing) |

---

## 🔐 Архитектура E2EE

```
Client A                          Server                        Client B
   |                                |                              |
   ├─ Generate ECDH keypair ────────┤                              |
   ├─ Upload public_key ────────────┼──────────────────────────────┤
   │                                |                              ├─ Generate ECDH keypair
   │                                |                              ├─ Upload public_key
   │                                |                              |
   ├─ Fetch B's public_key ────────┼──────────────────────────────┤
   ├─ Derive shared secret (ECDH)  |                              |
   ├─ Encrypt msg (AES-GCM) ───────┼─── store ciphertext ────────┤
   │                                |                              ├─ Fetch msg
   │                                |                              ├─ Fetch A's public_key
   │                                |                              ├─ Derive shared secret (ECDH)
   │                                |                              ├─ Decrypt msg (AES-GCM)
```

- Приватный ключ **никогда** не покидает браузер
- Сервер хранит только `ciphertext + iv + salt + ephemeral_key`
- Даже при компрометации сервера — сообщения не читаемы

---

## 🗄️ Схема БД

- `users` — id, username, display_name, password_hash, public_key
- `conversations` — id, type (direct|group)
- `participants` — связь пользователей с чатами
- `messages` — ciphertext, iv, salt, ephemeral_key
- `attachments` — ciphertext, content_hash (UNIQUE для dedup)
- `message_attachments` — связь сообщений с файлами
- `read_receipts` — отметки о прочтении
