FROM python:3.12-slim

WORKDIR /app

# System deps: none beyond what asyncpg/yfinance/pandas need at build time —
# psycopg is not used, asyncpg ships its own C extension wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime and expects the app to bind to it — never
# hardcode a port. Shell form (not exec-array CMD) so ${PORT} actually
# expands; falls back to 8000 for `docker run` without $PORT set (e.g. this
# session's local `docker build`/`docker run` verification).
# --workers is intentionally omitted: this app owns in-process state
# (app.state.provider, the APScheduler job) that must not be duplicated
# across multiple worker processes — see main.py's lifespan.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
