import sqlite3
from datetime import datetime
from config import DATABASE, DISCIPLINAS


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS vinculos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id   TEXT    NOT NULL,
            nome_professor TEXT    NOT NULL,
            disciplina     TEXT    NOT NULL,
            turma          TEXT    NOT NULL,
            ano_letivo     INTEGER NOT NULL,
            UNIQUE(disciplina, turma, ano_letivo)
        );

        CREATE TABLE IF NOT EXISTS avaliacoes (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            bimestre           INTEGER NOT NULL,
            ano                INTEGER NOT NULL,
            turma              TEXT    NOT NULL,
            tipo_avaliacao     TEXT,
            total_alunos       INTEGER,
            perc_participacao  REAL,
            perc_acertos       REAL,
            mat   REAL, port REAL, ing  REAL, hist REAL, geo  REAL,
            cie   REAL, filo REAL, soc  REAL, bio  REAL, fis  REAL,
            qui   REAL, fin  REAL, tec  REAL, arte REAL,
            rob   REAL, olp  REAL, olm  REAL,
            data_importacao    TEXT,
            UNIQUE(bimestre, ano, turma, tipo_avaliacao)
        );
    ''')
    conn.commit()

    # Migração 1: adiciona colunas novas se não existirem
    for col in ('arte REAL', 'rob REAL', 'olp REAL', 'olm REAL'):
        try:
            conn.execute(f'ALTER TABLE avaliacoes ADD COLUMN {col}')
            conn.commit()
        except Exception:
            pass  # coluna já existe

    # Migração 1b: adiciona coluna tipo_avaliacao se não existir
    try:
        conn.execute('ALTER TABLE avaliacoes ADD COLUMN tipo_avaliacao TEXT')
        conn.commit()
        conn.execute("UPDATE avaliacoes SET tipo_avaliacao='PROVA PAULISTA' WHERE tipo_avaliacao IS NULL")
        conn.commit()
    except Exception:
        pass  # coluna já existe

    # Migração 2: recria tabela com UNIQUE(bimestre, ano, turma, tipo_avaliacao)
    # SQLite não permite ALTER CONSTRAINT — precisa recriar a tabela
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='avaliacoes'"
        ).fetchone()
        sql_atual = row[0] if row else ''
        unique_parte = sql_atual[sql_atual.upper().rfind('UNIQUE'):] if 'UNIQUE' in sql_atual.upper() else ''
        if 'tipo_avaliacao' not in unique_parte:
            print('  Migração: recriando tabela avaliacoes com constraint UNIQUE correta...')
            conn.executescript('''
                CREATE TABLE avaliacoes_v2 (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    bimestre          INTEGER NOT NULL,
                    ano               INTEGER NOT NULL,
                    turma             TEXT    NOT NULL,
                    tipo_avaliacao    TEXT,
                    total_alunos      INTEGER,
                    perc_participacao REAL,
                    perc_acertos      REAL,
                    mat  REAL, port REAL, ing  REAL, hist REAL, geo  REAL,
                    cie  REAL, filo REAL, soc  REAL, bio  REAL, fis  REAL,
                    qui  REAL, fin  REAL, tec  REAL,
                    data_importacao   TEXT,
                    UNIQUE(bimestre, ano, turma, tipo_avaliacao)
                );
                INSERT OR IGNORE INTO avaliacoes_v2
                    SELECT id, bimestre, ano, turma, tipo_avaliacao,
                           total_alunos, perc_participacao, perc_acertos,
                           mat, port, ing, hist, geo, cie, filo, soc,
                           bio, fis, qui, fin, tec, data_importacao
                    FROM avaliacoes;
                DROP TABLE avaliacoes;
                ALTER TABLE avaliacoes_v2 RENAME TO avaliacoes;
            ''')
            conn.commit()
            print('  Migração concluída.')
    except Exception as e:
        print(f'  Aviso migração UNIQUE: {e}')

    conn.close()


def salvar_avaliacoes(registros, bimestre, ano, tipo_avaliacao='PROVA PAULISTA'):
    conn = get_db()
    agora = datetime.now().strftime('%d/%m/%Y %H:%M')
    salvos = 0
    for r in registros:
        try:
            conn.execute('''
                INSERT INTO avaliacoes
                    (bimestre, ano, turma, tipo_avaliacao,
                     total_alunos, perc_participacao, perc_acertos,
                     mat, port, ing, hist, geo, cie, filo, soc, bio, fis, qui, fin, tec,
                     arte, rob, olp, olm,
                     data_importacao)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(bimestre, ano, turma, tipo_avaliacao) DO UPDATE SET
                    total_alunos      = excluded.total_alunos,
                    perc_participacao = COALESCE(excluded.perc_participacao, perc_participacao),
                    perc_acertos      = COALESCE(excluded.perc_acertos,      perc_acertos),
                    mat  = COALESCE(excluded.mat,  mat),
                    port = COALESCE(excluded.port, port),
                    ing  = COALESCE(excluded.ing,  ing),
                    hist = COALESCE(excluded.hist, hist),
                    geo  = COALESCE(excluded.geo,  geo),
                    cie  = COALESCE(excluded.cie,  cie),
                    filo = COALESCE(excluded.filo, filo),
                    soc  = COALESCE(excluded.soc,  soc),
                    bio  = COALESCE(excluded.bio,  bio),
                    fis  = COALESCE(excluded.fis,  fis),
                    qui  = COALESCE(excluded.qui,  qui),
                    fin  = COALESCE(excluded.fin,  fin),
                    tec  = COALESCE(excluded.tec,  tec),
                    arte = COALESCE(excluded.arte, arte),
                    rob  = COALESCE(excluded.rob,  rob),
                    olp  = COALESCE(excluded.olp,  olp),
                    olm  = COALESCE(excluded.olm,  olm),
                    data_importacao = excluded.data_importacao
            ''', (
                bimestre, ano, r['turma'], tipo_avaliacao,
                r['total_alunos'], r['perc_participacao'], r['perc_acertos'],
                r.get('mat'), r.get('port'), r.get('ing'), r.get('hist'),
                r.get('geo'), r.get('cie'), r.get('filo'), r.get('soc'),
                r.get('bio'), r.get('fis'), r.get('qui'), r.get('fin'), r.get('tec'),
                r.get('arte'), r.get('rob'), r.get('olp'), r.get('olm'), agora
            ))
            salvos += 1
        except Exception as e:
            print(f'Erro ao salvar turma {r.get("turma")}: {e}')
    conn.commit()
    conn.close()
    return salvos


def get_stats():
    conn = get_db()
    total_vinculos = conn.execute('SELECT COUNT(*) FROM vinculos').fetchone()[0]
    total_avaliacoes = conn.execute('SELECT COUNT(*) FROM avaliacoes').fetchone()[0]
    ultima_importacao = conn.execute(
        'SELECT data_importacao FROM avaliacoes ORDER BY id DESC LIMIT 1'
    ).fetchone()
    bimestres = conn.execute(
        'SELECT DISTINCT bimestre, ano FROM avaliacoes ORDER BY ano, bimestre'
    ).fetchall()
    conn.close()
    return {
        'total_vinculos': total_vinculos,
        'total_avaliacoes': total_avaliacoes,
        'ultima_importacao': ultima_importacao[0] if ultima_importacao else None,
        'bimestres': [dict(b) for b in bimestres],
    }


def get_turmas_disponiveis():
    conn = get_db()
    rows = conn.execute('SELECT DISTINCT turma FROM avaliacoes ORDER BY turma').fetchall()
    conn.close()
    return [r['turma'] for r in rows]


def get_turmas_por_disciplina(disciplina, ano):
    """Retorna turmas que têm dados para a disciplina, com info de vínculo existente."""
    if disciplina.upper() not in DISCIPLINAS:
        return []
    disc = disciplina.lower()
    conn = get_db()
    rows = conn.execute(f'''
        SELECT DISTINCT a.turma, v.professor_id, v.nome_professor
        FROM avaliacoes a
        LEFT JOIN vinculos v
               ON a.turma     = v.turma
              AND v.disciplina = ?
              AND v.ano_letivo = ?
        WHERE a.ano = ? AND a.{disc} IS NOT NULL
        ORDER BY a.turma
    ''', (disciplina.upper(), ano, ano)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vinculos(ano_letivo=None):
    conn = get_db()
    if ano_letivo:
        rows = conn.execute(
            'SELECT * FROM vinculos WHERE ano_letivo=? ORDER BY nome_professor, disciplina, turma',
            (ano_letivo,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM vinculos ORDER BY ano_letivo DESC, nome_professor, disciplina, turma'
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cache_upsert_vinculo(vinculo_id, professor_id, nome_professor, disciplina, turma, ano_letivo):
    """Atualiza o cache local de um vínculo após gravação na planilha."""
    conn = get_db()
    conn.execute('''
        INSERT INTO vinculos (id, professor_id, nome_professor, disciplina, turma, ano_letivo)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(disciplina, turma, ano_letivo) DO UPDATE SET
            id=excluded.id,
            professor_id=excluded.professor_id,
            nome_professor=excluded.nome_professor
    ''', (vinculo_id, professor_id, nome_professor, disciplina, turma, ano_letivo))
    conn.commit()
    conn.close()


def cache_remover_vinculo(vinculo_id):
    """Remove do cache local após remoção na planilha."""
    conn = get_db()
    conn.execute('DELETE FROM vinculos WHERE id=?', (vinculo_id,))
    conn.commit()
    conn.close()


# ── Sincronização Google Sheets → SQLite ────────────────────────────────────

def _parse_float(val):
    if val is None or val == '':
        return None
    try:
        return float(str(val).replace(',', '.').replace('%', ''))
    except (ValueError, TypeError):
        return None


def _parse_int(val):
    if val is None or val == '':
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def sync_vinculos(rows):
    """Substitui o cache de vínculos com os dados da planilha."""
    conn = get_db()
    with conn:
        conn.execute('DELETE FROM vinculos')
        for r in rows:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO vinculos
                        (id, professor_id, nome_professor, disciplina, turma, ano_letivo)
                    VALUES (?,?,?,?,?,?)
                ''', (
                    _parse_int(r.get('id')),
                    str(r.get('professor_id', '')),
                    str(r.get('nome_professor', '')),
                    str(r.get('disciplina', '')),
                    str(r.get('turma', '')),
                    _parse_int(r.get('ano_letivo')),
                ))
            except Exception as e:
                print(f'Erro sync vínculo: {e}')
    conn.close()
    return len(rows)


def sync_avaliacoes(rows):
    """Sincroniza avaliações da planilha → SQLite via upsert (nunca apaga dados locais)."""
    if not rows:
        return 0
    conn = get_db()
    salvos = 0
    with conn:
        for r in rows:
            try:
                conn.execute('''
                    INSERT INTO avaliacoes
                        (id, bimestre, ano, turma, tipo_avaliacao,
                         total_alunos, perc_participacao, perc_acertos,
                         mat, port, ing, hist, geo, cie, filo, soc,
                         bio, fis, qui, fin, tec, arte, rob, olp, olm,
                         data_importacao)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(bimestre, ano, turma, tipo_avaliacao) DO UPDATE SET
                        total_alunos      = excluded.total_alunos,
                        perc_participacao = COALESCE(excluded.perc_participacao, perc_participacao),
                        perc_acertos      = COALESCE(excluded.perc_acertos,      perc_acertos),
                        mat  = COALESCE(excluded.mat,  mat),
                        port = COALESCE(excluded.port, port),
                        ing  = COALESCE(excluded.ing,  ing),
                        hist = COALESCE(excluded.hist, hist),
                        geo  = COALESCE(excluded.geo,  geo),
                        cie  = COALESCE(excluded.cie,  cie),
                        filo = COALESCE(excluded.filo, filo),
                        soc  = COALESCE(excluded.soc,  soc),
                        bio  = COALESCE(excluded.bio,  bio),
                        fis  = COALESCE(excluded.fis,  fis),
                        qui  = COALESCE(excluded.qui,  qui),
                        fin  = COALESCE(excluded.fin,  fin),
                        tec  = COALESCE(excluded.tec,  tec),
                        arte = COALESCE(excluded.arte, arte),
                        rob  = COALESCE(excluded.rob,  rob),
                        olp  = COALESCE(excluded.olp,  olp),
                        olm  = COALESCE(excluded.olm,  olm),
                        data_importacao = excluded.data_importacao
                ''', (
                    _parse_int(r.get('id')),
                    _parse_int(r.get('bimestre')),
                    _parse_int(r.get('ano')),
                    str(r.get('turma', '')),
                    str(r.get('tipo_avaliacao', '') or 'PROVA PAULISTA'),
                    _parse_int(r.get('total_alunos')),
                    _parse_float(r.get('perc_participacao')),
                    _parse_float(r.get('perc_acertos')),
                    _parse_float(r.get('mat')),  _parse_float(r.get('port')),
                    _parse_float(r.get('ing')),  _parse_float(r.get('hist')),
                    _parse_float(r.get('geo')),  _parse_float(r.get('cie')),
                    _parse_float(r.get('filo')), _parse_float(r.get('soc')),
                    _parse_float(r.get('bio')),  _parse_float(r.get('fis')),
                    _parse_float(r.get('qui')),  _parse_float(r.get('fin')),
                    _parse_float(r.get('tec')),  _parse_float(r.get('arte')),
                    _parse_float(r.get('rob')),  _parse_float(r.get('olp')),
                    _parse_float(r.get('olm')),
                    str(r.get('data_importacao', '')),
                ))
                salvos += 1
            except Exception as e:
                print(f'Erro sync avaliação: {e}')
    conn.close()
    return salvos


def get_anos_disponiveis():
    conn = get_db()
    rows = conn.execute('SELECT DISTINCT ano FROM avaliacoes ORDER BY ano DESC').fetchall()
    conn.close()
    return [r['ano'] for r in rows]


def get_tipos_disponiveis_professor(professor_id, ano):
    """Retorna quais tipos de avaliação têm dados para as turmas do professor."""
    conn = get_db()
    rows = conn.execute('''
        SELECT DISTINCT a.tipo_avaliacao
        FROM avaliacoes a
        JOIN vinculos v ON a.turma = v.turma AND v.ano_letivo = ?
        WHERE v.professor_id = ? AND a.ano = ? AND a.tipo_avaliacao IS NOT NULL
        ORDER BY a.tipo_avaliacao
    ''', (ano, professor_id, ano)).fetchall()
    conn.close()
    return [r['tipo_avaliacao'] for r in rows]


def get_professor_performance(professor_id, ano, tipo_avaliacao=None):
    conn = get_db()
    vinculos = conn.execute(
        'SELECT * FROM vinculos WHERE professor_id=? AND ano_letivo=? ORDER BY disciplina, turma',
        (professor_id, ano)
    ).fetchall()

    resultado = []
    bimestres_set = set()

    for v in vinculos:
        disc = v['disciplina'].lower()

        if tipo_avaliacao:
            avaliacoes = conn.execute(
                'SELECT * FROM avaliacoes WHERE turma=? AND ano=? AND tipo_avaliacao=? ORDER BY bimestre',
                (v['turma'], ano, tipo_avaliacao)
            ).fetchall()
        else:
            # Sem filtro: agrega por bimestre (média entre tipos quando há mais de um)
            avaliacoes = conn.execute(
                'SELECT * FROM avaliacoes WHERE turma=? AND ano=? ORDER BY tipo_avaliacao, bimestre',
                (v['turma'], ano)
            ).fetchall()

        por_bimestre = {}
        for aval in avaliacoes:
            bim = aval['bimestre']
            tipo = aval['tipo_avaliacao'] or ''
            # Chave composta quando "todos os tipos" para não sobrescrever bimestres iguais
            chave = f"{bim}|{tipo}" if not tipo_avaliacao else bim
            bimestres_set.add(bim)
            # TAREFAS não tem colunas por disciplina — usa perc_acertos (IQ) como fallback
            valor = aval[disc] if aval[disc] is not None else aval['perc_acertos']
            por_bimestre[chave] = {
                'valor': valor,
                'tipo': tipo,
                'bimestre': bim,
                'total_alunos': aval['total_alunos'],
                'participacao': aval['perc_participacao'],
                'media_escola': _media_escola(conn, disc, ano, bim, tipo_avaliacao or tipo),
            }

        resultado.append({
            'disciplina': v['disciplina'],
            'turma': v['turma'],
            'por_bimestre': por_bimestre,
            'modo_todos': not tipo_avaliacao,
        })

    conn.close()
    return resultado, sorted(bimestres_set)


def _media_escola(conn, disc, ano, bimestre, tipo_avaliacao=None):
    if tipo_avaliacao:
        row = conn.execute(
            f'SELECT AVG({disc}) FROM avaliacoes WHERE ano=? AND bimestre=? AND tipo_avaliacao=? AND {disc} > 0',
            (ano, bimestre, tipo_avaliacao)
        ).fetchone()
    else:
        row = conn.execute(
            f'SELECT AVG({disc}) FROM avaliacoes WHERE ano=? AND bimestre=? AND {disc} > 0',
            (ano, bimestre)
        ).fetchone()
    if row and row[0]:
        return round(row[0], 1)
    # Fallback para TAREFAS (sem colunas por disciplina): usa perc_acertos (IQ)
    if tipo_avaliacao:
        row = conn.execute(
            'SELECT AVG(perc_acertos) FROM avaliacoes WHERE ano=? AND bimestre=? AND tipo_avaliacao=? AND perc_acertos > 0',
            (ano, bimestre, tipo_avaliacao)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT AVG(perc_acertos) FROM avaliacoes WHERE ano=? AND bimestre=? AND perc_acertos > 0',
            (ano, bimestre)
        ).fetchone()
    return round(row[0], 1) if row and row[0] else None


def get_ranking_professores(ano, bimestre=None):
    conn = get_db()
    vinculos = conn.execute(
        'SELECT * FROM vinculos WHERE ano_letivo=?', (ano,)
    ).fetchall()

    ranking = {}
    for v in vinculos:
        disc = v['disciplina'].lower()
        pid = v['professor_id']

        if bimestre:
            rows = conn.execute(
                f'SELECT {disc} FROM avaliacoes WHERE turma=? AND ano=? AND bimestre=? AND {disc} > 0',
                (v['turma'], ano, bimestre)
            ).fetchall()
        else:
            rows = conn.execute(
                f'SELECT {disc} FROM avaliacoes WHERE turma=? AND ano=? AND {disc} > 0',
                (v['turma'], ano)
            ).fetchall()

        valores = [r[0] for r in rows if r[0] is not None]
        if valores:
            media = round(sum(valores) / len(valores), 1)
            if pid not in ranking:
                ranking[pid] = {
                    'professor_id': pid,
                    'nome': v['nome_professor'],
                    'medias': [],
                }
            ranking[pid]['medias'].append(media)

    for pid in ranking:
        medias = ranking[pid]['medias']
        ranking[pid]['media_geral'] = round(sum(medias) / len(medias), 1) if medias else 0

    conn.close()
    return sorted(ranking.values(), key=lambda x: x['media_geral'], reverse=True)
