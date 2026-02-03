# Guia de Testes - DJI AG API

Este documento explica como testar a API de automação do DJI AG.

## 📋 Pré-requisitos

1. Ambiente virtual ativado:
```powershell
cd c:\repo\djiag-api
.\venv\Scripts\Activate.ps1
```

2. Dependências instaladas:
```powershell
pip install -r requirements.txt
playwright install chromium
```

3. Arquivo `.env` configurado:
```env
DJI_USERNAME=seu_email@exemplo.com
DJI_PASSWORD=sua_senha
PORT=8000
DOWNLOAD_PATH=./downloads
HEADLESS=false
```

---

## 🧪 Teste 1: Script de Login Standalone

Testa o fluxo de login completo sem a API.

```powershell
python test_hybrid_login.py
```

### O que acontece:
1. Abre browser Chromium
2. Acessa `https://www.djiag.com/br/records`
3. Se redirecionar para login:
   - Marca checkbox "I have read..."
   - Clica "Log in with DJI account"
4. Preenche credenciais no `account.dji.com`
5. Aguarda redirecionamento
6. Navega para `/records`

### Resultado esperado:
```
✅ LOGIN BEM-SUCEDIDO! Redirecionado para /records
```

### Arquivos gerados:
- `records_page.png` - Screenshot da página de records
- `records_page.html` - HTML da página para análise

---

## 🧪 Teste 2: API REST

### Iniciar o servidor

```powershell
python run.py
```

O servidor inicia em `http://localhost:8000`

### Endpoints disponíveis

#### Swagger UI (documentação interativa)
```
http://localhost:8000/docs
```

#### Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

#### Status da Sessão
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/status"
```

#### Login
```powershell
# Usando credenciais do .env
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method POST

# Ou com credenciais específicas
$body = @{
    username = "email@exemplo.com"
    password = "senha"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method POST -Body $body -ContentType "application/json"
```

#### Listar Records
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/records"
```

#### Download de Record
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/records/RECORD_ID/download" -Method POST
```

#### Download de Todos
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/records/download-all" -Method POST
```

#### Logout
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/logout" -Method POST
```

---

## 🧪 Teste 3: Fluxo Completo via cURL

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login

# 2. Verificar status
curl http://localhost:8000/api/status

# 3. Listar records
curl http://localhost:8000/api/records

# 4. Logout
curl -X POST http://localhost:8000/api/auth/logout
```

---

## 🔍 Dicas de Debug

### Limpar perfil do browser
Se tiver problemas de sessão, remova o perfil:
```powershell
Remove-Item -Recurse -Force c:\repo\djiag-api\browser_profile
```

### Ver logs do servidor
Os logs são exibidos no terminal onde o servidor está rodando.

### CAPTCHA
Se aparecer CAPTCHA durante o login:
1. Complete manualmente no browser que abriu
2. O script aguarda até 60 segundos

### Modo Headless
Para rodar sem abrir browser (produção):
```env
HEADLESS=true
```

---

## ✅ Checklist de Testes

- [ ] Script `test_hybrid_login.py` funciona
- [ ] API inicia sem erros
- [ ] Endpoint `/health` responde
- [ ] Login via API funciona
- [ ] Redirecionamento para `/records` funciona
- [ ] Listagem de records retorna dados
- [ ] Download funciona

---

## 🐛 Problemas Comuns

| Problema | Solução |
|----------|---------|
| Browser fecha sozinho | Use `launch_persistent_context` (já implementado) |
| Login não completa | Verifique credenciais no `.env` |
| Redireciona para /mission | O código tenta redirecionar para /records automaticamente |
| Timeout | Aumente o timeout ou verifique conexão |
| Sessão expirada | Faça login novamente |
