# DJI AG API

API REST para automação de login e extração de dados de voo do DJI AG SmartFarm.

## 🔐 Segurança

A API usa **X-API-KEY** para autenticação. Todos os endpoints (exceto `/health`) requerem o header:

```
X-API-KEY: sua_chave_secreta
```

## ⚠️ Limitações do DJI

O DJI AG usa **WebAssembly** para gerar assinaturas de requisição, impossibilitando requisições HTTP diretas. Esta API usa **Playwright** para automação de browser com contexto persistente.

## 📋 Funcionalidades

- ✅ Login automático no DJI Account via Playwright
- ✅ Sessão persistente (mantém login entre execuções)
- ✅ Listagem de records de voo
- ✅ Detalhes de record individual
- ✅ Extração de dados GPS/telemetria
- ✅ Exportação GeoJSON
- ✅ Anti-detecção de automação
- ✅ Pronto para Docker/VPS

## 🛠️ Tecnologias

- **Python 3.10+**
- **FastAPI** - Framework web REST
- **Playwright** - Automação de browser
- **Pydantic** - Validação de dados
- **Uvicorn** - Servidor ASGI

## 📦 Instalação Local

### 1. Clone e configure o ambiente

```bash
git clone <seu-repositorio>
cd djiag-api

# Criar ambiente virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar browser do Playwright
playwright install chromium
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env`:

```env
# Credenciais DJI (obrigatório)
DJI_USERNAME=seu_email@exemplo.com
DJI_PASSWORD=sua_senha

# Segurança API (obrigatório)
API_KEY=sua_chave_secreta

# Configurações
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api
BROWSER_HEADLESS=false
```

### 3. Inicie o servidor

```bash
python -m src.main
```

## 🐳 Docker

```bash
# Copiar e configurar .env
cp .env.example .env
nano .env

# Iniciar
docker compose up -d --build

# Ver logs
docker compose logs -f
```

Veja [DEPLOY.md](DEPLOY.md) para instruções completas de deploy em VPS.

## 📡 Endpoints

| Método | Endpoint | Auth | Descrição |
|--------|----------|------|-----------|
| GET | `/api/health` | ❌ | Health check |
| POST | `/api/auth/login` | ✅ | Login no DJI AG |
| GET | `/api/auth/status` | ✅ | Status da autenticação |
| GET | `/api/records` | ✅ | Listar records |
| GET | `/api/records/{id}` | ✅ | Detalhes de um record |
| GET | `/api/records/{id}/flight-data` | ✅ | Dados de voo (GPS/telemetria) |
| GET | `/api/records/{id}/geojson` | ✅ | GeoJSON (resposta JSON) |
| GET | `/api/records/{id}/geojson/download` | ✅ | GeoJSON (download arquivo) |

**Swagger UI:** `http://localhost:8000/api/docs`

## 🚀 Exemplos de Uso

### cURL

```bash
# Health check (sem autenticação)
curl http://localhost:8000/api/health

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "X-API-KEY: sua_api_key"

# Listar records
curl http://localhost:8000/api/records \
  -H "X-API-KEY: sua_api_key"

# Obter GeoJSON
curl http://localhost:8000/api/records/ABC123/geojson \
  -H "X-API-KEY: sua_api_key"

# Download GeoJSON como arquivo
curl -O http://localhost:8000/api/records/ABC123/geojson/download \
  -H "X-API-KEY: sua_api_key"
```

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api"
HEADERS = {"X-API-KEY": "sua_api_key"}

# Login
response = requests.post(f"{BASE_URL}/auth/login", headers=HEADERS)
print(response.json())

# Listar records
response = requests.get(f"{BASE_URL}/records", headers=HEADERS)
records = response.json()

# Obter GeoJSON de um record
record_id = records["items"][0]["id"]
response = requests.get(f"{BASE_URL}/records/{record_id}/geojson", headers=HEADERS)
geojson = response.json()
```

### PowerShell

```powershell
$headers = @{ "X-API-KEY" = "sua_api_key" }

# Login
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method POST -Headers $headers

# Listar records
Invoke-RestMethod -Uri "http://localhost:8000/api/records" -Headers $headers
```

## 🏗️ Estrutura do Projeto

```
djiag-api/
├── src/
│   ├── application/          # Casos de uso
│   ├── domain/               # Entidades e interfaces
│   ├── infrastructure/       # Implementações (browser, config)
│   │   ├── config/
│   │   ├── repositories/
│   │   └── services/
│   ├── presentation/         # API (rotas, dependencies)
│   │   └── routes/
│   └── main.py
├── prototipo/                # Scripts de desenvolvimento
├── downloads/                # Downloads salvos
├── browser_profile/          # Sessão persistente do browser
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── DEPLOY.md
└── README.md
```

## ⚠️ Troubleshooting

### Login falha ou timeout
- Verifique credenciais no `.env`
- Se aparecer CAPTCHA, complete manualmente (browser abrirá)
- Configure `BROWSER_HEADLESS=false` para ver o browser

### GeoJSON trava o Swagger
- Use o endpoint `/geojson/download` para arquivos grandes
- O download retorna arquivo ao invés de renderizar no Swagger

### Erro no Docker
- Verifique se `shm_size: 2gb` está no docker-compose
- Playwright precisa de memória compartilhada

### Browser não abre
- Verifique se Playwright está instalado: `playwright install chromium`
- No Docker, sempre use `BROWSER_HEADLESS=true`

## 📄 Licença

Este projeto é para uso pessoal e educacional. Respeite os Termos de Serviço do DJI.
