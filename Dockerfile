FROM python:3.12-slim-trixie

# 1. Install uv (pinned for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

# 2. Set working directory
WORKDIR /app

# 3. Environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1

# 4. Install dependencies first (cached layer — only re-runs when lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 5. Copy application code and install the project
COPY . /app
RUN uv sync --frozen

# 6. Expose port
EXPOSE 5678

CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:5678", "--timeout", "120", "form_app.app:app"]
