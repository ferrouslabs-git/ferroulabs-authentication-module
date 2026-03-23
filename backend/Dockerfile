FROM python:3.13-slim

WORKDIR /app

# Install only the system libs needed by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run Alembic migrations then start Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
