# ==============================================================
# DJI AG API - Dockerfile
# ==============================================================
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ src/
COPY .env .env

# Criar diretórios para persistência
RUN mkdir -p browser_profile downloads

# Expor porta da API
EXPOSE 8000

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Rodar a API
CMD ["python", "-m", "src.main"]
