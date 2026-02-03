# 🚀 Deploy em VPS - DJI AG API

## Requisitos Mínimos da VPS

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| RAM | 1 GB | 2 GB |
| CPU | 1 vCPU | 2 vCPU |
| Disco | 10 GB | 20 GB |
| SO | Ubuntu 20.04+ | Ubuntu 22.04 |

## Deploy Rápido

### 1. Instalar Docker

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt install docker-compose-plugin -y

# Relogar para aplicar grupo
exit
```

### 2. Clonar Repositório

```bash
git clone <seu-repositorio> djiag-api
cd djiag-api
```

### 3. Configurar Variáveis de Ambiente

```bash
# Copiar exemplo
cp .env.example .env

# Gerar API_KEY segura
API_KEY=$(openssl rand -hex 32)
echo "API_KEY=$API_KEY" >> .env

# Editar credenciais DJI
nano .env
```

**Variáveis obrigatórias:**
```env
DJI_USERNAME=seu_email@dji.com
DJI_PASSWORD=sua_senha
API_KEY=sua_chave_gerada_com_openssl
```

### 4. Iniciar API

```bash
# Produção
docker compose up -d --build

# Ver logs
docker compose logs -f
```

### 5. Verificar Status

```bash
# Health check (não requer X-API-KEY)
curl http://localhost:8000/api/health

# Testar endpoint protegido (requer X-API-KEY)
curl -H "X-API-KEY: sua_api_key" http://localhost:8000/api/auth/status

# Status do container
docker compose ps
```

## Comandos Úteis

```bash
# Parar
docker compose down

# Reiniciar
docker compose restart

# Ver logs em tempo real
docker compose logs -f api

# Acessar container
docker compose exec api bash

# Rebuild após mudanças
docker compose up -d --build
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
docker compose up -d --build
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
