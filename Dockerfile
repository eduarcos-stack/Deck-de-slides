# TRACE-LM — imagem do backend FastAPI (deploy Grau B).
# Contexto de build = raiz do repositório (precisa de backend/ e datasets/).
#   docker build -t tracelm-api .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro (camada cacheável).
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Código do backend + dataset sintético (para o demo-seed §82).
COPY backend/ /app/backend/
COPY datasets/ /app/datasets/

# Gera o CSV do Illicit Matrix no build (dados fictícios, determinísticos).
RUN python /app/datasets/illicit_matrix/generate.py || true

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

# Fly.io/Render injetam a porta via $PORT.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
