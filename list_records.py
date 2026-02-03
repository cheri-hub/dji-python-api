#!/usr/bin/env python
"""
Listar todos os records do DJI AG com dados da tabela
Retorna os mesmos dados que aparecem na página após clicar em "List"
"""

import os
import sys
import time
import json
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")


def extract_table_records(page):
    """Extrai records da página atual da tabela"""
    return page.evaluate("""
        () => {
            const records = [];
            const rows = document.querySelectorAll('.ant-table-row');
            
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                const rowKey = row.getAttribute('data-row-key');
                
                // Pular linhas de grupo (IDs que começam com timestamp grande)
                if (!rowKey || rowKey.length > 12) return;
                
                if (cells.length >= 9) {
                    const record = {
                        id: rowKey,
                        takeoff_landing_time: cells[1]?.textContent?.trim() || '',
                        flight_duration: cells[2]?.textContent?.trim() || '',
                        task_mode: cells[3]?.textContent?.trim() || '',
                        area: cells[4]?.textContent?.trim() || '',
                        application_rate: cells[5]?.textContent?.trim() || '',
                        flight_mode: cells[6]?.textContent?.trim() || '',
                        pilot_name: cells[7]?.textContent?.trim() || '',
                        device_name: cells[8]?.textContent?.trim() || '',
                    };
                    records.push(record);
                }
            });
            
            return records;
        }
    """)


def get_pagination_info(page):
    """Retorna informações de paginação"""
    return page.evaluate("""
        () => {
            const pagination = document.querySelector('.ant-pagination');
            if (!pagination) return { total_pages: 1, current_page: 1, has_next: false };
            
            // Tentar pegar o total de páginas
            const pages = pagination.querySelectorAll('.ant-pagination-item');
            const lastPage = pages.length > 0 ? parseInt(pages[pages.length - 1].textContent) : 1;
            
            // Página atual
            const current = pagination.querySelector('.ant-pagination-item-active');
            const currentPage = current ? parseInt(current.textContent) : 1;
            
            // Tem próxima página?
            const nextBtn = pagination.querySelector('.ant-pagination-next');
            const hasNext = nextBtn && !nextBtn.classList.contains('ant-pagination-disabled');
            
            // Total de itens (se disponível)
            const totalText = pagination.querySelector('.ant-pagination-total-text');
            const totalMatch = totalText?.textContent?.match(/\\d+/);
            const totalItems = totalMatch ? parseInt(totalMatch[0]) : null;
            
            return {
                total_pages: lastPage,
                current_page: currentPage,
                has_next: hasNext,
                total_items: totalItems
            };
        }
    """)


def list_all_records(headless=False):
    """
    Lista todos os records do DJI AG (todas as páginas)
    
    Returns:
        list: Lista de dicionários com os dados de cada record
    """
    all_records = []
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=headless,
            slow_mo=50,
            viewport={"width": 1400, "height": 900},
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Acessar página
        page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
        time.sleep(3)
        
        # Clicar em List
        try:
            list_btn = page.locator("button:has-text('List'), span:has-text('List')").first
            list_btn.click()
            time.sleep(3)
        except:
            pass
        
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Verificar paginação
        pagination = get_pagination_info(page)
        print(f"   📄 Página {pagination['current_page']}/{pagination['total_pages']}")
        if pagination.get('total_items'):
            print(f"   📊 Total de itens: {pagination['total_items']}")
        
        # Coletar primeira página
        records = extract_table_records(page)
        all_records.extend(records)
        print(f"   ✅ Página 1: {len(records)} records")
        
        # Navegar pelas próximas páginas
        page_num = 1
        while pagination['has_next']:
            page_num += 1
            
            # Clicar no botão "próxima página"
            try:
                next_btn = page.locator('.ant-pagination-next').first
                if next_btn:
                    next_btn.click()
                    time.sleep(2)
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    
                    # Coletar records desta página
                    records = extract_table_records(page)
                    all_records.extend(records)
                    print(f"   ✅ Página {page_num}: {len(records)} records")
                    
                    # Atualizar info de paginação
                    pagination = get_pagination_info(page)
                else:
                    break
            except Exception as e:
                print(f"   ⚠️ Erro na página {page_num}: {e}")
                break
        
        context.close()
    
    # Remover duplicatas (por ID)
    seen_ids = set()
    unique_records = []
    for r in all_records:
        if r['id'] not in seen_ids:
            seen_ids.add(r['id'])
            unique_records.append(r)
    
    return unique_records


def print_records(records):
    """Imprime os records em formato tabular"""
    print(f"\n{'='*120}")
    print(f"{'ID':<12} {'DATA/HORA':<25} {'DURAÇÃO':<12} {'MODO':<10} {'ÁREA':<10} {'PAYLOAD':<12} {'VOO':<8} {'PILOTO':<20} {'DRONE':<10}")
    print(f"{'='*120}")
    
    for r in records:
        print(f"{r['id']:<12} {r['takeoff_landing_time']:<25} {r['flight_duration']:<12} {r['task_mode']:<10} {r['area']:<10} {r['application_rate']:<12} {r['flight_mode']:<8} {r['pilot_name'][:18]:<20} {r['device_name']:<10}")
    
    print(f"{'='*120}")
    print(f"Total: {len(records)} records")


if __name__ == "__main__":
    print("=" * 60)
    print(" DJI AG - LISTAR TODOS OS RECORDS")
    print("=" * 60)
    
    print("\n🔍 Buscando records...")
    records = list_all_records(headless=False)
    
    print_records(records)
    
    # Salvar JSON
    output_path = os.path.join(os.path.dirname(__file__), "downloads", "records_list.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'date': datetime.now().isoformat(),
            'total': len(records),
            'records': records
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Lista salva em: {output_path}")
