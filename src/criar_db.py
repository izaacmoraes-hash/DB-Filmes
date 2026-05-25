import sqlite3

import pandas as pd

from utils import normalizar_titulo, BASE_DIR, OUTPUT_DIR, DB_PATH


# ─── helpers ──────────────────────────────────────────────────────────────────

def converter_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return None if (not s or s.lower() == "nan") else s


def converter_float(v):
    s = converter_str(v)
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def converter_int(v):
    f = converter_float(v)
    return int(f) if f is not None else None


def split_lista(v):
    s = converter_str(v)
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


# ─── DDL ──────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Classificacao_Etaria (
    id_classificacao INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo           TEXT NOT NULL UNIQUE,
    descricao        TEXT
);

CREATE TABLE IF NOT EXISTS Produtora (
    id_produtora INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Publicadora (
    id_publicadora INTEGER PRIMARY KEY AUTOINCREMENT,
    nome           TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Genero (
    id_genero INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Pessoa (
    id_pessoa INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Critico (
    id_critico     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_pessoa      INTEGER NOT NULL UNIQUE REFERENCES Pessoa(id_pessoa),
    top_critic     INTEGER,
    id_publicadora INTEGER REFERENCES Publicadora(id_publicadora)
);

CREATE TABLE IF NOT EXISTS Filme (
    id_filme          INTEGER PRIMARY KEY AUTOINCREMENT,
    rt_link           TEXT UNIQUE,
    titulo            TEXT NOT NULL,
    sinopse           TEXT,
    consenso_criticos TEXT,
    ano_lancamento    INTEGER,
    data_lancamento   TEXT,
    data_streaming    TEXT,
    duracao_min       REAL,
    id_classificacao  INTEGER REFERENCES Classificacao_Etaria(id_classificacao),
    id_produtora      INTEGER REFERENCES Produtora(id_produtora)
);

CREATE TABLE IF NOT EXISTS Filme_Genero (
    id_filme  INTEGER REFERENCES Filme(id_filme),
    id_genero INTEGER REFERENCES Genero(id_genero),
    PRIMARY KEY (id_filme, id_genero)
);

CREATE TABLE IF NOT EXISTS Filme_Diretor (
    id_filme  INTEGER REFERENCES Filme(id_filme),
    id_pessoa INTEGER REFERENCES Pessoa(id_pessoa),
    PRIMARY KEY (id_filme, id_pessoa)
);

CREATE TABLE IF NOT EXISTS Filme_Roteirista (
    id_filme  INTEGER REFERENCES Filme(id_filme),
    id_pessoa INTEGER REFERENCES Pessoa(id_pessoa),
    PRIMARY KEY (id_filme, id_pessoa)
);

CREATE TABLE IF NOT EXISTS Filme_Ator (
    id_filme  INTEGER REFERENCES Filme(id_filme),
    id_pessoa INTEGER REFERENCES Pessoa(id_pessoa),
    PRIMARY KEY (id_filme, id_pessoa)
);

CREATE TABLE IF NOT EXISTS Avaliacao_RT (
    id_filme                 INTEGER PRIMARY KEY REFERENCES Filme(id_filme),
    nota_tomatometro         REAL,
    status_tomatometro       TEXT,
    total_criticas           REAL,
    criticas_positivas       INTEGER,
    criticas_negativas       INTEGER,
    criticos_top             INTEGER,
    nota_publico             REAL,
    status_publico           TEXT,
    total_avaliacoes_publico REAL
);

CREATE TABLE IF NOT EXISTS Avaliacao_IMDB (
    id_filme    INTEGER PRIMARY KEY REFERENCES Filme(id_filme),
    nota_imdb   REAL,
    metascore   REAL,
    total_votos INTEGER,
    bilheteria  REAL,
    poster_link TEXT
);

CREATE TABLE IF NOT EXISTS Critica (
    id_critica INTEGER PRIMARY KEY AUTOINCREMENT,
    id_filme   INTEGER NOT NULL REFERENCES Filme(id_filme),
    id_critico INTEGER NOT NULL REFERENCES Critico(id_critico),
    tipo       TEXT,
    nota       TEXT,
    data       TEXT,
    conteudo   TEXT
);
"""


# ─── lookup helper ────────────────────────────────────────────────────────────

def inserir_lookup(conn, tabela, coluna, valores):
    """Insere valores únicos e retorna dict {valor: id}."""
    cur = conn.cursor()
    uniq = sorted(set(v for v in valores if v))
    cur.executemany(
        f"INSERT OR IGNORE INTO {tabela} ({coluna}) VALUES (?)",
        [(v,) for v in uniq],
    )
    conn.commit()
    cur.execute(f"SELECT {coluna}, rowid FROM {tabela}")
    return dict(cur.fetchall())


# ─── tfilmes ──────────────────────────────────────────────────────────────────

def popular_tfilmes(conn, df):
    cur = conn.cursor()
    print("  classificações, produtoras, gêneros, pessoas...")

    id_rating    = inserir_lookup(conn, "Classificacao_Etaria", "codigo",
                                  df["content_rating"].dropna().unique())
    id_produtora = inserir_lookup(conn, "Produtora", "nome",
                                  df["production_company"].dropna().unique())

    generos = set()
    for v in df["genres"].dropna():
        generos.update(split_lista(v))
    id_genero = inserir_lookup(conn, "Genero", "nome", generos)

    pessoas = set()
    for col in ("directors", "authors", "actors"):
        for v in df[col].dropna():
            pessoas.update(split_lista(v))
    id_pessoa = inserir_lookup(conn, "Pessoa", "nome", pessoas)

    print("  filmes e avaliações RT...")
    filme_rows = []
    avrt_rows  = []
    for row in df.itertuples(index=False):
        titulo = converter_str(row.movie_title)
        if not titulo:
            continue
        rt        = converter_str(row.rotten_tomatoes_link)
        data_lanc = converter_str(row.original_release_date)
        ano       = int(data_lanc[:4]) if data_lanc and len(data_lanc) >= 4 else None
        cr        = converter_str(row.content_rating)
        prd       = converter_str(row.production_company)
        filme_rows.append((
            rt, titulo,
            converter_str(row.movie_info),
            converter_str(row.critics_consensus),
            ano, data_lanc,
            converter_str(row.streaming_release_date),
            converter_float(row.runtime),
            id_rating.get(cr),
            id_produtora.get(prd),
        ))
        avrt_rows.append((
            rt,
            converter_float(row.tomatometer_rating),
            converter_str(row.tomatometer_status),
            converter_float(row.tomatometer_count),
            converter_int(row.tomatometer_fresh_critics_count),
            converter_int(row.tomatometer_rotten_critics_count),
            converter_int(row.tomatometer_top_critics_count),
            converter_float(row.audience_rating),
            converter_str(row.audience_status),
            converter_float(row.audience_count),
        ))

    cur.executemany("""
        INSERT OR IGNORE INTO Filme
        (rt_link, titulo, sinopse, consenso_criticos, ano_lancamento,
         data_lancamento, data_streaming, duracao_min, id_classificacao, id_produtora)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, filme_rows)
    conn.commit()

    cur.execute("SELECT rt_link, id_filme FROM Filme WHERE rt_link IS NOT NULL")
    rt_to_id = dict(cur.fetchall())

    avrt_final = [
        (rt_to_id[r[0]], *r[1:]) for r in avrt_rows if r[0] and r[0] in rt_to_id
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO Avaliacao_RT
        (id_filme, nota_tomatometro, status_tomatometro, total_criticas,
         criticas_positivas, criticas_negativas, criticos_top,
         nota_publico, status_publico, total_avaliacoes_publico)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, avrt_final)
    conn.commit()

    print("  relacoes filme-genero, diretor, roteirista, ator...")
    fg = set(); fd = set(); fr = set(); fa = set()
    for row in df.itertuples(index=False):
        idf = rt_to_id.get(converter_str(row.rotten_tomatoes_link))
        if not idf:
            continue
        for g in split_lista(row.genres):
            ig = id_genero.get(g)
            if ig: fg.add((idf, ig))
        for p in split_lista(row.directors):
            ip = id_pessoa.get(p)
            if ip: fd.add((idf, ip))
        for p in split_lista(row.authors):
            ip = id_pessoa.get(p)
            if ip: fr.add((idf, ip))
        for p in split_lista(row.actors):
            ip = id_pessoa.get(p)
            if ip: fa.add((idf, ip))

    cur.executemany("INSERT OR IGNORE INTO Filme_Genero     VALUES (?, ?)", fg)
    cur.executemany("INSERT OR IGNORE INTO Filme_Diretor    VALUES (?, ?)", fd)
    cur.executemany("INSERT OR IGNORE INTO Filme_Roteirista VALUES (?, ?)", fr)
    cur.executemany("INSERT OR IGNORE INTO Filme_Ator       VALUES (?, ?)", fa)
    conn.commit()
    return rt_to_id, id_pessoa, id_genero


# ─── imdb ─────────────────────────────────────────────────────────────────────

def popular_imdb(conn, df, rt_to_id, id_pessoa, id_genero):
    cur = conn.cursor()

    cur.execute("SELECT id_filme, titulo, ano_lancamento FROM Filme")
    titulo_to_id = {
        (normalizar_titulo(t), a): idf
        for idf, t, a in cur.fetchall() if a
    }

    novas_p = {
        converter_str(getattr(row, col))
        for row in df.itertuples(index=False)
        for col in ("Director", "Star1", "Star2", "Star3", "Star4")
        if converter_str(getattr(row, col)) and converter_str(getattr(row, col)) not in id_pessoa
    }
    if novas_p:
        id_pessoa.update(inserir_lookup(conn, "Pessoa", "nome", novas_p))

    novos_g = {
        g
        for v in df["Genre"].dropna()
        for g in split_lista(v)
        if g not in id_genero
    }
    if novos_g:
        id_genero.update(inserir_lookup(conn, "Genero", "nome", novos_g))

    avimdb = []; fa = set(); fd = set(); fg = set()
    for row in df.itertuples(index=False):
        tn  = normalizar_titulo(row.Series_Title)
        raw = converter_str(row.Released_Year)
        try:
            ano = int(float(raw)) if raw else None
        except ValueError:
            ano = None
        idf = titulo_to_id.get((tn, ano))
        if not idf:
            continue

        avimdb.append((
            idf,
            converter_float(row.IMDB_Rating),
            converter_float(row.Meta_score),
            converter_int(row.No_of_Votes),
            converter_float(row.Gross),
            converter_str(row.Poster_Link),
        ))
        for col in ("Star1", "Star2", "Star3", "Star4"):
            v = converter_str(getattr(row, col))
            if v:
                ip = id_pessoa.get(v)
                if ip: fa.add((idf, ip))
        d = converter_str(row.Director)
        if d:
            ip = id_pessoa.get(d)
            if ip: fd.add((idf, ip))
        for g in split_lista(row.Genre):
            ig = id_genero.get(g)
            if ig: fg.add((idf, ig))

    cur.executemany("""
        INSERT OR IGNORE INTO Avaliacao_IMDB
        (id_filme, nota_imdb, metascore, total_votos, bilheteria, poster_link)
        VALUES (?, ?, ?, ?, ?, ?)
    """, avimdb)
    cur.executemany("INSERT OR IGNORE INTO Filme_Ator       VALUES (?, ?)", fa)
    cur.executemany("INSERT OR IGNORE INTO Filme_Diretor    VALUES (?, ?)", fd)
    cur.executemany("INSERT OR IGNORE INTO Filme_Genero     VALUES (?, ?)", fg)
    conn.commit()


# ─── tcritico ─────────────────────────────────────────────────────────────────

def popular_tcritico(conn, path, rt_to_id):
    cur = conn.cursor()

    criticos_uniq = pd.read_csv(
        path,
        usecols=["critic_name", "top_critic", "publisher_name"],
        dtype=str,
    ).drop_duplicates("critic_name")

    id_pub = inserir_lookup(conn, "Publicadora", "nome",
                            criticos_uniq["publisher_name"].dropna().unique())
    id_pessoa_c = inserir_lookup(conn, "Pessoa", "nome",
                                 criticos_uniq["critic_name"].dropna().unique())

    critico_rows = []
    for row in criticos_uniq.itertuples(index=False):
        nome = converter_str(row.critic_name)
        if not nome:
            continue
        ip  = id_pessoa_c.get(nome)
        if not ip:
            continue
        top = 1 if converter_str(row.top_critic) == "True" else 0
        pub = converter_str(row.publisher_name)
        critico_rows.append((ip, top, id_pub.get(pub)))

    cur.executemany(
        "INSERT OR IGNORE INTO Critico (id_pessoa, top_critic, id_publicadora) VALUES (?, ?, ?)",
        critico_rows,
    )
    conn.commit()

    cur.execute("""
        SELECT p.nome, c.id_critico FROM Critico c
        JOIN Pessoa p ON p.id_pessoa = c.id_pessoa
    """)
    id_critico = dict(cur.fetchall())

    print("  críticas em chunks de 50k...")
    total = 0
    for chunk in pd.read_csv(
        path,
        usecols=["rotten_tomatoes_link", "critic_name", "review_type",
                 "review_score", "review_date", "review_content"],
        dtype=str,
        chunksize=50_000,
    ):
        rows = []
        for row in chunk.itertuples(index=False):
            idf = rt_to_id.get(converter_str(row.rotten_tomatoes_link))
            nc  = converter_str(row.critic_name)
            idc = id_critico.get(nc) if nc else None
            if idf and idc:
                rows.append((
                    idf, idc,
                    converter_str(row.review_type),
                    converter_str(row.review_score),
                    converter_str(row.review_date),
                    converter_str(row.review_content),
                ))
        if rows:
            cur.executemany(
                "INSERT INTO Critica (id_filme, id_critico, tipo, nota, data, conteudo)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
            total += len(rows)
            print(f"    {total:,} críticas inseridas...")
    return total


# ─── resumo ───────────────────────────────────────────────────────────────────

def _imprimir_resumo(conn):
    tabelas = [
        "Classificacao_Etaria", "Produtora", "Publicadora", "Genero",
        "Pessoa", "Critico", "Filme",
        "Filme_Genero", "Filme_Diretor", "Filme_Roteirista", "Filme_Ator",
        "Avaliacao_RT", "Avaliacao_IMDB", "Critica",
    ]
    cur = conn.cursor()
    print("\n=== Linhas por tabela ===")
    for t in tabelas:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        print(f"  {t:<30} {n:>10,}")


# ─── entrada ──────────────────────────────────────────────────────────────────

def criar_banco():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print("Criando tabelas...")
    conn.executescript(DDL)

    print("\nPopulando tfilmes...")
    tfilmes = pd.read_csv(OUTPUT_DIR / "tfilmes_limpo.csv", dtype=str)
    rt_to_id, id_pessoa, id_genero = popular_tfilmes(conn, tfilmes)

    print("\nPopulando IMDB...")
    imdb = pd.read_csv(OUTPUT_DIR / "imdb_limpo.csv", dtype=str)
    popular_imdb(conn, imdb, rt_to_id, id_pessoa, id_genero)

    print("\nPopulando críticos e críticas (processo longo)...")
    popular_tcritico(conn, BASE_DIR / "tcritico.csv", rt_to_id)

    _imprimir_resumo(conn)
    conn.close()
    tamanho = DB_PATH.stat().st_size / 1e6
    print(f"\nBanco criado: {DB_PATH}  ({tamanho:.1f} MB)")


if __name__ == "__main__":
    criar_banco()
