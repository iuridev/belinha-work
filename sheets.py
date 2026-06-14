import os
from datetime import datetime
import requests
import pandas as pd
from io import StringIO
from config import SHEETS_URLS, SPREADSHEET_ID, CREDENTIALS_FILE, TIPOS_AVALIACAO_PADRAO

# ── Cabeçalhos das abas gerenciadas pelo sistema ────────────────────────────

CABECALHO_VINCULOS = ['id', 'professor_id', 'nome_professor', 'disciplina', 'turma', 'ano_letivo']

CABECALHO_AVALIACOES = [
    'id', 'bimestre', 'ano', 'turma', 'tipo_avaliacao', 'total_alunos',
    'perc_participacao', 'perc_acertos',
    'MAT', 'PORT', 'ING', 'HIST', 'GEO', 'CIE',
    'FILO', 'SOC', 'BIO', 'FIS', 'QUI', 'FIN', 'TEC',
    'data_importacao', 'ARTE'
]


# ── Leitura via CSV público ─────────────────────────────────────────────────

def _fetch_csv(tab):
    url = SHEETS_URLS.get(tab, '')
    if not url or url.startswith('COLE_AQUI'):
        return []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text), dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.where(pd.notna(df), None)
        return df.to_dict('records')
    except Exception as e:
        print(f'Erro ao ler aba {tab}: {e}')
        return []


def _is_ativo(valor):
    return str(valor).upper().strip() in ('SIM', 'TRUE', '1', 'S', 'YES')


# ── Leituras públicas ───────────────────────────────────────────────────────

def get_usuarios():
    return _fetch_csv('usuarios')


def get_professores():
    rows = _fetch_csv('professores')
    return [r for r in rows if _is_ativo(r.get('ativo', ''))]


def get_tipos_avaliacao():
    rows = _fetch_csv('tipos_avaliacao')
    ativos = [r.get('nome', '').strip() for r in rows if _is_ativo(r.get('ativo', '')) and r.get('nome')]
    return ativos if ativos else TIPOS_AVALIACAO_PADRAO


def _api_disponivel():
    """Retorna True se credenciais estão disponíveis (arquivo local ou env var)."""
    return os.path.exists(CREDENTIALS_FILE) or bool(os.getenv('GOOGLE_CREDENTIALS_JSON'))


def get_vinculos_planilha():
    """Lê vínculos em tempo real via API (sem cache). Fallback para CSV publicado."""
    if _api_disponivel():
        try:
            ws = _get_sheet('vinculos')
            registros = ws.get_all_records()
            return [{k.lower(): (v if v != '' else None) for k, v in r.items()} for r in registros]
        except Exception as e:
            print(f'Aviso: leitura de vínculos via API falhou ({e}), usando CSV publicado')
    return _fetch_csv('vinculos')


def get_avaliacoes_planilha():
    """Lê avaliações em tempo real via API, mapeando por posição (ignora cabeçalho desatualizado)."""
    if _api_disponivel():
        try:
            ws = _get_sheet('avaliacoes')
            todas = ws.get_all_values()
            if len(todas) < 2:
                return []
            # Corrige o cabeçalho se necessário (sem tocar nos dados)
            if todas[0] != CABECALHO_AVALIACOES:
                ws.update('A1', [CABECALHO_AVALIACOES])
            cols = [c.lower() for c in CABECALHO_AVALIACOES]
            resultado = []
            for row in todas[1:]:
                if not any(v.strip() for v in row if isinstance(v, str)):
                    continue
                r = {cols[i]: (row[i] if i < len(row) and row[i] != '' else None)
                     for i in range(len(cols))}
                resultado.append(r)
            return resultado
        except Exception as e:
            print(f'Aviso: leitura de avaliações via API falhou ({e}), usando CSV publicado')
    return _fetch_csv('avaliacoes')


def autenticar(login, senha):
    for u in get_usuarios():
        mesmo_login = str(u.get('login', '')).strip() == login.strip()
        mesma_senha = str(u.get('senha', '')).strip() == senha.strip()
        if mesmo_login and mesma_senha and _is_ativo(u.get('ativo', '')):
            return u
    return None


# ── Escrita via API (requer credentials.json) ───────────────────────────────

def _get_sheet(nome_aba):
    import json
    import gspread

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    # 1. Variável de ambiente (produção / Vercel)
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON', '').strip().lstrip('﻿')
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                f'GOOGLE_CREDENTIALS_JSON inválido ({e}). '
                'Gere o valor correto com: '
                'python -c "import json; print(json.dumps(json.load(open(\'credentials.json\'))))"'
            )
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
        return gc.open_by_key(SPREADSHEET_ID).worksheet(nome_aba)

    # 2. Arquivo local (desenvolvimento)
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            'Credenciais não encontradas. '
            'Em produção: defina GOOGLE_CREDENTIALS_JSON no Vercel. '
            'Em desenvolvimento: coloque credentials.json na raiz do projeto.'
        )
    gc = gspread.service_account(filename=CREDENTIALS_FILE, scopes=SCOPES)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(nome_aba)


def _garantir_cabecalho(ws, cabecalho):
    primeira_linha = ws.row_values(1)
    if not primeira_linha:
        ws.append_row(cabecalho)
    elif primeira_linha != cabecalho:
        # Atualiza só o cabeçalho sem tocar nos dados
        ws.update('A1', [cabecalho])


def _proximo_id(registros):
    ids = [int(str(r.get('id', 0))) for r in registros if str(r.get('id', '')).isdigit()]
    return max(ids, default=0) + 1


# ── Professores ─────────────────────────────────────────────────────────────

def adicionar_professor(nome, cpf):
    ws = _get_sheet('professores')
    todos = get_professores()
    novo_id = _proximo_id(todos)
    ws.append_row([novo_id, nome, cpf, 'TRUE'], value_input_option='USER_ENTERED')
    return novo_id


def atualizar_professor(professor_id, nome, cpf):
    ws = _get_sheet('professores')
    registros = ws.get_all_records()
    for i, row in enumerate(registros, start=2):
        if str(row.get('id')) == str(professor_id):
            col_nome = _col_index(ws, 'nome')
            col_cpf  = _col_index(ws, 'cpf')
            ws.update_cell(i, col_nome, nome)
            ws.update_cell(i, col_cpf,  cpf)
            return True
    return False


def inativar_professor(professor_id):
    ws = _get_sheet('professores')
    registros = ws.get_all_records()
    for i, row in enumerate(registros, start=2):
        if str(row.get('id')) == str(professor_id):
            col_ativo = _col_index(ws, 'ativo')
            ws.update_cell(i, col_ativo, 'FALSE')
            return True
    return False


# ── Vínculos ────────────────────────────────────────────────────────────────

def salvar_vinculo_planilha(professor_id, nome_professor, disciplina, turma, ano_letivo):
    """Salva ou atualiza um vínculo na planilha. Retorna o id do registro."""
    ws = _get_sheet('vinculos')
    _garantir_cabecalho(ws, CABECALHO_VINCULOS)
    registros = ws.get_all_records()

    # Verifica se já existe (disciplina + turma + ano_letivo) → atualiza
    for i, r in enumerate(registros, start=2):
        if (str(r.get('disciplina')) == str(disciplina)
                and str(r.get('turma')) == str(turma)
                and str(r.get('ano_letivo')) == str(ano_letivo)):
            ws.update(f'A{i}:F{i}', [[
                r.get('id'), professor_id, nome_professor,
                disciplina, turma, ano_letivo
            ]])
            return int(str(r.get('id')))

    # Novo registro
    novo_id = _proximo_id(registros)
    ws.append_row([novo_id, professor_id, nome_professor, disciplina, turma, ano_letivo])
    return novo_id


def remover_vinculo_planilha(vinculo_id):
    """Remove um vínculo da planilha pelo id."""
    ws = _get_sheet('vinculos')
    registros = ws.get_all_records()
    for i, r in enumerate(registros, start=2):
        if str(r.get('id')) == str(vinculo_id):
            ws.delete_rows(i)
            return True
    return False


# ── Avaliações ──────────────────────────────────────────────────────────────

def salvar_avaliacoes_planilha(registros, bimestre, ano, tipo_avaliacao='PROVA PAULISTA'):
    """Grava os registros importados na aba 'avaliacoes' da planilha.
    Ao conflitar (mesma turma/bimestre/ano/tipo), faz merge: mantém valores existentes
    nas colunas que chegam vazias — necessário para imports de TAREFAS por disciplina.
    """
    ws = _get_sheet('avaliacoes')
    _garantir_cabecalho(ws, CABECALHO_AVALIACOES)

    existentes = ws.get_all_records()
    # Mapeia chave → (linha_na_planilha, dados_existentes)
    # get_all_records() retorna chaves com o mesmo case do cabeçalho (ex: 'PORT', 'MAT')
    existentes_map = {
        (str(r.get('bimestre')), str(r.get('ano')),
         str(r.get('turma')), str(r.get('tipo_avaliacao', ''))): (i, r)
        for i, r in enumerate(existentes, start=2)
    }

    proximo_id = _proximo_id(existentes)
    agora = datetime.now().strftime('%d/%m/%Y %H:%M')
    novas_linhas = []
    gravados = 0

    # Mapa: coluna do cabeçalho → chave no registro (lowercase)
    # CABECALHO usa maiúsculo para disciplinas (MAT, PORT...) mas r usa minúsculo (mat, port...)
    CABECALHO_PARA_CHAVE = {
        'id': None, 'bimestre': 'bimestre', 'ano': 'ano',
        'turma': 'turma', 'tipo_avaliacao': 'tipo_avaliacao',
        'total_alunos': 'total_alunos', 'perc_participacao': 'perc_participacao',
        'perc_acertos': 'perc_acertos', 'data_importacao': None,
        **{d: d.lower() for d in ['MAT','PORT','ING','HIST','GEO','CIE','FILO','SOC','BIO','FIS','QUI','FIN','TEC','ARTE']}
    }

    for r in registros:
        chave = (str(bimestre), str(ano), str(r['turma']), str(tipo_avaliacao))

        # Monta nova linha na ordem exata de CABECALHO_AVALIACOES
        nova = []
        for col in CABECALHO_AVALIACOES:
            if col == 'id':
                nova.append(proximo_id)
            elif col == 'data_importacao':
                nova.append(agora)
            elif col == 'bimestre':
                nova.append(bimestre)
            elif col == 'ano':
                nova.append(ano)
            elif col == 'tipo_avaliacao':
                nova.append(tipo_avaliacao)
            else:
                chave_r = CABECALHO_PARA_CHAVE.get(col, col.lower())
                v = r.get(chave_r)
                nova.append(v if v is not None else '')

        if chave in existentes_map:
            row_idx, existing = existentes_map[chave]
            # Merge: se novo valor é vazio, mantém o existente
            # existing usa as chaves do cabeçalho (case original: 'PORT', 'MAT', etc.)
            merged = []
            for col, nv in zip(CABECALHO_AVALIACOES, nova):
                if col == 'id':
                    merged.append(existing.get('id', proximo_id))  # preserva ID existente
                elif col == 'data_importacao':
                    merged.append(agora)
                elif nv != '' and nv is not None:
                    merged.append(nv)
                else:
                    merged.append(existing.get(col, '') or '')
            # Garante que data_importacao sempre reflete o momento do import
            idx_data = CABECALHO_AVALIACOES.index('data_importacao')
            merged[idx_data] = agora
            col_fim = chr(ord('A') + len(CABECALHO_AVALIACOES) - 1)
            ws.update(f'A{row_idx}:{col_fim}{row_idx}',
                      [merged], value_input_option='USER_ENTERED')
        else:
            novas_linhas.append(nova)
            proximo_id += 1

        gravados += 1

    if novas_linhas:
        ws.append_rows(novas_linhas, value_input_option='USER_ENTERED')

    return gravados


# ── Utilitários ─────────────────────────────────────────────────────────────

def _col_index(ws, nome_col):
    headers = ws.row_values(1)
    nome_col = nome_col.lower().strip()
    for i, h in enumerate(headers, start=1):
        if h.lower().strip() == nome_col:
            return i
    raise ValueError(f'Coluna "{nome_col}" não encontrada na planilha.')
