import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('specialist_agent', str(Path(__file__).parent.parent.joinpath('backend','agents','specialist_agent.py')))
specialist_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(specialist_agent)

tests = [
    'AV. PINTOS, 1256, SOROCABANO, JABOTICABAL - SP, CEP: 14870000',
    'Rua das Flores 123, Jardim Primavera, Campinas - SP, 13000-000',
    'Praça Central, Centro, Belo Horizonte MG 30123-456',
    'Av Brasil 1000 - Rio de Janeiro/RJ - CEP 20000-000',
    'Rua sembairro, 45, SomeCity - XX, cep: 12345678'
]

for t in tests:
    print('---')
    print(t)
    print(specialist_agent._extract_address_parts(t))
