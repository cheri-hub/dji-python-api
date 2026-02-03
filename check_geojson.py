import json

with open('downloads/all_records_v3/record_530510380/mission.geojson', encoding='utf-8') as f:
    d = json.load(f)

print(f"Total features: {len(d['features'])}")

pts = [p for p in d['features'] if p['geometry']['type'] == 'Point']
print(f"Total pontos: {len(pts)}")

print("\nPrimeiros 10 pontos:")
for i, p in enumerate(pts[:10]):
    lat = p['properties']['latitude']
    lon = p['properties']['longitude']
    print(f"  {i}: lat={lat:.6f}, lon={lon:.6f}")

print("\nÚltimos 5 pontos:")
for i, p in enumerate(pts[-5:]):
    lat = p['properties']['latitude']
    lon = p['properties']['longitude']
    print(f"  {len(pts)-5+i}: lat={lat:.6f}, lon={lon:.6f}")
