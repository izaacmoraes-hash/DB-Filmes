import pandas as pd

from limpar import LimparCritico, LimparFilmes, LimparImdb
from explorar import normalizar_notas_tcritico
from utils import BASE_DIR, OUTPUT_DIR, normalizar_titulo


def limpar_imdb(path):
    db = LimparImdb.from_csv(path)
    db.normalizar_strings()
    db.corrigir_ano_desalinhado()
    db.extrair_runtime_minutos()
    db.normalizar_gross()
    return db.df

def limpar_tfilmes(path):
    db = LimparFilmes.from_csv(path)
    db.normalizar_strings()
    db.normalizar_content_rating()
    db.corrigir_soma_criticas()
    return db.df

def limpar_tcritico(path):
    db = LimparCritico.from_csv(path)
    db.normalizar_strings()
    db.corrigir_erros_pontuais()
    for num in list(range(1, 61)) + [5.4, 5.5, 20, 45, 50, 70, 80, 90, 95, 100, 1000]:
        db.formatar_base_10(num)
    db.converter_faixa_base_10(10, 100, 10)
    db.converter_faixa_base_10(100, 1000, 100)
    db.converter_faixa_base_10(0, 1, 0.1)
    db.alfa_to_numeric()
    return db.df

def verificar_compatibilidade(imdb, tfilmes):
    linhas = []

    runtime_imdb_ok = pd.api.types.is_numeric_dtype(imdb["Runtime"])
    runtime_rt_ok = pd.api.types.is_numeric_dtype(tfilmes["runtime"])
    linhas.append({
        "coluna_imdb": "Runtime",
        "coluna_tfilmes": "runtime",
        "status_compativel": "sim" if runtime_imdb_ok and runtime_rt_ok else "nao",
        "observacao": "Ambas numericas (minutos) apos extracao do sufixo 'min'",
    })

    certs = set(imdb["Certificate"].dropna().unique())
    ratings = set(tfilmes["content_rating"].dropna().unique())
    so_imdb = sorted(certs - ratings)
    so_rt = sorted(ratings - certs)
    linhas.append({
        "coluna_imdb": "Certificate",
        "coluna_tfilmes": "content_rating",
        "status_compativel": "parcial",
        "observacao": (
            f"So no IMDB: {so_imdb[:5]}{'...' if len(so_imdb) > 5 else ''}. "
            f"So no RT: {so_rt}"
        ),
    })

    exemplo_imdb = imdb["Genre"].dropna().iloc[0] if not imdb["Genre"].dropna().empty else ""
    exemplo_rt = tfilmes["genres"].dropna().iloc[0] if not tfilmes["genres"].dropna().empty else ""
    linhas.append({
        "coluna_imdb": "Genre",
        "coluna_tfilmes": "genres",
        "status_compativel": "nao",
        "observacao": (
            f"IMDB usa virgula simples ex: '{exemplo_imdb[:40]}'. "
            f"RT usa '&' e virgula ex: '{exemplo_rt[:40]}'"
        ),
    })

    linhas.append({
        "coluna_imdb": "Released_Year",
        "coluna_tfilmes": "original_release_date",
        "status_compativel": "parcial",
        "observacao": "IMDB guarda so o ano (int); RT guarda data completa. Merge feito extraindo dt.year do RT.",
    })

    return pd.DataFrame(linhas)

def padronizar_notas_base100(imdb, tfilmes, tcritico):
    imdb_c = imdb.copy()
    tfilmes_c = tfilmes.copy()

    imdb_c["title_norm"] = imdb_c["Series_Title"].map(normalizar_titulo)
    imdb_c["year_norm"] = pd.to_numeric(imdb_c["Released_Year"], errors="coerce").astype("Int64")

    tfilmes_c["title_norm"] = tfilmes_c["movie_title"].map(normalizar_titulo)
    tfilmes_c["year_norm"] = (
        pd.to_datetime(tfilmes_c["original_release_date"], errors="coerce")
        .dt.year
        .astype("Int64")
    )

    filmes = imdb_c.merge(
        tfilmes_c[["title_norm", "year_norm", "rotten_tomatoes_link",
                   "tomatometer_rating", "audience_rating"]],
        how="inner",
        on=["title_norm", "year_norm"],
    ).drop(columns=["title_norm", "year_norm"])

    notas_critico = normalizar_notas_tcritico(tcritico)
    media_criticos = (
        notas_critico
        .groupby("rotten_tomatoes_link", dropna=True)["review_score_base100"]
        .mean()
        .reset_index(name="media_review_score")
    )

    filmes = filmes.merge(media_criticos, how="left", on="rotten_tomatoes_link")

    filmes["imdb_rating_base100"] = pd.to_numeric(filmes["IMDB_Rating"], errors="coerce") * 10
    filmes["meta_score"] = pd.to_numeric(filmes["Meta_score"], errors="coerce")
    filmes["tomatometer_rating"] = pd.to_numeric(filmes["tomatometer_rating"], errors="coerce")
    filmes["audience_rating"] = pd.to_numeric(filmes["audience_rating"], errors="coerce")

    return filmes

def calcular_nota_media(df):
    colunas_notas = ["imdb_rating_base100", "meta_score", "tomatometer_rating",
                     "audience_rating", "media_review_score"]
    colunas_presentes = [c for c in colunas_notas if c in df.columns]

    df["nota_media"] = df[colunas_presentes].mean(axis=1, skipna=True).round(2)
    df["qtd_notas_usadas"] = df[colunas_presentes].notna().sum(axis=1)
    return df

def preparar_dados():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Limpando IMDB...")
    imdb = limpar_imdb(BASE_DIR / "imdb.csv")
    imdb.to_csv(OUTPUT_DIR / "imdb_limpo.csv", index=False)

    print("Limpando tfilmes...")
    tfilmes = limpar_tfilmes(BASE_DIR / "tfilmes.csv")
    tfilmes.to_csv(OUTPUT_DIR / "tfilmes_limpo.csv", index=False)

    print("Limpando tcritico (pode demorar)...")
    tcritico = limpar_tcritico(BASE_DIR / "tcritico.csv")
    tcritico.to_csv(OUTPUT_DIR / "tcritico_limpo.csv", index=False)

    print("\nVerificando compatibilidade entre colunas equivalentes:")
    compat = verificar_compatibilidade(imdb, tfilmes)
    print(compat.to_string(index=False))

    print("\nPadronizando notas para base 0-100 e calculando media...")
    filmes_notas = padronizar_notas_base100(imdb, tfilmes, tcritico)
    filmes_notas = calcular_nota_media(filmes_notas)

    colunas_notas = ["Series_Title", "Released_Year",
                     "imdb_rating_base100", "meta_score",
                     "tomatometer_rating", "audience_rating",
                     "media_review_score", "nota_media", "qtd_notas_usadas"]
    print("\nAmostra das notas unificadas:")
    print(filmes_notas[colunas_notas].head(10).to_string(index=False))
    print("\nEstatisticas de nota_media:")
    print(filmes_notas["nota_media"].describe().round(2))

    filmes_notas.to_csv(OUTPUT_DIR / "filmes_notas.csv", index=False)
    print(f"\nArquivos salvos em {OUTPUT_DIR}")

if __name__ == "__main__":
    preparar_dados()
