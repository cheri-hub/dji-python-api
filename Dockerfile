# ==============================================================
# DJI AG API - Dockerfile
# ==============================================================
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Instalar curl para healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ src/

# Criar diretórios para persistência com permissões corretas
RUN mkdir -p browser_profile downloads && \
    chmod -R 777 browser_profile downloads

# Expor porta da API
EXPOSE 8000

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BROWSER_HEADLESS=true

# Aumentar memória compartilhada para Chromium (evita crash)
# Nota: Em docker-compose, usar shm_size: 2gb ou tmpfs

# Healthcheck (start-period maior para inicialização do Playwright)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Rodar a API (produção - sem reload)
CMD ["python", "-m", "uvicorn", "src.presentation.api:app", "--host", "0.0.0.0", "--port", "8000"]
