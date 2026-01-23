# ---------- Frontend build (Vite) ----------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ---------- Backend runtime (Django + Gunicorn) ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pipenv

COPY Pipfile Pipfile.lock /app/
RUN pipenv install --deploy --system

COPY . /app/

# ✅ Copy Vite build output from the frontend-build stage
RUN mkdir -p /app/frontend_dist
COPY --from=frontend-build /frontend/dist/ /app/frontend_dist/

COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000
CMD ["/start.sh"]