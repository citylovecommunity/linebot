# City Love — Matchmaking Service

A dating/matchmaking service with a Flask web app and a FastAPI LINE bot.

## Quick Start

```bash
# Install dependencies
uv sync

# Run Flask app locally
uv run flask --app src/form_app/app.py run --debug
```

## Developer Setup

New developers need a few one-time steps beyond the standard install.

### 1. Environment variables

Copy `.env.example` to `.env` (or create `.env`) and fill in:

```
SECRET_KEY=...
TASK_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
DEV_DB_URL=postgresql://...
DEV_FORM_WEB_URL=http://localhost:5678
APP_ENV=development
LINE_TEST_USER_ID=<your LINE user ID>   # all LINE pushes go here in dev mode
DEV_ADMIN_ID=<your member ID>           # used by /auto-login-admin to log in as you
```

### 2. Run migrations

```bash
uv run alembic upgrade head
```

### 3. Bootstrap your developer account

Your account must exist in the `member` table with `is_developer=True`. The
first time there is no UI to do this, so run it once from the shell:

```bash
uv run python - <<'EOF'
from form_app.database import SessionLocal
from form_app.models import Member
db = SessionLocal()
me = db.query(Member).filter_by(phone_number='09XXXXXXXX').first()
me.is_developer = True
me.is_test = True    # excludes you from the matching pool
me.is_active = False # excludes you from member stats
db.commit()
print('Done:', me.name)
EOF
```

After that, mark `DEV_ADMIN_ID=<your member id>` in `.env` so that
`/auto-login-admin` always logs in as you.

Access the backdoor login via:

```
/auto-login-admin?token=<TASK_SECRET>
```

### 4. Developer-only features

Once logged in as a developer, the admin panel exposes extra capabilities
that regular admin accounts cannot access:

| Feature | How to use |
|---|---|
| **Chat UI preview** | `/dev/chat-preview?step=1` — renders the real chat page with fake data. Use `?step=1/2/3/4` to switch between all UI states (matched / pending proposal / confirmed / cancelled) |
| **Reset a user's password** | Admin panel → edit any member → "重設密碼" section at the bottom |
| **Grant developer role** | Admin panel → edit any member → "Is Developer" checkbox (only visible to developers) |

## Role Reference

| Role | `is_admin` | `is_developer` | Notes |
|---|---|---|---|
| Regular member | — | — | Dashboard only |
| Admin | ✓ | — | Admin panel: member CRUD, matchings, notifications |
| Developer | ✓ (implied) | ✓ | All admin features + impersonate + password reset + grant roles |

## Commands

```bash
# Run with gunicorn (production-like)
uv run gunicorn -w 1 -b 0.0.0.0:5678 form_app.app:app

# Run Docker
docker compose up --build

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Run a script manually (e.g., backfill, ETL)
uv run python scripts/etl_load_data.py
```
