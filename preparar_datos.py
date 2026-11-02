"""Preprocesa los archivos del DANE (xlsx) y genera CSV livianos en data/.

Uso: python preparar_datos.py <NoFetal2019.xlsx> <CodigosDeMuerte.xlsx> <Divipola.xlsx>
"""
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

nofetal, codigos, divipola = sys.argv[1:4]

# --- Mortalidad no fetal 2019 ---
cols = ["COD_DANE", "COD_DEPARTAMENTO", "COD_MUNICIPIO", "MES", "SEXO",
        "GRUPO_EDAD1", "MANERA_MUERTE", "COD_MUERTE"]
df = pd.read_excel(nofetal, sheet_name="No_Fetales_2019", usecols=cols,
                   dtype={"COD_DANE": str, "COD_DEPARTAMENTO": str, "COD_MUNICIPIO": str})
df["COD_DANE"] = df["COD_DANE"].str.zfill(5)
df["COD_DEPARTAMENTO"] = df["COD_DEPARTAMENTO"].str.zfill(2)
df.to_csv(OUT / "mortalidad_2019.csv.gz", index=False, compression="gzip")

# --- Códigos CIE-10 (4 caracteres) ---
raw = pd.read_excel(codigos, header=None, skiprows=9, usecols=[2, 3, 4, 5])
cie = pd.concat([raw[[4, 5]].set_axis(["COD_MUERTE", "DESCRIPCION"], axis=1),
                 raw[[2, 3]].set_axis(["COD_MUERTE", "DESCRIPCION"], axis=1)]).dropna()
cie["COD_MUERTE"] = cie["COD_MUERTE"].astype(str).str.strip()
cie["DESCRIPCION"] = cie["DESCRIPCION"].astype(str).str.strip()
cie.drop_duplicates("COD_MUERTE").to_csv(OUT / "codigos_muerte.csv", index=False)

# --- DIVIPOLA: municipios + coordenadas ---
mun = pd.read_excel(divipola, sheet_name="Hoja1", dtype=str)[["COD_DANE", "COD_DEPARTAMENTO", "DEPARTAMENTO", "MUNICIPIO"]]
mun["COD_DANE"] = mun["COD_DANE"].str.zfill(5)
mun["COD_DEPARTAMENTO"] = mun["COD_DEPARTAMENTO"].str.zfill(2)

geo = pd.read_excel(divipola, sheet_name="Hoja3", header=None, skiprows=2, dtype=str).iloc[:, [2, 5, 6]]
geo.columns = ["COD_DANE", "LON", "LAT"]
geo = geo.dropna()
geo["COD_DANE"] = geo["COD_DANE"].str.zfill(5)
for c in ("LON", "LAT"):
    geo[c] = pd.to_numeric(geo[c].str.replace(",", "."), errors="coerce")
mun = mun.merge(geo, on="COD_DANE", how="left")
mun.to_csv(OUT / "divipola.csv", index=False)
print("Registros de mortalidad:", len(df), "| códigos CIE-10:", len(cie), "| municipios:", len(mun))
