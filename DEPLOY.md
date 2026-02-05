# 🚀 Deploy em VPS - DJI AG API

## Requisitos Mínimos da VPS

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| RAM | 1 GB | 2 GB |
| CPU | 1 vCPU | 2 vCPU |
| Disco | 10 GB | 20 GB |
| SO | Ubuntu 20.04+ | Ubuntu 22.04 |

## Deploy Rápido

### 1. Instalar Docker (se ainda não tiver)

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Instalar Docker Compose
sudo apt install docker-compose-plugin -y
```

### 2. Criar Pasta do Projeto

```bash
mkdir -p /opt/djiag-api
cd /opt/djiag-api
```

### 3. Criar docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  api:
    image: ghcr.io/cheri-hub/dji-python-api:latest
    container_name: djiag-api
    ports:
      - "8000:8000"
    environment:
      - DJI_USERNAME=${DJI_USERNAME}
      - DJI_PASSWORD=${DJI_PASSWORD}
      - API_KEY=${API_KEY}
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - BROWSER_HEADLESS=true
    volumes:
      - djiag-browser:/app/browser_profile
      - djiag-downloads:/app/downloads
    shm_size: 2gb
    restart: unless-stopped

volumes:
  djiag-browser:
  djiag-downloads:
EOF
```

### 4. Criar arquivo .env

```bash
cat > .env << EOF
DJI_USERNAME=seu_email@dji.com
DJI_PASSWORD=sua_senha
API_KEY=$(openssl rand -hex 32)
EOF

# Editar com suas credenciais reais
nano .env
```

### 5. Iniciar API

```bash
docker compose up -d

# Ver logs
docker compose logs -f
```

### 6. Verificar Status

```bash
# Health check (não requer X-API-KEY)
curl http://localhost:8000/api/health

# Testar endpoint protegido (requer X-API-KEY)
curl -H "X-API-KEY: sua_api_key" http://localhost:8000/api/auth/status

# Status do container
docker compose ps
```

**Estrutura final:**
```
/opt/djiag-api/
├── docker-compose.yml
└── .env
```

## Comandos Úteis

```bash
# Parar
docker compose down

# Reiniciar
docker compose restart

# Ver logs em tempo real
docker compose logs -f

# Acessar container
docker compose exec api bash

# Atualizar para nova versão
docker compose pull
docker compose up -d
```

## Configurar Nginx (Opcional - HTTPS)

### 1. Instalar Nginx e Certbot

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. Configurar Proxy Reverso

```bash
sudo nano /etc/nginx/sites-available/djiag-api
```

```nginx
server {
    server_name api.seudominio.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts para operações longas
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

### 3. Ativar e Gerar SSL

```bash
sudo ln -s /etc/nginx/sites-available/djiag-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Gerar certificado SSL
sudo certbot --nginx -d api.seudominio.com
```

## Monitoramento

### Verificar uso de recursos

```bash
# Uso de memória/CPU
docker stats djiag-api

# Espaço em disco dos volumes
docker system df -v
```

### Logs

```bash
# Últimas 100 linhas
docker compose logs --tail=100 api

# Logs com timestamp
docker compose logs -t api
```

## Troubleshooting

### Container não inicia

```bash
# Ver logs de erro
docker compose logs api

# Verificar se porta está em uso
sudo lsof -i :8000
```

### Erro de memória

Aumente o limite no `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
```

### Browser não funciona

```bash
# Verificar se Playwright está funcionando
docker compose exec api python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

### Limpar tudo e recomeçar

```bash
docker compose down -v
docker system prune -af
docker compose up -d
```

## Backup

```bash
# Backup dos volumes
docker run --rm -v djiag-api_djiag-browser:/data -v $(pwd):/backup alpine tar czf /backup/browser-backup.tar.gz /data
docker run --rm -v djiag-api_djiag-downloads:/data -v $(pwd):/backup alpine tar czf /backup/downloads-backup.tar.gz /data
```

## Endpoints Disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/health` | Health check |
| POST | `/api/auth/login` | Login (usa .env) |
| GET | `/api/auth/status` | Status autenticação |
| GET | `/api/records` | Listar records |
| GET | `/api/records/{id}` | Detalhes record |
| GET | `/api/records/{id}/geojson` | GeoJSON (JSON) |
| GET | `/api/records/{id}/geojson/download` | GeoJSON (arquivo) |

**Swagger UI:** `http://sua-vps:8000/api/docs`
