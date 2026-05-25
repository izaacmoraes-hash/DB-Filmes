import re
import sys
from pathlib import Path

import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:
	sys.path.append(str(Path(__file__).resolve().parent))

from limpar import LimparCritico


BASE_DIR = Path(__file__).parent / "db"


def normalizar_titulo(valor):
	if pd.isna(valor):
		return pd.NA

	texto = str(valor).strip().lower()
	texto = re.sub(r"[^a-z0-9]+", " ", texto)
	return re.sub(r"\s+", " ", texto).strip()


def carregar_tabelas(base_dir=BASE_DIR):
	return {
		"imdb.csv": pd.read_csv(base_dir / "imdb.csv"),
		"tfilmes.csv": pd.read_csv(base_dir / "tfilmes.csv"),
		"tcritico.csv": pd.read_csv(base_dir / "tcritico.csv"),
	}


def analisar_colunas_exclusivas(tabelas):
	colunas_por_tabela = {nome: set(df.columns) for nome, df in tabelas.items()}
	linhas = []

	for nome, colunas in colunas_por_tabela.items():
		colunas_outras = set().union(
			*(cols for outra_tabela, cols in colunas_por_tabela.items() if outra_tabela != nome)
		)
		exclusivas = sorted(colunas - colunas_outras)
		linhas.append(
			{
				"tabela": nome,
				"qtd_colunas_exclusivas": len(exclusivas),
				"colunas_exclusivas": ", ".join(exclusivas) if exclusivas else "(nenhuma)",
			}
		)

	return pd.DataFrame(linhas)


def analisar_colunas_comuns_tres(tabelas):
	colunas_por_tabela = [set(df.columns) for df in tabelas.values()]
	comuns = sorted(set.intersection(*colunas_por_tabela)) if colunas_por_tabela else []

	if not comuns:
		return pd.DataFrame([{"colunas_comuns_tres": "(nenhuma)"}])

	return pd.DataFrame({"colunas_comuns_tres": comuns})


def normalizar_notas_tcritico(tcritico):
	notas = tcritico[["rotten_tomatoes_link", "review_score"]].copy()
	limpador = LimparCritico(notas)

	limpador.corrigir_erros_pontuais()
	for num in list(range(1, 61)) + [5.4, 5.5, 20, 45, 50, 70, 80, 90, 95, 100, 1000]:
		limpador.formatar_base_10(num)
	limpador.converter_faixa_base_10(10, 100, 10)
	limpador.converter_faixa_base_10(100, 1000, 100)
	limpador.converter_faixa_base_10(0, 1, 0.1)
	limpador.alfa_to_numeric()

	notas["review_score_base10"] = pd.to_numeric(limpador.df["review_score"], errors="coerce")
	notas["review_score_base100"] = notas["review_score_base10"] * 10
	return notas


def resumir_estrutura_notas(tabelas):
	imdb = tabelas["imdb.csv"]
	tfilmes = tabelas["tfilmes.csv"]
	tcritico = tabelas["tcritico.csv"]
	review_scores = normalizar_notas_tcritico(tcritico)

	linhas = [
		{
			"tabela": "imdb.csv",
			"coluna_nota": "IMDB_Rating",
			"escala": "0-10",
			"faixa_observada": f"{imdb['IMDB_Rating'].min()} a {imdb['IMDB_Rating'].max()}",
			"observacao": "Nota de publico do IMDb.",
		},
		{
			"tabela": "imdb.csv",
			"coluna_nota": "Meta_score",
			"escala": "0-100",
			"faixa_observada": f"{imdb['Meta_score'].min()} a {imdb['Meta_score'].max()}",
			"observacao": "Nota de critica agregada em outra escala.",
		},
		{
			"tabela": "tfilmes.csv",
			"coluna_nota": "tomatometer_rating",
			"escala": "0-100",
			"faixa_observada": f"{tfilmes['tomatometer_rating'].min()} a {tfilmes['tomatometer_rating'].max()}",
			"observacao": "Critica agregada do Rotten Tomatoes.",
		},
		{
			"tabela": "tfilmes.csv",
			"coluna_nota": "audience_rating",
			"escala": "0-100",
			"faixa_observada": f"{tfilmes['audience_rating'].min()} a {tfilmes['audience_rating'].max()}",
			"observacao": "Nota de publico do Rotten Tomatoes.",
		},
		{
			"tabela": "tcritico.csv",
			"coluna_nota": "review_score",
			"escala": "mista",
			"faixa_observada": (
				f"normalizada para 0-100 em {review_scores['review_score_base100'].min():.1f} "
				f"a {review_scores['review_score_base100'].max():.1f}"
			),
			"observacao": "Vem como fracao, inteiro, decimal, letra ou vazio e precisa de normalizacao.",
		},
	]

	return pd.DataFrame(linhas)


def montar_base_notas(tabelas):
	imdb = tabelas["imdb.csv"].copy()
	tfilmes = tabelas["tfilmes.csv"].copy()
	tcritico = tabelas["tcritico.csv"].copy()

	imdb["title_norm"] = imdb["Series_Title"].map(normalizar_titulo)
	imdb["year_norm"] = pd.to_numeric(imdb["Released_Year"], errors="coerce").astype("Int64")

	tfilmes["title_norm"] = tfilmes["movie_title"].map(normalizar_titulo)
	tfilmes["year_norm"] = (
		pd.to_datetime(tfilmes["original_release_date"], errors="coerce")
		.dt.year
		.astype("Int64")
	)

	filmes = imdb.merge(
		tfilmes,
		how="inner",
		on=["title_norm", "year_norm"],
		suffixes=("_imdb", "_rt"),
	)

	review_scores = normalizar_notas_tcritico(tcritico)
	media_review = (
		review_scores.groupby("rotten_tomatoes_link", dropna=True)["review_score_base100"]
		.mean()
		.reset_index(name="media_review_score_base100")
	)

	comparacao = filmes.merge(media_review, how="left", on="rotten_tomatoes_link")
	comparacao["imdb_rating_base100"] = pd.to_numeric(comparacao["IMDB_Rating"], errors="coerce") * 10
	comparacao["meta_score"] = pd.to_numeric(comparacao["Meta_score"], errors="coerce")
	comparacao["audience_rating"] = pd.to_numeric(comparacao["audience_rating"], errors="coerce")
	comparacao["tomatometer_rating"] = pd.to_numeric(
		comparacao["tomatometer_rating"], errors="coerce"
	)
	comparacao["dif_publico_imdb_vs_rt"] = (
		comparacao["imdb_rating_base100"] - comparacao["audience_rating"]
	)
	comparacao["dif_critica_imdb_vs_rt"] = (
		comparacao["meta_score"] - comparacao["tomatometer_rating"]
	)
	comparacao["dif_rt_agregado_vs_criticos"] = (
		comparacao["tomatometer_rating"] - comparacao["media_review_score_base100"]
	)
	return comparacao


def resumir_diferencas_notas(comparacao):
	metricas = [
		("IMDB publico vs Rotten audience", "dif_publico_imdb_vs_rt"),
		("IMDB critica vs Rotten tomatometer", "dif_critica_imdb_vs_rt"),
		("Rotten tomatometer vs media das criticas", "dif_rt_agregado_vs_criticos"),
	]

	linhas = []
	for descricao, coluna in metricas:
		serie = pd.to_numeric(comparacao[coluna], errors="coerce").dropna()
		linhas.append(
			{
				"comparacao": descricao,
				"qtd_filmes_comparados": int(serie.size),
				"media_diferenca": round(float(serie.mean()), 2) if not serie.empty else pd.NA,
				"mediana_diferenca": round(float(serie.median()), 2) if not serie.empty else pd.NA,
				"media_absoluta": round(float(serie.abs().mean()), 2) if not serie.empty else pd.NA,
				"maior_diferenca_absoluta": round(float(serie.abs().max()), 2) if not serie.empty else pd.NA,
			}
		)

	return pd.DataFrame(linhas)


def exemplos_diferencas_notas(comparacao):
	metricas = [
		(
			"IMDB publico vs Rotten audience",
			"dif_publico_imdb_vs_rt",
			"IMDB_Rating x 10",
			"imdb_rating_base100",
			"audience_rating",
			"audience_rating",
		),
		(
			"IMDB critica vs Rotten tomatometer",
			"dif_critica_imdb_vs_rt",
			"Meta_score",
			"meta_score",
			"tomatometer_rating",
			"tomatometer_rating",
		),
		(
			"Rotten tomatometer vs media das criticas",
			"dif_rt_agregado_vs_criticos",
			"tomatometer_rating",
			"tomatometer_rating",
			"media_review_score_base100",
			"media_review_score_base100",
		),
	]

	exemplos = []
	for descricao, coluna_dif, nome_1, coluna_1, nome_2, coluna_2 in metricas:
		base = comparacao[["Series_Title", "Released_Year", coluna_1, coluna_2, coluna_dif]].copy()
		base = base.dropna(subset=[coluna_dif])
		if base.empty:
			continue

		base = base.rename(
			columns={
				coluna_1: "valor_1",
				coluna_2: "valor_2",
				coluna_dif: "diferenca",
			}
		)
		base.insert(2, "nota_1", nome_1)
		base.insert(4, "nota_2", nome_2)
		base["diferenca_absoluta"] = base["diferenca"].abs()
		base = base.sort_values("diferenca_absoluta", ascending=False).head(5)
		base.insert(0, "comparacao", descricao)
		exemplos.append(base)

	if not exemplos:
		return pd.DataFrame()

	return pd.concat(exemplos, ignore_index=True)


def gerar_recomendacoes(tabelas, comuns_tres, comparacao):
	recomendacoes = []

	if comuns_tres.iloc[0, 0] == "(nenhuma)":
		recomendacoes.append(
			{
				"prioridade": "alta",
				"recomendacao": "Criar uma chave compartilhada entre as 3 tabelas.",
				"motivo": "Hoje o imdb.csv depende de casamento por titulo+ano, enquanto tfilmes.csv e tcritico.csv usam rotten_tomatoes_link.",
			}
		)

	recomendacoes.append(
		{
			"prioridade": "alta",
			"recomendacao": "Padronizar todas as notas em uma escala comum.",
			"motivo": "IMDB_Rating esta em 0-10, Meta_score/tomatometer/audience em 0-100 e review_score vem em formatos mistos como frações e letras.",
		}
	)

	recomendacoes.append(
		{
			"prioridade": "media",
			"recomendacao": "Separar campos multivalorados em tabelas auxiliares.",
			"motivo": "Genre, genres, actors, directors e authors carregam listas em uma unica coluna e dificultam filtros e normalizacao.",
		}
	)

	cobertura_reviews = comparacao["media_review_score_base100"].notna().mean()
	recomendacoes.append(
		{
			"prioridade": "media",
			"recomendacao": "Persistir a media das criticas individuais por filme.",
			"motivo": f"A cobertura atual da media de review_score na base comparada e de {cobertura_reviews:.1%}, o que ajuda a confrontar tomatometer com notas individuais.",
		}
	)

	recomendacoes.append(
		{
			"prioridade": "baixa",
			"recomendacao": "Montar um dicionario de dados com equivalencias semanticas.",
			"motivo": "As tabelas tem campos parecidos com nomes diferentes, como Series_Title/movie_title e Meta_score/tomatometer_rating.",
		}
	)

	return pd.DataFrame(recomendacoes)


def imprimir_secao(titulo, df):
	print(f"\n{titulo}")
	print("-" * len(titulo))
	if df.empty:
		print("Sem dados.")
		return
	print(df.to_string(index=False))


def main():
	tabelas = carregar_tabelas()
	exclusivas = analisar_colunas_exclusivas(tabelas)
	comuns_tres = analisar_colunas_comuns_tres(tabelas)
	estrutura_notas = resumir_estrutura_notas(tabelas)
	comparacao = montar_base_notas(tabelas)
	resumo_notas = resumir_diferencas_notas(comparacao)
	exemplos_notas = exemplos_diferencas_notas(comparacao)
	recomendacoes = gerar_recomendacoes(tabelas, comuns_tres, comparacao)

	imprimir_secao("1. Colunas que so existem em uma tabela", exclusivas)
	imprimir_secao("2. Colunas que existem nas tres tabelas", comuns_tres)
	imprimir_secao("3. Estrutura das notas nas 3 tabelas", estrutura_notas)
	imprimir_secao("3.1 Resumo das diferencas entre as notas", resumo_notas)
	imprimir_secao("3.2 Exemplos com maiores diferencas de notas", exemplos_notas)
	imprimir_secao("4. Recomendacoes de informacoes", recomendacoes)


if __name__ == "__main__":
	main()
