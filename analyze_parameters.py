"""
Análise mais profunda - buscar todos os valores constantes/parâmetros de missão
"""
import os
import struct
from collections import defaultdict

def decode_varint(data, pos):
    result, shift = 0, 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos

def analyze_all_depths(data, max_depth=5):
    """Analisa todos os níveis do protobuf"""
    
    all_values = defaultdict(lambda: defaultdict(list))
    
    def parse_recursive(data, depth=0, path=""):
        if depth > max_depth:
            return
            
        pos = 0
        while pos < len(data):
            try:
                tag, new_pos = decode_varint(data, pos)
                if new_pos >= len(data):
                    break
                pos = new_pos
                
                wire_type = tag & 0x07
                field = tag >> 3
                key = f"d{depth}_f{field}"
                
                if wire_type == 0:  # varint
                    val, pos = decode_varint(data, pos)
                    if val < 1e15:  # filtrar valores muito grandes
                        all_values[depth][f'int_{field}'].append(val)
                        
                elif wire_type == 1:  # double
                    if pos + 8 <= len(data):
                        val = struct.unpack('<d', data[pos:pos+8])[0]
                        if -1e10 < val < 1e10:
                            all_values[depth][f'dbl_{field}'].append(val)
                    pos += 8
                    
                elif wire_type == 2:  # submensagem
                    length, pos = decode_varint(data, pos)
                    if length and pos + length <= len(data):
                        parse_recursive(data[pos:pos+length], depth + 1)
                        pos += length
                    else:
                        break
                        
                elif wire_type == 5:  # float
                    if pos + 4 <= len(data):
                        val = struct.unpack('<f', data[pos:pos+4])[0]
                        if -1e10 < val < 1e10:
                            all_values[depth][f'flt_{field}'].append(val)
                    pos += 4
                else:
                    break
            except:
                break
    
    parse_recursive(data)
    return all_values

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print(f"\n{'='*70}")
    print("🔬 ANÁLISE PROFUNDA - TODOS OS NÍVEIS DO PROTOBUF")
    print(f"{'='*70}\n")
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"Arquivo: {os.path.basename(route_file)}")
    print(f"Tamanho: {len(data):,} bytes\n")
    
    all_values = analyze_all_depths(data, max_depth=6)
    
    # Procurar valores constantes (provavelmente são parâmetros)
    print(f"\n{'='*70}")
    print("🎯 VALORES CONSTANTES OU QUASE CONSTANTES (parâmetros de missão)")
    print(f"{'='*70}")
    
    for depth in sorted(all_values.keys()):
        print(f"\n📁 DEPTH {depth}:")
        
        for key in sorted(all_values[depth].keys()):
            values = all_values[depth][key]
            if len(values) < 10:
                continue
            
            unique = set(round(v, 4) if isinstance(v, float) else v for v in values)
            
            # Valores constantes ou com poucas variações
            if len(unique) <= 10:
                field_type = key.split('_')[0]
                field_num = key.split('_')[1]
                
                sorted_unique = sorted(unique)
                
                # Identificar possíveis significados
                meaning = ""
                sample_val = list(unique)[0]
                
                if isinstance(sample_val, float):
                    if 2 <= sample_val <= 10:
                        meaning = "← ROUTE SPACING ou SPEED?"
                    elif 0 < sample_val < 2:
                        meaning = "← SPRAY FLOW RATE?"
                    elif 5 <= sample_val <= 50:
                        meaning = "← ALTITUDE?"
                    elif 90 <= sample_val <= 110:
                        meaning = "← porcentagem?"
                
                print(f"   {key}: {len(values)} ocorrências | "
                      f"valores: {sorted_unique[:5]} {meaning}")
    
    # Procurar especificamente valores típicos
    print(f"\n{'='*70}")
    print("🎯 BUSCA POR VALORES TÍPICOS DE PARÂMETROS")
    print(f"{'='*70}")
    
    # Spray Flow Rate: 0.5 - 10 L/min
    print("\n💧 Possível SPRAY FLOW RATE (0.5 - 10 L/min):")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'flt' in key or 'dbl' in key:
                values = all_values[depth][key]
                candidates = [v for v in values if 0.5 <= v <= 15]
                unique = set(round(v, 2) for v in candidates)
                if len(unique) >= 10 and len(unique) <= 50:
                    print(f"   Depth {depth} {key}: {sorted(unique)[:10]}...")
                elif 1 <= len(unique) <= 5:
                    print(f"   Depth {depth} {key}: {sorted(unique)} ({len(candidates)} ocorrências)")
    
    # Route Spacing: 2-10m
    print("\n📏 Possível ROUTE SPACING (2-10 m):")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'flt' in key or 'dbl' in key:
                values = all_values[depth][key]
                candidates = [v for v in values if 2 <= v <= 12]
                unique = set(round(v, 1) for v in candidates)
                if 1 <= len(unique) <= 5 and len(candidates) > 100:
                    print(f"   Depth {depth} {key}: {sorted(unique)} ({len(candidates)} ocorrências)")
    
    # Task Speed: 2-20 m/s
    print("\n🚀 Possível TASK SPEED (2-20 m/s):")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'flt' in key or 'dbl' in key:
                values = all_values[depth][key]
                candidates = [v for v in values if 2 <= v <= 20]
                unique = set(round(v, 1) for v in candidates)
                if 1 <= len(unique) <= 5 and len(candidates) > 100:
                    print(f"   Depth {depth} {key}: {sorted(unique)} ({len(candidates)} ocorrências)")
    
    # Altitude: 5-50m
    print("\n🏔️ Possível ALTITUDE (5-100 m):")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'flt' in key or 'dbl' in key:
                values = all_values[depth][key]
                candidates = [v for v in values if 5 <= v <= 100]
                unique = set(round(v, 1) for v in candidates)
                if 1 <= len(unique) <= 10 and len(candidates) > 100:
                    print(f"   Depth {depth} {key}: {sorted(unique)} ({len(candidates)} ocorrências)")
    
    # Ângulos
    print("\n🧭 Possível HEADING/GIMBAL (0-360°):")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'flt' in key:
                values = all_values[depth][key]
                candidates = [v for v in values if 0 <= v <= 360]
                if len(candidates) > 1000:
                    unique = set(round(v, 0) for v in candidates[:1000])
                    if 8 <= len(unique) <= 16:  # Valores discretos de ângulo
                        print(f"   Depth {depth} {key}: {sorted(unique)} ({len(candidates)} ocorrências)")
    
    # Inteiros interessantes
    print("\n🔢 INTEIROS INTERESSANTES:")
    for depth in sorted(all_values.keys()):
        for key in all_values[depth]:
            if 'int' in key:
                values = all_values[depth][key]
                if len(values) < 100:
                    continue
                unique = set(values)
                if 1 <= len(unique) <= 5:
                    field_num = key.split('_')[1]
                    print(f"   Depth {depth} {key}: valores {sorted(unique)} ({len(values)} ocorrências)")

if __name__ == "__main__":
    main()
