# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app.py auth.py config.py state.py mail_reader.py merger.py database.py migrate_json_to_sqlite.py ./
COPY routers/ ./routers/
COPY china_regions.json .
COPY templates/ ./templates/

# Copy frontend build output
COPY --from=frontend-builder /app/dist_vue ./dist_vue

# Data directories (volume mount points)
RUN mkdir -p data output uploads
VOLUME ["/app/data", "/app/output"]

ENV PYTHONUNBUFFERED=1
ENV SERVICE_TOKEN=lx-internal-service-token
ENV PASSWORD_SALT=excel-merger-salt

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
