FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the shared library first
COPY ./shared/ /tmp/shared

# 2. Copy the specific service files
COPY ./form_app /app
WORKDIR /app

# Install the shared folder as a package
RUN uv pip install /tmp/shared
RUN uv pip install -r requirements.txt

EXPOSE 5678

CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:5678", "app:app"]