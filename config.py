import os
from dotenv import load_dotenv

load_dotenv()  # carrega .env localmente; em produção usa as env vars do Vercel

SECRET_KEY     = os.getenv('SECRET_KEY', 'chave-insegura-troque-em-producao')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')

# Em produção (Vercel) o filesystem é efêmero — usa /tmp.
# Localmente usa a raiz do projeto.
_db_dir  = '/tmp' if os.getenv('VERCEL') else '.'
DATABASE = os.path.join(_db_dir, 'database.db')

CREDENTIALS_FILE = 'credentials.json'

# URLs das abas publicadas como CSV (somente leitura pública — ok ficar no código)
SHEETS_URLS = {
    'usuarios':        'https://docs.google.com/spreadsheets/d/e/2PACX-1vTJwCTUI4iRBDii_kwcu5_6gVL2xDwczYZoRL37RIgk0KT6CPBp8L1RLJgpSovOaHVNbd-kBSvA8HzH/pub?gid=0&single=true&output=csv',
    'professores':     'https://docs.google.com/spreadsheets/d/e/2PACX-1vTJwCTUI4iRBDii_kwcu5_6gVL2xDwczYZoRL37RIgk0KT6CPBp8L1RLJgpSovOaHVNbd-kBSvA8HzH/pub?gid=812465740&single=true&output=csv',
    'tipos_avaliacao': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTJwCTUI4iRBDii_kwcu5_6gVL2xDwczYZoRL37RIgk0KT6CPBp8L1RLJgpSovOaHVNbd-kBSvA8HzH/pub?gid=1404603060&single=true&output=csv',
    'vinculos':        'https://docs.google.com/spreadsheets/d/e/2PACX-1vTJwCTUI4iRBDii_kwcu5_6gVL2xDwczYZoRL37RIgk0KT6CPBp8L1RLJgpSovOaHVNbd-kBSvA8HzH/pub?gid=1291573465&single=true&output=csv',
    'avaliacoes':      'https://docs.google.com/spreadsheets/d/e/2PACX-1vTJwCTUI4iRBDii_kwcu5_6gVL2xDwczYZoRL37RIgk0KT6CPBp8L1RLJgpSovOaHVNbd-kBSvA8HzH/pub?gid=816095818&single=true&output=csv',
}

TIPOS_AVALIACAO_PADRAO = ['PROVA PAULISTA', 'SARESP', 'SAEB']

DISCIPLINAS = ['MAT', 'PORT', 'ING', 'HIST', 'GEO', 'CIE', 'FILO', 'SOC', 'BIO', 'FIS', 'QUI', 'FIN', 'TEC']

DISCIPLINAS_NOMES = {
    'MAT':  'Matemática',
    'PORT': 'Português',
    'ING':  'Inglês',
    'HIST': 'História',
    'GEO':  'Geografia',
    'CIE':  'Ciências',
    'FILO': 'Filosofia',
    'SOC':  'Sociologia',
    'BIO':  'Biologia',
    'FIS':  'Física',
    'QUI':  'Química',
    'FIN':  'Financeira',
    'TEC':  'Tecnologia',
}
