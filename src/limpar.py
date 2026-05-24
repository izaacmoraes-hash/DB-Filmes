import pandas as pd


def formatar_uma_casa(serie):
    return serie.map(lambda valor: f"{valor:.1f}").astype("string")


class LimparCritico:
    def __init__(self, df):
        self.df = df

    @classmethod
    def from_csv(cls, tabela):
        return cls(pd.read_csv(tabela))

    def corrigir_erros_pontuais(self):
        review_score = self.df["review_score"].astype("string").str.strip()
        self.df.loc[review_score == "61/00", "review_score"] = "6.1"
        self.df.loc[review_score == "4/0", "review_score"] = "4.0"
        self.df.loc[review_score == "4/3.5", "review_score"] = pd.NA
        self.df.loc[review_score == "1.0", "review_score"] = pd.NA
        return self.df

    def formatar_base_10(self, denominador):
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

    def alfa_to_numeric(self):
        review_score = self.df["review_score"].astype("string").str.strip().str.upper()
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
        self.df["review_score"] = score_convertido
        return self.df

class LimparFilmes:
    CONTENT_RATINGS_VALIDOS = {"G", "PG", "PG-13", "R", "NC-17", "NR"}
    STATUS_TOMATOMETER_VALIDOS = {"Fresh", "Rotten", "Certified-Fresh"}
    STATUS_AUDIENCE_VALIDOS = {"Upright", "Spilled"}

    def __init__(self, df):
        self.df = df

    @classmethod
    def from_csv(cls, tabela):
        return cls(pd.read_csv(tabela))

    def _selecionar(self, mask, colunas):
        cols = ["rotten_tomatoes_link", "movie_title", *colunas]
        cols = [c for c in cols if c in self.df.columns]
        return self.df.loc[mask, cols]

    def linhas_link_duplicado(self):
        link = self.df["rotten_tomatoes_link"]
        mask = link.notna() & link.duplicated(keep=False)
        return self._selecionar(mask, ["rotten_tomatoes_link"])

    def linhas_rating_fora_intervalo(self, coluna):
        valores = pd.to_numeric(self.df[coluna], errors="coerce")
        mask = valores.notna() & ((valores < 0) | (valores > 100))
        return self._selecionar(mask, [coluna])

    def linhas_contagens_negativas(self):
        colunas = [
            "tomatometer_count",
            "audience_count",
            "tomatometer_top_critics_count",
            "tomatometer_fresh_critics_count",
            "tomatometer_rotten_critics_count",
        ]
        mask = pd.Series(False, index=self.df.index)
        for col in colunas:
            valores = pd.to_numeric(self.df[col], errors="coerce")
            mask = mask | (valores.notna() & (valores < 0))
        return self._selecionar(mask, colunas)

    def linhas_runtime_invalido(self):
        runtime = pd.to_numeric(self.df["runtime"], errors="coerce")
        mask = runtime.notna() & (runtime <= 0)
        return self._selecionar(mask, ["runtime"])

    def linhas_content_rating_invalido(self):
        valores = self.df["content_rating"].astype("string").str.strip()
        mask = valores.notna() & ~valores.isin(self.CONTENT_RATINGS_VALIDOS)
        return self._selecionar(mask, ["content_rating"])

    def linhas_status_tomatometer_invalido(self):
        valores = self.df["tomatometer_status"].astype("string").str.strip()
        mask = valores.notna() & ~valores.isin(self.STATUS_TOMATOMETER_VALIDOS)
        return self._selecionar(mask, ["tomatometer_status"])

    def linhas_status_audience_invalido(self):
        valores = self.df["audience_status"].astype("string").str.strip()
        mask = valores.notna() & ~valores.isin(self.STATUS_AUDIENCE_VALIDOS)
        return self._selecionar(mask, ["audience_status"])

    def linhas_soma_criticas_errada(self):
        total = pd.to_numeric(self.df["tomatometer_count"], errors="coerce")
        fresh = pd.to_numeric(self.df["tomatometer_fresh_critics_count"], errors="coerce")
        rotten = pd.to_numeric(self.df["tomatometer_rotten_critics_count"], errors="coerce")
        validos = total.notna() & fresh.notna() & rotten.notna()
        mask = validos & (total != fresh + rotten)
        return self._selecionar(
            mask,
            [
                "tomatometer_count",
                "tomatometer_fresh_critics_count",
                "tomatometer_rotten_critics_count",
            ],
        )

    def linhas_top_critics_excedente(self):
        total = pd.to_numeric(self.df["tomatometer_count"], errors="coerce")
        top = pd.to_numeric(self.df["tomatometer_top_critics_count"], errors="coerce")
        mask = total.notna() & top.notna() & (top > total)
        return self._selecionar(
            mask, ["tomatometer_count", "tomatometer_top_critics_count"]
        )

    def linhas_coerencia_tomatometer(self):
        status = self.df["tomatometer_status"].astype("string").str.strip()
        rating = pd.to_numeric(self.df["tomatometer_rating"], errors="coerce")
        validos = status.notna() & rating.notna()
        rotten_err = validos & (status == "Rotten") & (rating >= 60)
        fresh_err = (
            validos
            & status.isin(["Fresh", "Certified-Fresh"])
            & (rating < 60)
        )
        mask = rotten_err | fresh_err
        return self._selecionar(mask, ["tomatometer_status", "tomatometer_rating"])

    def linhas_coerencia_audience(self):
        status = self.df["audience_status"].astype("string").str.strip()
        rating = pd.to_numeric(self.df["audience_rating"], errors="coerce")
        validos = status.notna() & rating.notna()
        spilled_err = validos & (status == "Spilled") & (rating >= 60)
        upright_err = validos & (status == "Upright") & (rating < 60)
        mask = spilled_err | upright_err
        return self._selecionar(mask, ["audience_status", "audience_rating"])

    def linhas_datas_invertidas(self):
        original = pd.to_datetime(self.df["original_release_date"], errors="coerce")
        streaming = pd.to_datetime(self.df["streaming_release_date"], errors="coerce")
        mask = original.notna() & streaming.notna() & (streaming < original)
        return self._selecionar(
            mask, ["original_release_date", "streaming_release_date"]
        )

    def linhas_titulo_vazio(self):
        titulo = self.df["movie_title"].astype("string").str.strip()
        mask = titulo.isna() | (titulo == "")
        return self._selecionar(mask, ["movie_title"])

    def relatorio(self):
        return {
            "link_duplicado": self.linhas_link_duplicado(),
            "tomatometer_rating_fora_0_100": self.linhas_rating_fora_intervalo(
                "tomatometer_rating"
            ),
            "audience_rating_fora_0_100": self.linhas_rating_fora_intervalo(
                "audience_rating"
            ),
            "contagens_negativas": self.linhas_contagens_negativas(),
            "runtime_invalido": self.linhas_runtime_invalido(),
            "content_rating_invalido": self.linhas_content_rating_invalido(),
            "status_tomatometer_invalido": self.linhas_status_tomatometer_invalido(),
            "status_audience_invalido": self.linhas_status_audience_invalido(),
            "soma_criticas_errada": self.linhas_soma_criticas_errada(),
            "top_critics_excedente": self.linhas_top_critics_excedente(),
            "coerencia_tomatometer": self.linhas_coerencia_tomatometer(),
            "coerencia_audience": self.linhas_coerencia_audience(),
            "datas_invertidas": self.linhas_datas_invertidas(),
            "titulo_vazio": self.linhas_titulo_vazio(),
        }

    def verificar_tudo(self):
        return all(df.empty for df in self.relatorio().values())

    def imprimir_inconsistencias(self):
        rel = self.relatorio()
        total = 0
        for nome, df in rel.items():
            if df.empty:
                continue
            total += len(df)
            print(f"\n[{nome}] {len(df)} linha(s) inconsistente(s):")
            print(df.to_string(index=True, max_rows=20))
        if total == 0:
            print("Nenhuma inconsistência encontrada.")
        else:
            print(f"\nTotal de inconsistências: {total}")
        return total == 0
    
def Critica(tabela, caminho_saida):
    "Critica"
    db = LimparCritico.from_csv(tabela)
    db.corrigir_erros_pontuais()
    for num in list(range(1, 61)) + [5.4, 5.5, 20, 45, 50, 70, 80, 90, 95, 100, 1000]:
        db.formatar_base_10(num)
    db.converter_faixa_base_10(10, 100, 10)
    db.converter_faixa_base_10(100, 1000, 100)
    db.converter_faixa_base_10(0, 1, 0.1)
    print("-------------------")
    db.alfa_to_numeric()
    db.df["review_score"] = pd.to_numeric(db.df["review_score"])
    db.df[["review_score"]].to_csv(caminho_saida / "beta.csv", index=False)
    db.df.to_csv(caminho_saida / "beta_completo.csv", index=False)
    print(db.df["review_score"].unique())


def main(tabela, caminho_saida):

    "Filmes"
    db = LimparFilmes.from_csv(tabela)
    db.imprimir_inconsistencias()       # imprime todas as linhas com problema

    # ou programaticamente:
    rel = db.relatorio()
    print(rel["soma_criticas_errada"])  # DataFrame só com linhas onde a soma falha


    "IMDB"

