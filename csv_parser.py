import unicodedata
import pandas as pd
from io import StringIO

DISC_COLUNAS = ['mat', 'port', 'ing', 'hist', 'geo', 'cie', 'filo', 'soc', 'bio', 'fis', 'qui', 'fin', 'tec']

# Nomes alternativos de disciplina usados no SARESP → chave interna do sistema
DISC_ALIAS = {
    'MAT':  'mat',  'PORT': 'port', 'LPT':  'port',  # LPT = Língua Portuguesa (SARESP)
    'ING':  'ing',  'HIST': 'hist', 'HIS':  'hist',  # HIS  = História (SARESP)
    'GEO':  'geo',  'CIE':  'cie',  'FILO': 'filo',  'FIL': 'filo',  # FIL = Filosofia (SARESP)
    'SOC':  'soc',  'BIO':  'bio',  'FIS':  'fis',
    'QUI':  'qui',  'FIN':  'fin',  'TEC':  'tec',
}


def _normalizar(texto):
    """Remove acentos e converte para maiúsculo."""
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return nfkd.encode('ascii', 'ignore').decode('ascii').upper().strip()


def _parse_valor(valor, multiplicar=1.0):
    """Converte string para float, aplicando multiplicador (uso: nota 0-10 → 0-100)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).replace('%', '').replace(',', '.').strip()
    try:
        f = float(s)
        return round(f * multiplicar, 1) if f > 0 else None
    except ValueError:
        return None


def _parse_percent(valor):
    return _parse_valor(valor, 1.0)


def parse_csv(conteudo_bytes):
    texto = None
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            texto = conteudo_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if texto is None:
        raise ValueError('Não foi possível decodificar o arquivo.')

    df = pd.read_csv(StringIO(texto), sep=';', dtype=str, header=0)

    cols_orig = list(df.columns)
    cols_norm = [_normalizar(c) for c in cols_orig]

    idx_turma = next((i for i, c in enumerate(cols_norm) if 'TURMA' in c), 0)

    # Detecta formato pelo conteúdo das colunas
    tem_qualidade = any('QUALIDADE' in c for c in cols_norm)
    tem_acertos   = any('ACERTO' in c for c in cols_norm)
    tem_nota_med  = any('MEDIA' in c for c in cols_norm)

    if tem_qualidade:
        return _parse_tarefas(df, cols_norm, idx_turma)
    elif tem_acertos:
        return _parse_prova_paulista(df, cols_norm, idx_turma)
    elif tem_nota_med:
        return _parse_saresp(df, cols_norm, cols_orig, idx_turma)
    else:
        return _parse_prova_paulista(df, cols_norm, idx_turma)


# ── Formato PROVA PAULISTA ─────────────────────────────────────────────────

def _parse_prova_paulista(df, cols_norm, idx_turma):
    idx_total = next((i for i, c in enumerate(cols_norm) if 'TOTAL' in c and 'ALUNO' in c), 1)
    idx_part  = next((i for i, c in enumerate(cols_norm) if 'PARTICIP' in c), 2)
    idx_acert = next((i for i, c in enumerate(cols_norm) if 'ACERTO' in c), 3)
    idx_disc_inicio = idx_acert + 1

    registros = []
    for _, row in df.iterrows():
        turma = str(row.iloc[idx_turma]).strip()
        if _linha_invalida(turma):
            continue

        try:
            total_alunos = int(float(str(row.iloc[idx_total]).replace(',', '.')))
        except (ValueError, TypeError):
            continue
        if total_alunos == 0:
            continue

        rec = {
            'turma':             turma,
            'total_alunos':      total_alunos,
            'perc_participacao': _parse_percent(row.iloc[idx_part]),
            'perc_acertos':      _parse_percent(row.iloc[idx_acert]),
        }
        for i, disc in enumerate(DISC_COLUNAS):
            col_idx = idx_disc_inicio + i
            rec[disc] = _parse_percent(row.iloc[col_idx]) if col_idx < len(row) else None
        registros.append(rec)

    return registros


# ── Formato SARESP ─────────────────────────────────────────────────────────

def _parse_saresp(df, cols_norm, cols_orig, idx_turma):
    """
    SARESP usa notas de 0-10. Convertemos ×10 para escala 0-100 uniforme.
    LPT→port, HIS→hist, FIL→filo.
    """
    idx_avaliados = next((i for i, c in enumerate(cols_norm) if 'AVALIAD' in c), 1)
    idx_media     = next((i for i, c in enumerate(cols_norm) if 'MEDIA' in c), 2)
    idx_disc_inicio = idx_media + 1

    # Detecta colunas de disciplina presentes no arquivo
    disc_cols = []
    for i in range(idx_disc_inicio, len(cols_orig)):
        chave = DISC_ALIAS.get(_normalizar(cols_orig[i]))
        if chave:
            disc_cols.append((i, chave))

    registros = []
    for _, row in df.iterrows():
        turma = str(row.iloc[idx_turma]).strip()
        if _linha_invalida(turma):
            continue

        try:
            total_alunos = int(float(str(row.iloc[idx_avaliados]).replace(',', '.')))
        except (ValueError, TypeError):
            continue
        if total_alunos == 0:
            continue

        # Nota média (0-10) → 0-100 para ficar na mesma escala da PROVA PAULISTA
        nota_media = _parse_valor(row.iloc[idx_media], multiplicar=10.0)

        rec = {
            'turma':             turma,
            'total_alunos':      total_alunos,
            'perc_participacao': None,       # SARESP não informa % de participação
            'perc_acertos':      nota_media,
        }
        for disc in DISC_COLUNAS:
            rec[disc] = None
        for col_idx, chave in disc_cols:
            rec[chave] = _parse_valor(row.iloc[col_idx], multiplicar=10.0)

        registros.append(rec)

    return registros


# ── Formato TAREFAS ───────────────────────────────────────────────────────────

def _parse_tarefas(df, cols_norm, idx_turma):
    """
    CSV de TAREFAS do SEDUC-SP.
    Colunas-chave: Matrículas Ativas, % Tarefas Realizadas, % Acertos, Índice de Qualidade (IQ).
    Armazena IQ em perc_acertos e % Tarefas Realizadas em perc_participacao.
    Não há dados por disciplina — todas as colunas de disc ficam nulas.
    """
    idx_matriculas = next((i for i, c in enumerate(cols_norm) if 'MATRICULA' in c), 1)
    idx_iq = next(
        (i for i, c in enumerate(cols_norm) if 'QUALIDADE' in c),
        None
    )
    idx_perc_tarefas = next(
        (i for i, c in enumerate(cols_norm)
         if '%' in c and 'TAREFAS' in c and 'REALIZAD' in c and 'ALUNOS' not in c),
        None
    )

    registros = []
    for _, row in df.iterrows():
        turma = str(row.iloc[idx_turma]).strip()
        if _linha_invalida(turma):
            continue

        try:
            raw = str(row.iloc[idx_matriculas]).replace('.', '').replace(',', '.').strip()
            total_alunos = int(float(raw))
        except (ValueError, TypeError):
            continue
        if total_alunos == 0:
            continue

        rec = {
            'turma':             turma,
            'total_alunos':      total_alunos,
            'perc_participacao': _parse_percent(row.iloc[idx_perc_tarefas]) if idx_perc_tarefas is not None else None,
            'perc_acertos':      _parse_percent(row.iloc[idx_iq]) if idx_iq is not None else None,
        }
        for disc in DISC_COLUNAS:
            rec[disc] = None

        registros.append(rec)

    return registros


def _linha_invalida(turma):
    t = turma.lower()
    return (not turma
            or t in ('nan', 'total', '')
            or t.startswith('filtro')
            or turma.startswith('"'))
