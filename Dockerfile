FROM python:3.12-slim-trixie

# 1. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Set working directory
WORKDIR /app

# 3. Environment variables
# Ensure the virtual environment is used by default
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# Bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1 



COPY ./pyproject.toml /app
COPY ./uv.lock /app

COPY ./shared /app/shared
COPY ./form_app /app/form_app
COPY ./senders /app/senders
COPY ./webhook /app/webhook
COPY ./scripts /app/scripts

# 6. Install the project itself (if your app is configured as a package)
# If your app is just scripts, this might be redundant, but it's safe for uv workspaces.
RUN uv sync --frozen

# 7. Expose ports
EXPOSE 5678

# 8. Default Command (Can be overridden)
# Since we added .venv to PATH, we don't strictly need 'uv run' prefix, 
# but keeping it is harmless and explicit.
CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:5678", "form_app.app:app"]
