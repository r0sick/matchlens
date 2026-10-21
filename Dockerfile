# MatchLens container: live server + MCP server + AI newsroom in one process.
# Build:  docker build -t matchlens .
# Run:    docker run -p 8000:8000 --env-file .env matchlens   ->  http://localhost:8000
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY matchsim/ matchsim/
COPY matchlens/ matchlens/
COPY data/ data/

# Run as an unprivileged user
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
# One worker on purpose: live match sessions are held in memory and shared by every viewer of a match.
# The agents reach the MCP server inside the same container at http://127.0.0.1:8000/mcp/.
CMD ["uvicorn", "matchlens.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
