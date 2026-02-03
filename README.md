# DJI AG API

API REST para automação de login e download de records do DJI AG (Agriculture).

## ⚠️ Importante: Limitações de Segurança do DJI

A API do DJI AG usa **WebAssembly** para gerar assinaturas de requisição, o que torna impossível
fazer requisições HTTP diretas sem usar um browser. Por isso, esta API usa **Playwright** para
automação de browser com contexto persistente.

## 🔐 Fluxo de Login Homologado

O processo de login segue o fluxo:

1. **ETAPA 1**: Acessar `https://www.djiag.com/br/records`
2. **ETAPA 2**: Se redirecionar para login:
   - Clicar checkbox "I have read..."
   - Clicar botão "Log in with DJI account"
3. **ETAPA 3**: Preencher credenciais no `account.dji.com`:
   - Email
   - Senha
   - Clicar Login
4. **ETAPA 4**: Verificar redirecionamento para página autenticada

O browser usa um **perfil persistente** (`browser_profile/`) que mantém a sessão entre execuções.

## 📋 Funcionalidades

- ✅ Login automático no DJI Account via Playwright
- ✅ Sessão persistente (mantém login entre execuções)
- ✅ Listagem de records do TaskHistory
- ✅ Download de record individual
- ✅ Download de todos os records
- ✅ Anti-detecção de automação

## 🛠️ Tecnologias

- **Python 3.10+**
- **FastAPI** - Framework web para API REST
- **Playwright** - Automação de browser com contexto persistente
- **httpx** - Cliente HTTP async
- **Pydantic** - Validação de dados
- **Uvicorn** - Servidor ASGI

## 📦 Instalação

### Pré-requisitos

- Python 3.10+ instalado
- pip

### Passos

1. Clone o repositório:
```bash
git clone <seu-repositorio>
cd djiag-api
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Instale os browsers do Playwright:
```bash
playwright install chromium
```

5. Configure as variáveis de ambiente:
```bash
cp .env.example .env
```

6. Edite o arquivo `.env` com suas credenciais:
```env
DJI_USERNAME=seu_email@exemplo.com
DJI_PASSWORD=sua_senha
PORT=8000
DOWNLOAD_PATH=./downloads
HEADLESS=false
```

7. Inicie o servidor:
```bash
python run.py
```

## 🚀 Uso da API

### Base URL
```
http://localhost:8000
```

### Documentação Interativa (Swagger)
```
http://localhost:8000/docs
```

---

## 📡 Endpoints

### Health Check
```http
GET /health
```
Retorna o status do servidor.

---

### Status da Sessão
```http
GET /api/status?use_proxy=true
```
Retorna o status da sessão atual.

---

### Login (Recomendado: Browser Proxy)
```http
POST /api/auth/login?use_proxy=true
```

Quando você faz login com `use_proxy=true`:
1. Um browser Chrome será aberto
2. Você deve fazer login manualmente no DJI Account
3. Após o login, a API detecta automaticamente e começa a funcionar

**Body (opcional):**
```json
{
  "username": "seu_email@exemplo.com",
  "password": "sua_senha"
}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Login realizado com sucesso",
  "session_status": {
    "authenticated": true,
    "username": "user@example.com"
  }
}
```

---

### Listar Records
```http
GET /api/records?use_proxy=true
```

Retorna a lista de flight records do TaskHistory.

**Resposta:**
```json
{
  "success": true,
  "message": "Encontrados 5 records",
  "records": [
    {
      "id": "12345",
      "name": "Flight Record 1",
      "date": "2025-01-27",
      "status": "completed"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 10
}
```

---

### Download de Record Individual
```http
POST /api/records/{record_id}/download?use_proxy=true
```

Inicia o download de um record específico.

---

### Download de Todos os Records
```http
POST /api/records/download-all?use_proxy=true
```

Usa o botão "Download All" do site para baixar todos os records.

---

### Set Token Manualmente (Avançado)
```http
POST /api/auth/set-token
Content-Type: application/json
```

Para casos onde você capturou o token manualmente do DevTools:

```json
{
  "auth_token": "seu_jwt_token_aqui",
  "device_id": "seu_device_id"
}
```

---

### Logout
```http
POST /api/auth/logout?use_proxy=true
```

Encerra a sessão e fecha o browser.

---

## 🔧 Script de Captura de Token

Se preferir capturar o token manualmente, use o script auxiliar:

```bash
python capture_token.py
```

Este script:
1. Abre o Chrome na página de login do DJI AG
2. Aguarda você fazer login manualmente
3. Captura o token de autenticação
4. Salva em `captured_credentials.json`

---

## 📝 Exemplos de Uso

### PowerShell

```powershell
# Login (abre browser para login manual)
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login?use_proxy=true" -Method POST

# Listar records
Invoke-RestMethod -Uri "http://localhost:8000/api/records?use_proxy=true" -Method GET

# Download all
Invoke-RestMethod -Uri "http://localhost:8000/api/records/download-all?use_proxy=true" -Method POST

# Logout
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/logout?use_proxy=true" -Method POST
```

### cURL

```bash
# Login
curl -X POST "http://localhost:8000/api/auth/login?use_proxy=true"

# Listar records
curl "http://localhost:8000/api/records?use_proxy=true"

# Download all
curl -X POST "http://localhost:8000/api/records/download-all?use_proxy=true"
```

### Python

```python
import requests

BASE_URL = "http://localhost:8000"

# Login (abre browser para login manual)
response = requests.post(f"{BASE_URL}/api/auth/login?use_proxy=true")
print(response.json())

# Listar records
response = requests.get(f"{BASE_URL}/api/records?use_proxy=true")
records = response.json()
print(f"Total de records: {records['total']}")

# Download de um record específico
record_id = records['records'][0]['id']
response = requests.post(f"{BASE_URL}/api/records/{record_id}/download?use_proxy=true")
print(response.json())
```

---

## 🏗️ Estrutura do Projeto

```
djiag-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── routes.py            # Rotas da API
│   ├── models.py            # Modelos Pydantic
│   ├── config.py            # Configurações
│   └── services/
│       ├── __init__.py
│       ├── djiag_service.py         # Serviço HTTP (limitado)
│       └── djiag_proxy_service.py   # Serviço Browser Proxy (completo)
├── capture_token.py         # Script para captura manual de token
├── requirements.txt
├── run.py
├── .env.example
└── README.md
```

---

## 🔒 Segurança

- As credenciais são armazenadas apenas em memória durante a execução
- O arquivo `.env` não deve ser commitado (está no `.gitignore`)
- O token JWT expira após um tempo (gerenciado pelo DJI)
- O browser proxy mantém a sessão enquanto o servidor estiver rodando

---

## ⚠️ Troubleshooting

### "Login failed" ou timeout
- Certifique-se de que o Chrome está instalado
- Verifique se não há CAPTCHA ou verificação de 2FA
- Faça o login manualmente quando o browser abrir

### "Signature error" ou "Forbidden"
- Use `use_proxy=true` para todas as requisições
- O serviço HTTP direto não consegue gerar assinaturas válidas

### Browser não abre
- Verifique se o Chrome está instalado
- Configure `HEADLESS=false` no `.env` para ver o browser

### ChromeDriver error
- O webdriver-manager baixa automaticamente a versão correta
- Se falhar, atualize o Chrome para a versão mais recente

---

## 📄 Licença

Este projeto é para uso pessoal e educacional. Respeite os Termos de Serviço do DJI.
