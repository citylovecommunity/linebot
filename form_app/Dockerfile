FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy the rest of the application
COPY . /app

RUN uv sync --locked


# Expose the port uvicorn will run on
EXPOSE 5678

# Command to run the app
CMD ["uv", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:5678", "app:app"]