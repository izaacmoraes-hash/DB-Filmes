import pandas as pd


def formatar_uma_casa(serie):
    return serie.map(lambda valor: f"{valor:.1f}").astype("string")


class LimparBase:
    _colunas_vazias = ["verificacao", "linha"]

    def __init__(self, df):
        self.df = df

    @classmethod
    def from_csv(cls, tabela):
        df = pd.read_csv(tabela)
        df = df.replace(r"(?i)^\s*nan\s*$", pd.NA, regex=True)
        return cls(df)

    def normalizar_strings(self):
        for col in self.df.select_dtypes(include="object").columns:
            self.df[col] = self.df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        return self.df

    def relatorio(self):
        raise NotImplementedError

    def verificar_tudo(self):
        return all(df.empty for df in self.relatorio().values())

    def resumo_df(self):
        rel = self.relatorio()
        return pd.DataFrame(
            {
                "verificacao": list(rel.keys()),
                "qtd_inconsistencias": [len(df) for df in rel.values()],
            }
        ).sort_values("qtd_inconsistencias", ascending=False).reset_index(drop=True)

    def inconsistencias_df(self):
        partes = []
        for nome, df in self.relatorio().items():
            if df.empty:
                continue
            bloco = df.copy()
            bloco.insert(0, "verificacao", nome)
            bloco.insert(1, "linha", bloco.index)
            partes.append(bloco)
        if not partes:
            return pd.DataFrame(columns=self._colunas_vazias)
        return pd.concat(partes, ignore_index=True)


class LimparCritico(LimparBase):
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
            "A+": 10.0, "A": 9.5, "A-": 9.0,
            "B+": 8.5,  "B": 8.0, "B-": 7.5,
            "C+": 6.5,  "C": 5.5, "C-": 4.5,
            "D+": 4.0,  "D": 3.5, "D-": 3.0,
            "F+": 2.0,  "F": 1.1, "F-": 0.0,
        }
        score_convertido = review_score.replace(escala_letras)
        mask = review_score.isin(escala_letras)
        score_convertido.loc[mask] = formatar_uma_casa(score_convertido.loc[mask].astype(float))
        score_convertido = score_convertido.replace("", pd.NA)
        self.df["review_score"] = score_convertido
        return self.df


class LimparFilmes(LimparBase):
    CONTENT_RATINGS_VALIDOS = {"G", "PG", "PG-13", "R", "NC-17", "NC17", "NR"}
    STATUS_TOMATOMETER_VALIDOS = {"Fresh", "Rotten", "Certified-Fresh"}
    STATUS_AUDIENCE_VALIDOS = {"Upright", "Spilled"}
    _colunas_vazias = ["verificacao", "linha", "rotten_tomatoes_link", "movie_title"]

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
        sem_nulos = self.df["content_rating"].dropna()
        invalidos = ~sem_nulos.astype(str).str.strip().isin(self.CONTENT_RATINGS_VALIDOS)
        mask = pd.Series(False, index=self.df.index)
        mask.loc[invalidos[invalidos].index] = True
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
        total = pd.to_numeric(self.df["tomatometer_count"], errors="coerce").round()
        fresh = pd.to_numeric(self.df["tomatometer_fresh_critics_count"], errors="coerce").round()
        rotten = pd.to_numeric(self.df["tomatometer_rotten_critics_count"], errors="coerce").round()
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

    def corrigir_soma_criticas(self):
        fresh = pd.to_numeric(self.df["tomatometer_fresh_critics_count"], errors="coerce").round()
        rotten = pd.to_numeric(self.df["tomatometer_rotten_critics_count"], errors="coerce").round()
        mask = fresh.notna() & rotten.notna()
        self.df.loc[mask, "tomatometer_count"] = (fresh + rotten)[mask]
        return self.df

    def normalizar_content_rating(self):
        self.df["content_rating"] = (
            self.df["content_rating"]
            .astype("string")
            .str.strip()
            .replace("NC17", "NC-17")
        )
        return self.df

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


class LimparImdb(LimparBase):
    CERTIFICADOS_VALIDOS = {
        "G", "PG", "PG-13", "R", "NC-17", "GP", "Approved", "Passed", "Unrated",
        "U", "U/A", "UA", "A", "16",
        "TV-14", "TV-MA", "TV-PG", "TV-G", "TV-Y", "TV-Y7",
    }
    ANO_MINIMO = 1888
    ANO_MAXIMO = 2026
    _colunas_vazias = ["verificacao", "linha", "Series_Title"]

    def _selecionar(self, mask, colunas):
        cols = ["Series_Title", *colunas]
        cols = [c for c in cols if c in self.df.columns]
        return self.df.loc[mask, cols]

    def linhas_linha_inteira_duplicada(self):
        mask = self.df.duplicated(keep=False)
        return self._selecionar(mask, ["Released_Year", "Director"])

    def linhas_poster_invalido(self):
        poster = self.df["Poster_Link"].astype("string").str.strip()
        mask = poster.isna() | ~poster.str.startswith("http", na=False)
        return self._selecionar(mask, ["Poster_Link"])

    def linhas_titulo_vazio(self):
        titulo = self.df["Series_Title"].astype("string").str.strip()
        mask = titulo.isna() | (titulo == "")
        return self._selecionar(mask, ["Series_Title"])

    def linhas_ano_invalido(self):
        ano = pd.to_numeric(self.df["Released_Year"], errors="coerce")
        nao_numerico = self.df["Released_Year"].notna() & ano.isna()
        fora_intervalo = ano.notna() & ((ano < self.ANO_MINIMO) | (ano > self.ANO_MAXIMO))
        mask = nao_numerico | fora_intervalo
        return self._selecionar(mask, ["Released_Year"])

    def linhas_runtime_invalido(self):
        runtime = self.df["Runtime"].astype("string").str.strip()
        mask_formato = runtime.notna() & ~runtime.str.match(r"^\d+\s*min$", na=False)
        minutos = pd.to_numeric(
            runtime.str.replace(r"\s*min$", "", regex=True), errors="coerce"
        )
        mask_valor = minutos.notna() & (minutos <= 0)
        mask = mask_formato | mask_valor
        return self._selecionar(mask, ["Runtime"])

    def linhas_imdb_rating_fora_intervalo(self):
        rating = pd.to_numeric(self.df["IMDB_Rating"], errors="coerce")
        mask = rating.notna() & ((rating < 0) | (rating > 10))
        return self._selecionar(mask, ["IMDB_Rating"])

    def linhas_meta_score_fora_intervalo(self):
        meta = pd.to_numeric(self.df["Meta_score"], errors="coerce")
        mask = meta.notna() & ((meta < 0) | (meta > 100))
        return self._selecionar(mask, ["Meta_score"])

    def linhas_no_of_votes_invalido(self):
        votos = pd.to_numeric(self.df["No_of_Votes"], errors="coerce")
        mask = votos.notna() & (votos <= 0)
        return self._selecionar(mask, ["No_of_Votes"])

    def linhas_gross_invalido(self):
        gross = self.df["Gross"].astype("string").str.replace(",", "", regex=False)
        valor = pd.to_numeric(gross, errors="coerce")
        mask = self.df["Gross"].notna() & (valor.isna() | (valor < 0))
        return self._selecionar(mask, ["Gross"])

    def linhas_certificate_invalido(self):
        sem_nulos = self.df["Certificate"].dropna()
        invalidos = ~sem_nulos.astype(str).str.strip().isin(self.CERTIFICADOS_VALIDOS)
        mask = pd.Series(False, index=self.df.index)
        mask.loc[invalidos[invalidos].index] = True
        return self._selecionar(mask, ["Certificate"])

    def linhas_genero_vazio(self):
        genero = self.df["Genre"].astype("string").str.strip()
        mask = genero.isna() | (genero == "")
        return self._selecionar(mask, ["Genre"])

    def linhas_overview_vazio(self):
        overview = self.df["Overview"].astype("string").str.strip()
        mask = overview.isna() | (overview == "")
        return self._selecionar(mask, ["Overview"])

    def linhas_diretor_vazio(self):
        diretor = self.df["Director"].astype("string").str.strip()
        mask = diretor.isna() | (diretor == "")
        return self._selecionar(mask, ["Director"])

    def linhas_elenco_incompleto(self):
        estrelas = ["Star1", "Star2", "Star3", "Star4"]
        mask = pd.Series(False, index=self.df.index)
        for col in estrelas:
            valores = self.df[col].astype("string").str.strip()
            mask = mask | valores.isna() | (valores == "")
        return self._selecionar(mask, estrelas)

    def corrigir_ano_desalinhado(self):
        ano = pd.to_numeric(self.df["Released_Year"], errors="coerce")
        mask = self.df["Released_Year"].notna() & ano.isna()
        self.df.loc[mask, "Released_Year"] = pd.NA
        return self.df

    def extrair_runtime_minutos(self):
        minutos = (
            self.df["Runtime"]
            .astype("string")
            .str.strip()
            .str.replace(r"\s*min$", "", regex=True)
        )
        self.df["Runtime"] = pd.to_numeric(minutos, errors="coerce")
        return self.df

    def normalizar_gross(self):
        gross = self.df["Gross"].astype("string").str.strip().str.replace(",", "", regex=False)
        self.df["Gross"] = pd.to_numeric(gross, errors="coerce")
        return self.df

    def relatorio(self):
        return {
            "linha_inteira_duplicada": self.linhas_linha_inteira_duplicada(),
            "poster_invalido": self.linhas_poster_invalido(),
            "titulo_vazio": self.linhas_titulo_vazio(),
            "ano_invalido": self.linhas_ano_invalido(),
            "runtime_invalido": self.linhas_runtime_invalido(),
            "imdb_rating_fora_0_10": self.linhas_imdb_rating_fora_intervalo(),
            "meta_score_fora_0_100": self.linhas_meta_score_fora_intervalo(),
            "no_of_votes_invalido": self.linhas_no_of_votes_invalido(),
            "gross_invalido": self.linhas_gross_invalido(),
            "certificate_invalido": self.linhas_certificate_invalido(),
            "genero_vazio": self.linhas_genero_vazio(),
            "overview_vazio": self.linhas_overview_vazio(),
            "diretor_vazio": self.linhas_diretor_vazio(),
            "elenco_incompleto": self.linhas_elenco_incompleto(),
        }


def executar_critico(tabela, caminho_saida):
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


def executar_filmes(tabela, caminho_saida):
    db = LimparFilmes.from_csv(tabela)
    db.corrigir_soma_criticas()
    print("Resumo de inconsistências por verificação:")
    print(db.resumo_df())
    print("\nTodas as inconsistências (DataFrame):")
    print(db.inconsistencias_df())


def executar_imdb(tabela, caminho_saida):
    db = LimparImdb.from_csv(tabela)
    print("Resumo de inconsistências por verificação:")
    print(db.resumo_df())
    print("\nTodas as inconsistências (DataFrame):")
    print(db.inconsistencias_df())


def executar_limpeza(tabela, caminho_saida):
    executar_imdb(tabela, caminho_saida)
