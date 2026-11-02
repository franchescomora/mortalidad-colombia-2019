"""Aplicación web interactiva para el análisis de mortalidad en Colombia (2019).

Fuente: DANE - Estadísticas Vitales (EEVV) 2019, defunciones no fetales.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html

DATA = Path(__file__).parent / "data"

# ---------------------------------------------------------------- Datos
df = pd.read_csv(DATA / "mortalidad_2019.csv.gz",
                 dtype={"COD_DANE": str, "COD_DEPARTAMENTO": str, "COD_MUNICIPIO": str})
divipola = pd.read_csv(DATA / "divipola.csv", dtype={"COD_DANE": str, "COD_DEPARTAMENTO": str})
cie = pd.read_csv(DATA / "codigos_muerte.csv", dtype=str)

divipola["DEPARTAMENTO"] = divipola["DEPARTAMENTO"].replace(
    {"ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA": "SAN ANDRÉS Y PROVIDENCIA"})
df = df.merge(divipola[["COD_DANE", "DEPARTAMENTO", "MUNICIPIO"]], on="COD_DANE", how="left")
df["SEXO_TXT"] = df["SEXO"].map({1: "Hombre", 2: "Mujer", 3: "Indeterminado"})

# Centroide aproximado de cada departamento (promedio de sus municipios)
centroides = (divipola.groupby(["COD_DEPARTAMENTO", "DEPARTAMENTO"], as_index=False)[["LAT", "LON"]].mean())

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Rangos de GRUPO_EDAD1 según la tabla de referencia de la actividad
GRUPOS_EDAD = [
    ("Mortalidad neonatal (<1 mes)", range(0, 5)),
    ("Mortalidad infantil (1-11 meses)", range(5, 7)),
    ("Primera infancia (1-4 años)", range(7, 9)),
    ("Niñez (5-14 años)", range(9, 11)),
    ("Adolescencia (15-19 años)", range(11, 12)),
    ("Juventud (20-29 años)", range(12, 14)),
    ("Adultez temprana (30-44 años)", range(14, 17)),
    ("Adultez intermedia (45-59 años)", range(17, 20)),
    ("Vejez (60-84 años)", range(20, 25)),
    ("Longevidad (85-100+ años)", range(25, 29)),
    ("Edad desconocida", range(29, 30)),
]
MAPA_EDAD = {c: nombre for nombre, codigos in GRUPOS_EDAD for c in codigos}
ORDEN_EDAD = [g[0] for g in GRUPOS_EDAD]
df["CATEGORIA_EDAD"] = df["GRUPO_EDAD1"].map(MAPA_EDAD)

COLOR_H, COLOR_M = "#2a6f97", "#c44569"
PLANTILLA = "plotly_white"

# ---------------------------------------------------------------- Layout
app = Dash(__name__, title="Mortalidad en Colombia 2019")
server = app.server  # para gunicorn


def tarjeta(titulo, valor, id_):
    return html.Div(className="kpi", children=[html.Span(titulo), html.H3(valor, id=id_)])


def panel(grafico_id, ancho="mitad"):
    return html.Div(className=f"panel {ancho}", children=[dcc.Loading(dcc.Graph(id=grafico_id))])


app.layout = html.Div(className="contenedor", children=[
    html.Header(children=[
        html.H1("Mortalidad en Colombia · 2019"),
        html.P("Defunciones no fetales registradas por el DANE (Estadísticas Vitales). "
               "Use los filtros para explorar los datos: todos los gráficos se actualizan."),
    ]),
    html.Div(className="filtros", children=[
        html.Div([html.Label("Departamento"),
                  dcc.Dropdown(id="f-depto", multi=True, placeholder="Todos los departamentos",
                               options=sorted(df["DEPARTAMENTO"].dropna().unique()))]),
        html.Div([html.Label("Sexo"),
                  dcc.RadioItems(id="f-sexo", inline=True, value="Todos",
                                 options=["Todos", "Hombre", "Mujer"])]),
        html.Div([html.Label("Meses"),
                  dcc.RangeSlider(id="f-mes", min=1, max=12, step=1, value=[1, 12],
                                  marks={i + 1: m for i, m in enumerate(MESES)})]),
    ]),
    html.Div(className="kpis", children=[
        tarjeta("Total de muertes", "", "k-total"),
        tarjeta("Hombres", "", "k-h"),
        tarjeta("Mujeres", "", "k-m"),
        tarjeta("Homicidios", "", "k-hom"),
    ]),
    html.Div(className="grid", children=[
        panel("g-mapa"), panel("g-lineas"),
        panel("g-violentas"), panel("g-circular"),
        panel("g-apiladas", "completo"),
        panel("g-histograma", "completo"),
        html.Div(className="panel completo", children=[
            html.H4("Top 10 causas de muerte en Colombia (CIE-10)"),
            dash_table.DataTable(
                id="t-causas",
                columns=[{"name": "#", "id": "rank"}, {"name": "Código", "id": "COD_MUERTE"},
                         {"name": "Causa de muerte", "id": "DESCRIPCION"},
                         {"name": "Total de casos", "id": "TOTAL", "type": "numeric",
                          "format": {"specifier": ","}}],
                style_cell={"fontFamily": "inherit", "padding": "8px", "textAlign": "left",
                            "whiteSpace": "normal", "height": "auto"},
                style_header={"backgroundColor": "#1d3557", "color": "white", "fontWeight": "600"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#f4f6f9"}],
            ),
        ]),
    ]),
    html.Footer("Fuente: DANE – EEVV 2019 · Clasificación CIE-10 · DIVIPOLA"),
])


# ---------------------------------------------------------------- Lógica
def filtrar(deptos, sexo, meses):
    d = df[df["MES"].between(meses[0], meses[1])]
    if deptos:
        d = d[d["DEPARTAMENTO"].isin(deptos)]
    if sexo != "Todos":
        d = d[d["SEXO_TXT"] == sexo]
    return d


def estilo(fig, titulo, **kw):
    fig.update_layout(template=PLANTILLA, title=dict(text=titulo, x=0.01, font_size=16),
                      margin=dict(l=10, r=10, t=60, b=10), **kw)
    return fig


@app.callback(
    Output("k-total", "children"), Output("k-h", "children"), Output("k-m", "children"),
    Output("k-hom", "children"),
    Output("g-mapa", "figure"), Output("g-lineas", "figure"), Output("g-violentas", "figure"),
    Output("g-circular", "figure"), Output("g-apiladas", "figure"), Output("g-histograma", "figure"),
    Output("t-causas", "data"),
    Input("f-depto", "value"), Input("f-sexo", "value"), Input("f-mes", "value"),
)
def actualizar(deptos, sexo, meses):
    d = filtrar(deptos, sexo, meses)
    fmt = lambda n: f"{n:,}".replace(",", ".")

    # 1. Mapa: total de muertes por departamento
    por_dep = d.groupby("COD_DEPARTAMENTO").size().rename("MUERTES").reset_index()
    por_dep = centroides.merge(por_dep, on="COD_DEPARTAMENTO", how="inner")
    mapa = px.scatter_geo(por_dep, lat="LAT", lon="LON", size="MUERTES", color="MUERTES",
                          hover_name="DEPARTAMENTO", size_max=45,
                          color_continuous_scale="Reds",
                          hover_data={"LAT": False, "LON": False, "MUERTES": ":,"})
    mapa.update_geos(fitbounds="locations", showcountries=True, countrycolor="#999",
                     showland=True, landcolor="#f2efe9", showocean=True, oceancolor="#dbe9f4",
                     resolution=50, lataxis_range=[-4.5, 13.5], lonaxis_range=[-82, -66])
    estilo(mapa, "Distribución de muertes por departamento", coloraxis_colorbar_title="Muertes",
           height=480)

    # 2. Líneas: muertes por mes
    por_mes = d.groupby("MES").size().reindex(range(1, 13), fill_value=0).reset_index(name="MUERTES")
    por_mes["Mes"] = por_mes["MES"].map(lambda m: MESES[m - 1])
    por_mes = por_mes[por_mes["MES"].between(meses[0], meses[1])]
    lineas = px.line(por_mes, x="Mes", y="MUERTES", markers=True, text="MUERTES")
    lineas.update_traces(line_color="#1d3557", line_width=3, texttemplate="%{text:,}",
                         textposition="top center")
    estilo(lineas, "Total de muertes por mes", xaxis_title="Mes", yaxis_title="Número de muertes",
           height=480)

    # 3. Barras: 5 ciudades más violentas (homicidios X95 – arma de fuego)
    hom = d[d["COD_MUERTE"].str.startswith("X95")]
    top_v = hom.groupby("MUNICIPIO").size().nlargest(5).sort_values().reset_index(name="HOMICIDIOS")
    violentas = px.bar(top_v, x="HOMICIDIOS", y="MUNICIPIO", orientation="h", text="HOMICIDIOS",
                       color="HOMICIDIOS", color_continuous_scale="OrRd")
    violentas.update_layout(coloraxis_showscale=False)
    estilo(violentas, "5 ciudades más violentas: homicidios con arma de fuego (X95)",
           xaxis_title="Número de homicidios", yaxis_title="Ciudad", height=420)

    # 4. Circular: 10 ciudades con menor mortalidad
    por_mun = d.groupby(["MUNICIPIO", "DEPARTAMENTO"]).size().reset_index(name="MUERTES")
    por_mun["CIUDAD"] = por_mun["MUNICIPIO"].str.title() + " (" + por_mun["DEPARTAMENTO"].str.title() + ")"
    menores = por_mun.sort_values(["MUERTES", "CIUDAD"]).head(10)
    circular = px.pie(menores, names="CIUDAD", values="MUERTES", hole=0.35,
                      color_discrete_sequence=px.colors.qualitative.Pastel)
    circular.update_traces(textinfo="label+value", textposition="inside")
    estilo(circular, "10 ciudades con menor número de muertes", height=420,
           legend=dict(font_size=10))

    # 5. Barras apiladas: muertes por sexo en cada departamento
    sx = d[d["SEXO"].isin([1, 2])].groupby(["DEPARTAMENTO", "SEXO_TXT"]).size().reset_index(name="MUERTES")
    orden = sx.groupby("DEPARTAMENTO")["MUERTES"].sum().sort_values(ascending=False).index
    apiladas = px.bar(sx, x="DEPARTAMENTO", y="MUERTES", color="SEXO_TXT", barmode="stack",
                      category_orders={"DEPARTAMENTO": list(orden), "SEXO_TXT": ["Hombre", "Mujer"]},
                      color_discrete_map={"Hombre": COLOR_H, "Mujer": COLOR_M},
                      labels={"SEXO_TXT": "Sexo"})
    estilo(apiladas, "Total de muertes por sexo en cada departamento", xaxis_title="Departamento",
           yaxis_title="Número de muertes", height=520, xaxis_tickangle=-45, legend_title="Sexo")

    # 6. Histograma: distribución por ciclo de vida (GRUPO_EDAD1)
    ed = d["CATEGORIA_EDAD"].value_counts().reindex(ORDEN_EDAD, fill_value=0).reset_index()
    ed.columns = ["Grupo de edad", "MUERTES"]
    histo = go.Figure(go.Bar(x=ed["Grupo de edad"], y=ed["MUERTES"], marker_color="#457b9d",
                             text=ed["MUERTES"], texttemplate="%{text:,}", textposition="outside"))
    histo.update_layout(bargap=0.02)
    estilo(histo, "Distribución de muertes por ciclo de vida (GRUPO_EDAD1)",
           xaxis_title="Grupo de edad", yaxis_title="Número de muertes", height=480)

    # 7. Tabla: 10 principales causas de muerte
    causas = d.groupby("COD_MUERTE").size().nlargest(10).reset_index(name="TOTAL")
    causas = causas.merge(cie, on="COD_MUERTE", how="left").fillna({"DESCRIPCION": "Sin descripción"})
    causas.insert(0, "rank", range(1, len(causas) + 1))

    return (fmt(len(d)), fmt(int((d["SEXO"] == 1).sum())), fmt(int((d["SEXO"] == 2).sum())),
            fmt(int((d["MANERA_MUERTE"] == "Homicidio").sum())),
            mapa, lineas, violentas, circular, apiladas, histo, causas.to_dict("records"))


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=False)
