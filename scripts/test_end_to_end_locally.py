import json
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
import importlib.util
def load_module_from_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

agents_dir = os.path.join(ROOT, 'backend', 'agents')
enrichment_agent = load_module_from_path('enrichment_agent', os.path.join(agents_dir, 'enrichment_agent.py'))
specialist_agent = load_module_from_path('specialist_agent', os.path.join(agents_dir, 'specialist_agent.py'))

# Test 1: totals reconciliation
record = {
    'id': 'test-1',
    'filename': 'fake.pdf',
    'uploaded_at': '2025-10-26T00:00:00',
    'status': 'preprocessamento',
    'progress': 50,
    'ocr_text': None,
    'raw_extracted': None,
    'extracted_data': {
        'valor_total': 56.49,
        'itens': [
            {'descricao': 'ARGAMASSA/ITEM A', 'quantidade': 10, 'valor_unitario': 42.0, 'valor_total': 420.0},
        ],
        'emitente': {'razao_social': 'ACME', 'endereco': 'Rua das Flores 123, Jardim Primavera, Campinas - SP, 13000-000'}
    }
}

new_extracted, info = enrichment_agent.enrich_record(record)
print('\n=== Totals Test ===')
print('Original valor_total:', record['extracted_data']['valor_total'])
print('Computed aggregates before/after in report:', info.get('aggregates'))
print('Result valor_total:', new_extracted.get('valor_total'))
print('Report notes:', info.get('report'))

# Test 2: address extraction via specialist
addresses = [
    'AV. PINTOS, 1256, SOROCABANO, JABOTICABAL - SP, CEP: 14870000',
    'Rua das Flores 123, Jardim Primavera, Campinas - SP, 13000-000',
    'Praça Central, Centro, Belo Horizonte MG 30123-456',
    'Av Brasil 1000 - Rio de Janeiro/RJ - CEP 20000-000'
]
print('\n=== Address Extraction Test ===')
for a in addresses:
    parts = specialist_agent._extract_address_parts(a)
    print(a)
    print(parts)

# Test 3: run specialist.refine_extracted on a record with missing bairro/municipio
rec2 = {'ocr_text': None, 'raw_extracted': None, 'extracted_data': {'emitente': {'endereco': 'Rua das Flores 123, Jardim Primavera, Campinas - SP, 13000-000'}}}
refined, notes = specialist_agent.refine_extracted(rec2, rec2['extracted_data'])
print('\n=== Refine Extracted Test ===')
print('Refined:', json.dumps(refined, indent=2, ensure_ascii=False))
print('Notes:', notes)
