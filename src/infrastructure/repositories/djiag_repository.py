"""
DJI AG Record Repository Implementation

Usa a thread dedicada do Playwright para todas as operações de browser.
"""
import asyncio
import json
from functools import partial
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...domain.interfaces import IRecordRepository
from ...domain.entities import Record, RecordSummary, FlightData
from ..services import PlaywrightBrowserService, ProtobufDecoder
from ..config import get_settings


class DjiAgRecordRepository(IRecordRepository):
    """Repositório para records do DJI AG usando Playwright"""
    
    def __init__(self, browser_service: PlaywrightBrowserService):
        self._browser = browser_service
        self._decoder = ProtobufDecoder()
        self._settings = get_settings()
    
    def _list_all_in_browser(self, page: "Page", req_page: int = 1, per_page: int = 30) -> List[RecordSummary]:
        """Lista todos os records (executado na thread do Playwright)"""
        # Navegar para records
        page.goto("https://www.djiag.com/br/records", timeout=60000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Clicar em List
        try:
            list_btn = page.locator("button:has-text('List'), span:has-text('List')").first
            if list_btn.is_visible(timeout=3000):
                list_btn.click()
                page.wait_for_timeout(3000)
        except:
            pass
        
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        all_records = []
        current_page = 1
        
        while True:
            # Extrair dados da tabela
            table_data = page.evaluate("""
                () => {
                    const records = [];
                    const rows = document.querySelectorAll('.ant-table-row');
                    
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        const rowKey = row.getAttribute('data-row-key');
                        
                        if (!rowKey || rowKey.length > 12) return;
                        
                        if (cells.length >= 9) {
                            records.push({
                                id: rowKey,
                                takeoff_landing_time: cells[1]?.textContent?.trim() || '',
                                flight_duration: cells[2]?.textContent?.trim() || '',
                                task_mode: cells[3]?.textContent?.trim() || '',
                                area: cells[4]?.textContent?.trim() || '',
                                application_rate: cells[5]?.textContent?.trim() || '',
                                flight_mode: cells[6]?.textContent?.trim() || '',
                                pilot_name: cells[7]?.textContent?.trim() || '',
                                device_name: cells[8]?.textContent?.trim() || '',
                            });
                        }
                    });
                    
                    return records;
                }
            """)
            
            for r in table_data:
                all_records.append(RecordSummary(**r))
            
            # Verificar próxima página
            has_next = page.evaluate("""
                () => {
                    const pagination = document.querySelector('.ant-pagination');
                    if (!pagination) return false;
                    const nextBtn = pagination.querySelector('.ant-pagination-next');
                    return nextBtn && !nextBtn.classList.contains('ant-pagination-disabled');
                }
            """)
            
            if not has_next:
                break
            
            # Ir para próxima página
            try:
                next_btn = page.locator('.ant-pagination-next').first
                next_btn.click()
                page.wait_for_timeout(2000)
                page.wait_for_load_state("networkidle")
                current_page += 1
            except:
                break
        
        # Aplicar paginação do request
        start = (req_page - 1) * per_page
        end = start + per_page
        
        return all_records[start:end]
    
    async def list_all(self, page: int = 1, per_page: int = 30) -> List[RecordSummary]:
        """Lista todos os records com paginação"""
        return await self._browser.execute_in_browser_async(
            self._list_all_in_browser,
            req_page=page,
            per_page=per_page,
            timeout=120
        )
    
    def _get_by_id_in_browser(self, page: "Page", record_id: str) -> Optional[Record]:
        """Busca um record pelo ID (executado na thread do Playwright)"""
        api_metadata = {}
        
        # Capturar resposta da API
        def capture_response(response):
            nonlocal api_metadata
            try:
                url = response.url
                content_type = response.headers.get('content-type', '')
                
                if 'json' in content_type:
                    if f'/flight_records/{record_id}' in url and '/aggr' not in url:
                        data = response.json()
                        if data.get('data'):
                            api_metadata = data['data']
            except:
                pass
        
        page.on("response", capture_response)
        
        page.goto(f"https://www.djiag.com/record/{record_id}", timeout=60000)
        page.wait_for_timeout(5000)
        page.wait_for_load_state("networkidle")
        
        page.remove_listener("response", capture_response)
        
        if not api_metadata:
            return None
        
        return Record(
            id=str(api_metadata.get('id', record_id)),
            serial_number=api_metadata.get('serial_number'),
            hardware_id=api_metadata.get('hardware_id'),
            start_timestamp=api_metadata.get('start_timestamp'),
            end_timestamp=api_metadata.get('end_timestamp'),
            create_date=str(api_metadata.get('create_date')),
            location=api_metadata.get('location'),
            drone_type=api_metadata.get('drone_type'),
            nickname=api_metadata.get('nickname'),
            app_version=api_metadata.get('app_version'),
            nozzle_type=api_metadata.get('nozzle_type'),
            flyer_name=api_metadata.get('flyer_name'),
            team_name=api_metadata.get('team_name'),
            radar_height=api_metadata.get('radar_height'),
            max_radar_height=api_metadata.get('max_radar_height'),
            work_speed=api_metadata.get('work_speed'),
            max_flight_speed=api_metadata.get('max_flight_speed'),
            spray_width=api_metadata.get('spray_width'),
            new_work_area=api_metadata.get('new_work_area'),
            spray_usage=api_metadata.get('spray_usage'),
            min_flow_speed_per_mu=api_metadata.get('min_flow_speed_per_mu'),
            manual_mode=api_metadata.get('manual_mode'),
            use_rtk=api_metadata.get('use_rtk_flag') == 1,
        )
    
    async def get_by_id(self, record_id: str) -> Optional[Record]:
        """Busca um record pelo ID"""
        return await self._browser.execute_in_browser_async(
            self._get_by_id_in_browser,
            record_id=record_id,
            timeout=90
        )
    
    def _get_flight_data_in_browser(self, page: "Page", record_id: str) -> Optional[FlightData]:
        """Busca os dados de voo (executado na thread do Playwright)"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[FlightData] Iniciando busca para record {record_id}")
        
        flight_data_bytes = []
        
        # Capturar dados binários
        def capture_response(response):
            try:
                url = response.url
                content_type = response.headers.get('content-type', '')
                
                if 'octet-stream' in content_type:
                    logger.info(f"[FlightData] Resposta octet-stream: {url[:100]}")
                    if 'flight_datas' in url or 'objects/airline' in url:
                        body = response.body()
                        logger.info(f"[FlightData] Dados binários capturados: {len(body)} bytes")
                        if len(body) > 10000:
                            flight_data_bytes.append(body)
            except Exception as e:
                logger.warning(f"[FlightData] Erro capturando resposta: {e}")
        
        page.on("response", capture_response)
        
        logger.info(f"[FlightData] Navegando para record {record_id}")
        page.goto(f"https://www.djiag.com/record/{record_id}", timeout=60000)
        
        logger.info("[FlightData] Aguardando 8s...")
        page.wait_for_timeout(8000)
        
        logger.info("[FlightData] Aguardando networkidle...")
        page.wait_for_load_state("networkidle")
        
        page.remove_listener("response", capture_response)
        
        logger.info(f"[FlightData] Dados capturados: {len(flight_data_bytes)} arquivos")
        
        if not flight_data_bytes:
            logger.warning(f"[FlightData] Nenhum dado binário encontrado para {record_id}")
            return None
        
        # Usar o maior arquivo (mais dados)
        largest = max(flight_data_bytes, key=len)
        logger.info(f"[FlightData] Maior arquivo: {len(largest)} bytes")
        
        result = self._decoder.decode(largest, record_id)
        logger.info(f"[FlightData] Decode retornou: {result is not None}")
        return result
    
    async def get_flight_data(self, record_id: str) -> Optional[FlightData]:
        """Busca os dados de voo de um record"""
        return await self._browser.execute_in_browser_async(
            self._get_flight_data_in_browser,
            record_id=record_id,
            timeout=120
        )
    
    def _download_record_in_browser(self, page: "Page", record_id: str) -> Optional[dict]:
        """Faz download completo de um record (executado na thread do Playwright)"""
        api_metadata = {}
        flight_data_bytes = []
        
        # Capturar respostas
        def capture_response(response):
            nonlocal api_metadata
            try:
                url = response.url
                content_type = response.headers.get('content-type', '')
                
                if 'json' in content_type:
                    if f'/flight_records/{record_id}' in url and '/aggr' not in url:
                        data = response.json()
                        if data.get('data'):
                            api_metadata = data['data']
                
                if 'octet-stream' in content_type:
                    if 'flight_datas' in url or 'objects/airline' in url:
                        body = response.body()
                        if len(body) > 10000:
                            flight_data_bytes.append(body)
            except:
                pass
        
        page.on("response", capture_response)
        
        page.goto(f"https://www.djiag.com/record/{record_id}", timeout=60000)
        page.wait_for_timeout(8000)
        page.wait_for_load_state("networkidle")
        
        page.remove_listener("response", capture_response)
        
        if not api_metadata:
            return {"success": False, "message": "No metadata found"}
        
        result = {
            "success": True,
            "record_id": record_id,
            "metadata": api_metadata,
            "flight_data": None,
            "total_points": 0,
        }
        
        if flight_data_bytes:
            largest = max(flight_data_bytes, key=len)
            flight_data = self._decoder.decode(largest, record_id)
            if flight_data:
                result["flight_data"] = flight_data
                result["total_points"] = flight_data.total_points
        
        return result
    
    async def download_record(self, record_id: str) -> Optional[dict]:
        """Faz download completo de um record"""
        return await self._browser.execute_in_browser_async(
            self._download_record_in_browser,
            record_id=record_id,
            timeout=120
        )
