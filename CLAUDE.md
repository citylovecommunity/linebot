# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A dating/matchmaking service ("City Love") with two components:
1. **Flask web app** (`src/form_app/`) — member dashboard, admin panel, matching workflow
2. **FastAPI LINE bot** (`main.py`) — handles LINE webhook events (phone binding, postback actions)

Members sign up via Google Forms, get loaded into PostgreSQL, scored against each other, matched weekly, and communicate via an in-app chat + LINE notifications.

## Development Commands

```bash
# Install dependencies
uv sync

# Run Flask app locally
uv run flask --app src/form_app/app.py run --debug

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

## Environment Variables

Required in `.env` (loaded via pydantic-settings):
- `SECRET_KEY`, `TASK_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`
- `DEV_DB_URL` or `PROD_DB_URL` (PostgreSQL connection strings)
- `DEV_FORM_WEB_URL` or `PROD_FORM_WEB_URL`
- `APP_ENV` — `development` or `production` (controls which DB/URL is used)
- `LINE_TEST_USER_ID` — in dev mode, all LINE notifications are sent here

## Architecture

### Flask App (`src/form_app/`)

**Entry point:** `app.py` creates the Flask app, registers blueprints, and initializes the DB session factory.

**Blueprints:**
- `auth_bp` (`/`) — login/logout
- `dashboard_bp` (`/dashboard`) — member-facing: view matches, in-app chat, date proposals
- `admin_bp` (`/admin`) — admin-only: member CRUD, manual matching, send notifications
- `tasks_bp` (`/tasks`) — internal task endpoints (protected by `X-Task-Secret` header)
- `webhook_bp` — LINE webhook for the Flask app

**Database:** SQLAlchemy with a per-request session pattern. `get_db()` returns the session stored in Flask `g`. `init_db(app)` sets up the session factory at startup.

**Key models** (`models.py`):
- `Member` — core user; `user_info` JSONB column holds raw Google Form answers
- `Line_Info` — links phone number to LINE user_id (joined via phone_number, not FK)
- `Matching` — a pair of Members (subject/object), with status ACTIVE/COMPLETED/CANCELLED
- `Message` — in-app chat messages within a Matching
- `DateProposal` — date proposals within a Matching (PENDING/CONFIRMED/DELETED)
- `UserMatchScore` — precomputed compatibility scores between all cross-gender pairs

### Matching Pipeline

1. **Scoring** (`services/scoring.py`): `run_matching_score_optimized()` iterates all cross-gender eligible pairs, computes a `score` using `calculate_match_score()`, and bulk-upserts into `user_match_scores`. The `UserProfileAdapter` class wraps the raw `user_info` JSON for typed access to form answers.

2. **Matching** (`services/matching.py`): `generate_weekly_matches()` builds a NetworkX weighted graph and runs `max_weight_matching()`. Leftover unmatched nodes get a greedy second pass. `process_matches_bulk()` then bulk-inserts `Matching` rows.

3. **Eligibility** (`services/scoring.py:get_eligible_matching_pool`): Members must be active, non-test, have `user_info['會員介紹頁網址']`, and have a linked `Line_Info`.

4. **Trigger**: The `/tasks/match-all-users` endpoint runs scoring + matching in one call.

### Notifications (`services/messaging.py`)

`process_all_notifications()` collects unread in-app messages, pending date proposals, and confirmed date proposals, then pushes LINE messages. In dev mode (`APP_ENV=development`), all messages go to `LINE_TEST_USER_ID` instead of the real user.

### LINE Bot (`main.py`)

A standalone FastAPI app (separate from Flask) that handles:
- Text messages matching `綁定 09XXXXXXXX` → binds phone to LINE user_id in `line_info` table
- Postback `action=arrived` → replies with confirmation message

### Scripts (`scripts/`)

One-off data operations: ETL from Google Sheets (`etl_load_data.py`), backfills, migrations, manual matching runs. Run directly with `uv run python scripts/<script>.py`.

## Important Conventions

- **JSONB form data**: Member preferences and profile data live in `member.user_info` as raw Google Form answers in Chinese. `UserProfileAdapter` provides typed accessors for scoring logic.
- **`member.user_info` keys are in Chinese**: e.g., `'會員介紹頁網址'`, `'您的出生年月日'`, `'排約等級一'`.
- **subject/object pattern**: In `Matching`, `subject` is who was scored against `object` using `grading_metric`; `obj_grading_metric` is the reverse. `get_partner(user_id)` returns the other person.
- **Admin decorator**: `@admin_required` (in `decorators.py`) gates all `/admin` routes.
- **Task auth**: `/tasks/*` endpoints check `X-Task-Secret` header against `settings.TASK_SECRET`.
- The Flask app runs on port **5678**; the FastAPI LINE bot in `main.py` is a separate process.
