from pathlib import Path
import pandas as pd

import limpar

def formatar_uma_casa(serie):
    return serie.map(lambda valor: f"{valor:.1f}").astype("string")


def converter_fracao_base_10(df, denominador):
    review_score = df["review_score"].astype("string").str.strip()
    mask = review_score.str.fullmatch(rf"\d+(?:\.\d+)?/{denominador}")
    df.loc[mask, "review_score"] = (
        formatar_uma_casa(
        review_score[mask]
        .str.replace(f"/{denominador}", "", regex=False)
        .astype(float)
        .mul(10 / denominador)
        )
    )
    return df



def alfa_to_numeric(df):
    review_score = df["review_score"].astype("string").str.strip().str.upper()
    review_score = review_score.str.replace(r"([A-F])\s+([+-])", r"\1\2", regex=True)
    escala_letras = {
        "A+": 10.0,
        "A": 9.5,
        "A-": 9.0,
        "B+": 8.5,
        "B": 8.0,
        "B-": 7.5,
        "C+": 6.5,
        "C": 5.5,
        "C-": 4.5,
        "D+": 4.0,
        "D": 3.5,
        "D-": 3.0,
        "F+": 2.0,
        "F": 1.1,
        "F-": 0.0,
    }
    score_convertido = review_score.replace(escala_letras)
    mask = review_score.isin(escala_letras)
    score_convertido.loc[mask] = formatar_uma_casa(score_convertido.loc[mask].astype(float))
    score_convertido = score_convertido.replace("", pd.NA)
    df["review_score"] = score_convertido
    return df

def padronizar(tabela):
    df = pd.read_csv(tabela)
    for num in range(1, 61):
        df = converter_fracao_base_10(df, num)

    df = converter_fracao_base_10(df, 5.4)
    df = converter_fracao_base_10(df, 5.5)
    df = converter_fracao_base_10(df, 20)
    df = converter_fracao_base_10(df, 45)
    df = converter_fracao_base_10(df, 50)
    df = converter_fracao_base_10(df, 70)
    df = converter_fracao_base_10(df, 80)
    df = converter_fracao_base_10(df, 90)
    df = converter_fracao_base_10(df, 95)
    df = converter_fracao_base_10(df, 100)
    df = converter_fracao_base_10(df, 1000)
    limpar_db = limpar.LimparDB(df)
    limpar_db.converter_faixa_base_10(10, 100, 10)
    limpar_db.converter_faixa_base_10(100, 1000, 100)
    limpar_db.converter_faixa_base_10(0, 1, 0.1)
    
    print("-------------------")
    df = alfa_to_numeric(df)
    df["review_score"] = pd.to_numeric(df["review_score"])
    caminho_saida = Path(__file__).parent.parent / "beta.csv"
    df[["review_score"]].to_csv(caminho_saida, index=False)
    df.to_csv(Path(__file__).parent.parent / "beta_completo.csv", index=False)  
    print(df["review_score"].unique())

def main(tabela):
    print("Iniciando a limpeza dos dados...")



if __name__ == "__main__":
    limpar.ver()

    path = Path(__file__).parent
    tcritico = path / "db" / "tcritico.csv"
    tfilmes = path / "db" / "tfilmes.csv"
    imdb = path / "db" / "imdb.csv"

    main(tcritico)