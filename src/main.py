from pathlib import Path

import limpar


def main(tabela):
    print("Iniciando a limpeza dos dados...")
    caminho_raiz = Path(__file__).parent.parent
    limpar.main(tabela, caminho_raiz)


if __name__ == "__main__":

    path = Path(__file__).parent
    tcritico = path / "db" / "tcritico.csv"
    tfilmes = path / "db" / "tfilmes.csv"
    imdb = path / "db" / "imdb.csv"

    limpar.main(imdb, path/ "db" / "imdb.csv")


