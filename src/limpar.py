import pandas as pd


def ver():
    print("Olá, eu sou a função ver() do módulo limpeza.py!")


def formatar_uma_casa(serie):
    return serie.map(lambda valor: f"{valor:.1f}").astype("string")

class LimparDB:
    def __init__(self, df):
        self.df = df

    def corrigir_erros_pontuais(self):
        review_score = self.df["review_score"].astype("string").str.strip()
        self.df.loc[review_score == "61/00", "review_score"] = "6.1"
        self.df.loc[review_score == "4/0", "review_score"] = "4.0"
        self.df.loc[review_score == "4/3.5", "review_score"] = pd.NA
        self.df.loc[review_score == "1.0", "review_score"] = pd.NA
        return self.df
    
    def formarata_base_10(self, denominador):
        review_score = self.df["review_score"].astype("string").str.strip()
        mask = review_score.str.fullmatch(rf"\d+(?:\.\d+)?/{denominador}")
        self.df.loc[mask, "review_score"] = (
            formatar_uma_casa(
                review_score[mask]
                .str.replace(f"/{denominador}", "", regex=False)
                .astype(float)
                .mul(10 / denominador)
            )
        )
        return self.df

    def converter_faixa_base_10(self, minimo, maximo, divisor):
        review_score = self.df["review_score"].astype("string").str.strip()
        mask = review_score.str.fullmatch(r"\d+(?:\.\d+)?")
        valores = pd.to_numeric(review_score.where(mask), errors="coerce")
        alvo = mask & valores.gt(minimo) & valores.le(maximo)
        self.df.loc[alvo, "review_score"] = formatar_uma_casa(valores[alvo].div(divisor))
        return self.df
