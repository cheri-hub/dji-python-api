# 📋 Resumo do Projeto DJI AG API

## 🎯 Objetivo
Automação completa do DJI AG SmartFarm para download e processamento de registros de voo de drones agrícolas (T40, T50, etc).

---

## 🛠️ Tecnologia
- **Python 3.13** com venv
- **Playwright** - Automação de browser (necessário por causa do WebAssembly do DJI)
- **Sessão persistente** em `browser_profile/` (mantém login entre execuções)
- **Protobuf** - Decodificação de dados binários de voo

---

## 📂 Scripts Principais

| Script | Função |
|--------|--------|
| `test_hybrid_login.py` | Login automático com credenciais do `.env` |
| `list_records.py` | Lista todos os records (com paginação automática) |
| `download_all_records_v3.py` | Baixa todos os records com metadados + telemetria |
| `generate_geojson.py` | Gera GeoJSON com telemetria completa |
| `decode_flight_data.py` | Decodifica arquivos protobuf binários |

---

## ✅ Funcionalidades Implementadas

### 1. Login Automático (`test_hybrid_login.py`)
- Preenche email/senha do `.env`
- Clica nos botões corretamente
- Mantém sessão persistente em `browser_profile/`

### 2. Listar Records (`list_records.py`)
- Navega por **todas as páginas** (paginação automática)
- Extrai: ID, Data/Hora, Duração, Modo, Área, Payload, Piloto, Drone
- Salva em `downloads/records_list.json`

### 3. Download de Records (`download_all_records_v3.py`)
- Captura APIs de metadados JSON
- Baixa arquivos protobuf binários de rota
- Decodifica e extrai coordenadas GPS + telemetria
- Gera GeoJSON com pontos individuais e propriedades
- Filtra pares de coordenadas sincronizados (lat/lon válidos)

### 4. GeoJSON Enriquecido
- **LineString** com rota completa
- **Pontos individuais** com propriedades de telemetria
- Metadados da API incluídos no cabeçalho

---

## 📊 Dados Disponíveis

### Da API de Metadados (`/api/web/v1/flight_records/{id}`)

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `id` | Flight Record Number | `531405271` |
| `radar_height` | Altura de voo | `3.0` (metros) |
| `start_timestamp` | Início do voo (Unix) | `1738084265` |
| `end_timestamp` | Fim do voo (Unix) | `1738084812` |
| `create_date` | Data | `20260129` |
| `location` | Endereço completo | `"Bocaiúva do Sul, PR, Brazil"` |
| `drone_type` | Tipo do drone | `"T40"` |
| `serial_number` | Número de série | `"R2872572925"` |
| `nickname` | Nome do drone | `"T40-02"` |
| `flyer_name` | Nome do piloto | `"Paulo Andrzejevski"` |
| `team_name` | Nome da equipe | `"default team"` |
| `work_speed` | Velocidade de trabalho | `8.1` (m/s) |
| `spray_width` | Largura de pulverização | `7.85` (metros) |
| `new_work_area` | Área trabalhada | `9793.33` (m²) |
| `spray_usage` | Volume pulverizado | `22352` (ml) |
| `app_version` | Versão do app | `"6.5.47"` |
| `nozzle_type` | Tipo de bico | `1` |
| `use_rtk_flag` | Usando RTK | `0` ou `1` |
| `manual_mode` | Modo manual | `false` |

### Dos Dados de Voo (protobuf binário - por ponto)

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `latitude` | Latitude GPS | `-25.094082` |
| `longitude` | Longitude GPS | `-48.903529` |
| `heading` | Direção (graus) | `94.6` |
| `velocity_x` | Velocidade X | `-0.1` (m/s) |
| `velocity_y` | Velocidade Y | `-0.1` (m/s) |
| `speed_ms` | Velocidade total calculada | `0.14` (m/s) |
| `spray_rate` | Taxa de pulverização | `0.1` |

---

## 📁 Estrutura de Saída

```
downloads/
├── records_list.json              # Lista de todos os records
├── all_records_v3/                # Pasta com records baixados
│   ├── record_531405271/
│   │   ├── route_data.bin         # Dados binários originais
│   │   ├── api_metadata.json      # Metadados da API (JSON)
│   │   ├── mission.geojson        # GeoJSON com telemetria
│   │   └── screenshot.png         # Captura de tela
│   ├── record_531405260/
│   │   └── ...
│   └── index.json                 # Índice de todos os downloads
```

---

## 📝 Exemplo de GeoJSON Gerado

```json
{
  "type": "FeatureCollection",
  "name": "DJI AG Flight 531405271",
  "properties": {
    "flight_record_number": 531405271,
    "serial_number": "R2872572925",
    "date": 20260129,
    "start_datetime": "2026-01-28T16:11:05",
    "end_datetime": "2026-01-28T16:20:12",
    "duration_minutes": 9.1,
    "location": "Bocaiúva do Sul, PR, Brazil",
    "drone_type": "T40",
    "nickname": "T40-02",
    "pilot_name": "Paulo Andrzejevski",
    "flight_height_m": 3.0,
    "work_speed_ms": 8.1,
    "spray_width_m": 7.85,
    "work_area_ha": 0.98,
    "spray_usage_L": 22.35,
    "gps": {
      "total_points": 10954,
      "lat_min": -25.096940,
      "lat_max": -25.092552,
      "lon_min": -48.903535,
      "lon_max": -48.900157,
      "center_lat": -25.094746,
      "center_lon": -48.901846
    },
    "telemetry": {
      "heading_avg": -13.99,
      "heading_min": -179.9,
      "heading_max": 179.9,
      "speed_avg_ms": 5.7,
      "speed_max_ms": 12.64,
      "spray_rate_avg": 0.93
    }
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[-48.903529, -25.094082], ...]
      },
      "properties": {"type": "flight_path", "total_points": 10954}
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-48.903529, -25.094082]
      },
      "properties": {
        "index": 0,
        "latitude": -25.094082,
        "longitude": -48.903529,
        "heading": 94.6,
        "velocity_x": -0.1,
        "velocity_y": -0.1,
        "spray_rate": 0.1,
        "speed_ms": 0.14
      }
    }
  ]
}
```

---

## 📝 Exemplo de Lista de Records (`records_list.json`)

```json
[
  {
    "id": "531405271",
    "takeoff_landing_time": "16:11:05-16:20:12",
    "flight_duration": "09min07s",
    "task_mode": "Spray",
    "area": "0.98 ha",
    "application_rate": "22.4L",
    "flight_mode": "Auto",
    "pilot_name": "Paulo Andrzejevski",
    "device_name": "T40-02"
  },
  {
    "id": "531405260",
    "takeoff_landing_time": "15:49:04-15:57:05",
    "flight_duration": "08min01s",
    "task_mode": "Spray",
    "area": "1.68 ha",
    "application_rate": "33L",
    "flight_mode": "Auto",
    "pilot_name": "Paulo Andrzejevski",
    "device_name": "T40-02"
  }
]
```

---

## 🔧 Como Usar

### 1. Configurar credenciais
```bash
cp .env.example .env
# Editar .env com email e senha do DJI Account
```

**Exemplo `.env`:**
```
DJI_EMAIL=seu_email@exemplo.com
DJI_PASSWORD=sua_senha_aqui
```

### 2. Instalar dependências
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Fazer login (primeira vez)
```bash
python test_hybrid_login.py
```

### 4. Listar todos os records
```bash
python list_records.py
```

**Saída esperada:**
```
🔍 Buscando records...
   📄 Página 1/4
   ✅ Página 1: 30 records
   ✅ Página 2: 30 records
   ✅ Página 3: 30 records
   ✅ Página 4: 8 records
================================================================
ID           DATA/HORA                 DURAÇÃO      MODO       ÁREA
================================================================
531405271    16:11:05-16:20:12         09min07s     Spray      0.98 ha
531405260    15:49:04-15:57:05         08min01s     Spray      1.68 ha
...
================================================================
Total: 98 records
✅ Lista salva em: downloads/records_list.json
```

### 5. Baixar todos os records
```bash
python download_all_records_v3.py
```

**Saída esperada:**
```
📦 RECORD 1/30: 531405271
   🔗 https://www.djiag.com/record/531405271
   📋 Metadados capturados
   📥 Dados: 4,572,567 bytes
   ✅ GeoJSON salvo!
   📅 Data: 20260129
   ⏱️ Duração: 9.1 min
   🏔️ Altura: 3.0m
   📍 Área: 0.98 ha
   🚁 Drone: T40 (T40-02)
   📊 GPS: 10954 pontos
...
📊 RESUMO DO DOWNLOAD
   Total records: 30
   ✅ Baixados: 30
   ❌ Erros: 0
   📍 Total pontos GPS: 237,969
   🌾 Total área: 37.32 ha
```

---

## ⚠️ Limitações Descobertas

| Limitação | Descrição |
|-----------|-----------|
| **Sem KML** | DJI AG não oferece export KML, apenas protobuf binário |
| **WebAssembly** | Bloqueia requisições HTTP diretas (precisa Playwright) |
| **Dados incompletos** | Alguns records não têm dados de voo (apenas metadados) |
| **Coordenadas BR** | Filtro otimizado para Brasil (-35 < lat < -5, -75 < lon < -35) |

---

## 📈 Estatísticas

- **98 records** listados (4 páginas)
- **~238.000 pontos GPS** extraídos
- **~37 hectares** de área total
- **30 records** na primeira página

---

## 🔗 APIs Descobertas

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/web/v1/flight_records/{id}` | GET | Metadados completos do voo (JSON) |
| `/api/web/v2/airlines/{id}` | GET | URLs para download dos dados binários |
| `/api/web/v2/flight_datas/objects/airline/{id}/...` | GET | Dados binários protobuf da rota |

---

## 🔍 Estrutura do Protobuf (descoberta)

Os dados binários usam protobuf com a seguinte estrutura:

| Profundidade | Campo | Tipo | Descrição |
|--------------|-------|------|-----------|
| 3 | `dbl_1` | double | Latitude |
| 3 | `dbl_2` | double | Longitude |
| 3 | `dbl_3` | double | Heading (direção) |
| 3 | `flt_1` | float | Velocity X |
| 3 | `flt_2` | float | Velocity Y |
| 3 | `flt_3` | float | Spray Rate |
| 2 | `flt_39` | float | Battery % |
| 2 | `int_10` | int | Task Speed |
| 3 | `int_7` | int | Route Spacing |

---

## 📝 Arquivos de Configuração

| Arquivo | Descrição |
|---------|-----------|
| `.env` | Credenciais (DJI_EMAIL, DJI_PASSWORD) |
| `.env.example` | Template de credenciais |
| `browser_profile/` | Sessão persistente do Playwright |
| `requirements.txt` | Dependências Python |

---

## 🚀 Próximos Passos Possíveis

1. **Exportar para outros formatos** (CSV, Shapefile)
2. **Gerar relatórios** agregados por dia/piloto/drone
3. **Visualização em mapa** (Leaflet, Mapbox)
4. **Integração com sistemas agrícolas** (API REST)
5. **Análise de cobertura** (verificar sobreposição de passadas)
