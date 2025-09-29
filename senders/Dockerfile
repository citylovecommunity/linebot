# Use official Python image (uv supports Python ≥3.8)
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app

# Set working directory
WORKDIR /app

RUN uv sync --locked
