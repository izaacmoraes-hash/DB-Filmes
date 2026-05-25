import re
from pathlib import Path
import sys

import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))

import limpar


def normalizar_titulo(valor):
    if pd.isna(valor):
        return pd.NA

    texto = str(valor).strip().lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def criar_tabela_union(imdb_path, tfilmes_path, tcritico_path, saida_path):
    imdb = pd.read_csv(imdb_path).copy()
    tfilmes = pd.read_csv(tfilmes_path).copy()
    tcritico = pd.read_csv(tcritico_path)

    imdb["title_norm"] = imdb["Series_Title"].map(normalizar_titulo)
    imdb["year_norm"] = pd.to_numeric(imdb["Released_Year"], errors="coerce").astype("Int64")

    tfilmes["title_norm"] = tfilmes["movie_title"].map(normalizar_titulo)
    tfilmes["year_norm"] = (
        pd.to_datetime(tfilmes["original_release_date"], errors="coerce")
        .dt.year
        .astype("Int64")
    )

    filmes_unificados = imdb.merge(
        tfilmes,
        how="left",
        on=["title_norm", "year_norm"],
        suffixes=("_imdb", "_rt"),
    )
    union = filmes_unificados.merge(tcritico, how="left", on="rotten_tomatoes_link")
    union = union.drop(columns=["title_norm", "year_norm"])

    saida_path.parent.mkdir(parents=True, exist_ok=True)
    union.to_csv(saida_path, index=False)
    return union


def relacoes_entre_tabelas(imdb_path, tfilmes_path, tcritico_path):
    imdb = pd.read_csv(imdb_path, nrows=0)
    tfilmes = pd.read_csv(tfilmes_path, nrows=0)
    tcritico = pd.read_csv(tcritico_path, nrows=0)

    mapeamentos = [
        ("imdb.csv", "Series_Title",   "tfilmes.csv",  "movie_title",            "título do filme"),
        ("imdb.csv", "Released_Year",  "tfilmes.csv",  "original_release_date",  "ano de lançamento"),
        ("imdb.csv", "Runtime",        "tfilmes.csv",  "runtime",                "duração"),
        ("imdb.csv", "Genre",          "tfilmes.csv",  "genres",                 "gênero"),
        ("imdb.csv", "Director",       "tfilmes.csv",  "directors",              "diretor"),
        ("imdb.csv", "Certificate",    "tfilmes.csv",  "content_rating",         "classificação indicativa"),
        ("imdb.csv", "Overview",       "tfilmes.csv",  "movie_info",             "sinopse"),
        ("imdb.csv", "Star1",          "tfilmes.csv",  "actors",                 "elenco principal"),
        ("imdb.csv", "Star2",          "tfilmes.csv",  "actors",                 "elenco principal"),
        ("imdb.csv", "Star3",          "tfilmes.csv",  "actors",                 "elenco principal"),
        ("imdb.csv", "Star4",          "tfilmes.csv",  "actors",                 "elenco principal"),
        ("imdb.csv", "IMDB_Rating",    "tfilmes.csv",  "audience_rating",        "avaliação do público"),
        ("imdb.csv", "Meta_score",     "tfilmes.csv",  "tomatometer_rating",     "avaliação da crítica"),
        ("imdb.csv", "No_of_Votes",    "tfilmes.csv",  "audience_count",         "quantidade de votos do público"),
        ("tfilmes.csv", "rotten_tomatoes_link", "tcritico.csv", "rotten_tomatoes_link", "chave de junção filme<->crítica"),
        ("tfilmes.csv", "tomatometer_rating",   "tcritico.csv", "review_score",         "nota agregada vs. nota individual"),
        ("tfilmes.csv", "tomatometer_status",   "tcritico.csv", "review_type",          "status agregado vs. fresh/rotten individual"),
        ("tfilmes.csv", "original_release_date","tcritico.csv", "review_date",          "data do filme vs. data da crítica"),
    ]

    colunas = {
        "imdb.csv": set(imdb.columns),
        "tfilmes.csv": set(tfilmes.columns),
        "tcritico.csv": set(tcritico.columns),
    }

    linhas = []
    for tab_a, col_a, tab_b, col_b, descricao in mapeamentos:
        if col_a in colunas[tab_a] and col_b in colunas[tab_b]:
            tipo = "chave" if col_a == col_b == "rotten_tomatoes_link" else "semântica"
            linhas.append({
                "tabela_a": tab_a,
                "coluna_a": col_a,
                "tabela_b": tab_b,
                "coluna_b": col_b,
                "tipo_relacao": tipo,
                "descricao": descricao,
            })

    return pd.DataFrame(linhas)

def main(tabela):
    print("Iniciando a limpeza dos dados...")
    caminho_raiz = Path(__file__).parent.parent
    limpar.main(tabela, caminho_raiz)


if __name__ == "__main__":

    path = Path(__file__).parent
    tcritico = path / "db" / "tcritico.csv"
    tfilmes = path / "db" / "tfilmes.csv"
    imdb = path / "db" / "imdb.csv"
    union_path = path / "db" / "output" / "union.csv"


    df_relacoes = relacoes_entre_tabelas(imdb, tfilmes, tcritico)
    print("\nRelações entre as tabelas:")
    print(df_relacoes.to_string(index=False))

    df_union = criar_tabela_union(imdb, tfilmes, tcritico, union_path)
    print(f"\nTabela union criada em: {union_path}")
    print(f"Linhas da union: {len(df_union)}")


