import re
from pathlib import Path

import pandas as pd

BASE_DIR   = Path(__file__).parent / "db"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH    = OUTPUT_DIR / "filmes.db"


def normalizar_titulo(valor):
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    t = re.sub(r"[^a-z0-9]+", " ", str(valor).strip().lower())
    return re.sub(r"\s+", " ", t).strip()
