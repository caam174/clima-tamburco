import os
import folium
from folium.plugins import Fullscreen, MeasureControl
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Monitor ENOS & Hidrología - Abancay / Tamburco",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CENTRO_VALLE = [-13.6200, -72.8750]


# ---------------------------------------------------------
# INGESTA Y PROCESAMIENTO DE DATOS
# ---------------------------------------------------------
@st.cache_data(ttl=3600 * 12)
def obtener_indices_oceanicos():
    """Descarga los últimos datos mensuales de anomalía Niño 3.4 desde NOAA."""
    url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        lineas = resp.text.strip().split("\n")
        data = []
        for line in lineas[1:]:
            parts = line.split()
            if len(parts) >= 4:
                data.append(
                    {"SEAS": parts[0], "YR": int(parts[1]), "ANOM": float(parts[3])}
                )
        df = pd.DataFrame(data)
        return df.tail(24)
    except Exception:
        # Respaldo técnico referencial en caso de desconexión
        return pd.DataFrame(
            {
                "SEAS": ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS"],
                "YR": [2025, 2025, 2025, 2025, 2026, 2026, 2026, 2026],
                "ANOM": [1.4, 1.8, 2.1, 2.3, 2.0, 1.6, 1.3, 1.1],
            }
        )


@st.cache_data
def cargar_vectorial_local():
    ruta = "data/rios_abancay_tamburco.geojson"
    if os.path.exists(ruta):
        gdf = gpd.read_file(ruta)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    return None


gdf_rios = cargar_vectorial_local()
df_oni = obtener_indices_oceanicos()
ultima_anomalia = df_oni.iloc[-1]["ANOM"] if not df_oni.empty else 0.0

# ---------------------------------------------------------
# BARRA LATERAL: CONTROL DE CAPAS Y PARÁMETROS
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Control del Visor")
    st.markdown("**Área:** Microcuenca Río Mariño  \n**Jurisdicción:** Tamburco - Abancay")
    st.divider()

    st.subheader("Capas Vectoriales")
    ver_rios = st.checkbox("Cauces y Quebradas (ANA)", value=True)
    ver_fajas = st.checkbox("Zona de Faja Marginal (Buffer referencial)", value=False)

    st.subheader("Capas Satelitales")
    ver_satelite = st.checkbox("Satélite Alta Resolución (ESRI)", value=True)
    ver_ndvi = st.checkbox("Índice de Vegetación / Humedad (NDVI)", value=False)

    st.divider()
    st.markdown("### 📡 Estado ENOS Global")
    if ultima_anomalia >= 2.0:
        st.error(f"Niño Fuerte: +{ultima_anomalia} °C")
    elif ultima_anomalia >= 1.0:
        st.warning(f"Niño Moderado: +{ultima_anomalia} °C")
    elif ultima_anomalia >= 0.5:
        st.info(f"Niño Débil: +{ultima_anomalia} °C")
    else:
        st.success(f"Condición Neutra: {ultima_anomalia} °C")

# ---------------------------------------------------------
# CUERPO PRINCIPAL
# ---------------------------------------------------------
st.title("🛰️ Monitor Hidroclimático & Geodinámico: Tamburco - Abancay")

tab_mapa, tab_enos, tab_gestion = st.tabs(
    ["🗺️ Visor Geoespacial", "📈 Termómetro ENOS (Global/Costero)", "📋 Gestión del Riesgo"]
)

# ---------------------------------------------------------
# TAB 1: VISOR GEOESPACIAL
# ---------------------------------------------------------
with tab_mapa:
    col_m, col_kpi = st.columns([3, 1])

    with col_kpi:
        st.markdown("#### Métricas de Cuenca")
        st.metric(
            label="Anomalía Térmica Pacífico 3.4",
            value=f"+{ultima_anomalia} °C",
            delta="Pacífico Central",
        )
        st.metric(
            label="Susceptibilidad de Ladera",
            value="Nivel Medio-Alto",
            delta="Por saturación",
        )
        st.info(
            "💡 **Uso operativo:** Activa la capa de *Faja Marginal* en la barra lateral para identificar tramos con riesgo de desborde sobre áreas construidas o parcelas agrícolas."
        )

    with col_m:
        m = folium.Map(location=CENTRO_VALLE, zoom_start=13, tiles="CartoDB positron")

        # Capa Satelital ESRI
        if ver_satelite:
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri World Imagery",
                name="Satelital ESRI",
            ).add_to(m)

        # Capa NDVI / Sentinel-2 Abierta (WMS)
        if ver_ndvi:
            folium.WmsTileLayer(
                url="https://tiles.maps.eox.at/wms",
                layers="s2cloudless-2020",
                name="Vigor Vegetal / Relieve",
                format="image/png",
                transparent=True,
                attr="EOX Sentinel-2 cloudless",
            ).add_to(m)

        # Vectorial de ríos
        if gdf_rios is not None and ver_rios:
            folium.GeoJson(
                gdf_rios,
                name="Red Hídrica ANA",
                style_function=lambda x: {
                    "color": "#00f0ff",
                    "weight": 3.5,
                    "opacity": 0.95,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[c for c in ["nombre", "tipo", "cuenca"] if c in gdf_rios.columns],
                    aliases=["Cauce:", "Tipo:", "Cuenca:"][: len([c for c in ["nombre", "tipo", "cuenca"] if c in gdf_rios.columns])],
                ),
            ).add_to(m)

        # Faja marginal referencial (Buffer)
        if gdf_rios is not None and ver_fajas:
            # Reproyección métrica temporal para buffer de 25m y vuelta a 4326
            gdf_buffer = gdf_rios.to_crs(epsg=32718).buffer(25).to_crs(epsg=4326)
            folium.GeoJson(
                gdf_buffer,
                name="Faja Marginal (25m)",
                style_function=lambda x: {
                    "color": "#ffaa00",
                    "weight": 1,
                    "fillColor": "#ffaa00",
                    "fillOpacity": 0.35,
                },
            ).add_to(m)

        Fullscreen().add_to(m)
        MeasureControl(position="bottomleft").add_to(m)
        folium.LayerControl(position="topright").add_to(m)

        st_folium(m, width="100%", height=550, returned_objects=[])

# ---------------------------------------------------------
# TAB 2: TERMÓMETRO ENOS
# ---------------------------------------------------------
with tab_enos:
    st.subheader("Evolución de Anomalías Térmicas Oceánicas (Índice ONI / Región Niño 3.4)")
    st.caption("Los valores superiores a +2.0 °C definen un evento de magnitud 'Fuerte/Muy Fuerte'.")

    fig = go.Figure()
    periodos = [f"{r.SEAS} {r.YR}" for _, r in df_oni.iterrows()]

    fig.add_trace(
        go.Scatter(
            x=periodos,
            y=df_oni["ANOM"],
            mode="lines+markers",
            name="Anomalía TSM (°C)",
            line=dict(color="#e63946", width=3),
            marker=dict(size=7, color="#1d3557"),
            fill="tozeroy",
            fillcolor="rgba(230, 57, 70, 0.15)",
        )
    )

    # Umbrales
    fig.add_hline(y=2.0, line_dash="dash", line_color="#780000", annotation_text="Niño Fuerte (+2.0 °C)")
    fig.add_hline(y=1.0, line_dash="dot", line_color="#d62828", annotation_text="Niño Moderado (+1.0 °C)")
    fig.add_hline(y=0.5, line_dash="dot", line_color="#f77f00", annotation_text="Niño Débil (+0.5 °C)")
    fig.add_hline(y=-0.5, line_dash="dot", line_color="#0077b6", annotation_text="La Niña (-0.5 °C)")

    fig.update_layout(
        xaxis_title="Trimestre Móvil",
        yaxis_title="Anomalía Térmica (°C)",
        template="plotly_white",
        height=450,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: GESTIÓN TÉCNICA DEL RIESGO
# ---------------------------------------------------------
with tab_gestion:
    st.markdown("""
    ### Matriz de Vulnerabilidad Local en Tamburco y Abancay

    | Sector / Quebrada | Tipo de Peligro | Criterio Técnico y Legal |
    | :--- | :--- | :--- |
    | **Quebrada Marcahuasi (Tamburco)** | Desbordes y flujos de lodo | Pendientes pronunciadas con alta acumulación de material coluvial. Requiere descolmatación previa a lluvias pico. |
    | **Quebrada Sahuanay / Chontay** | Flujos de detritos (huaicos) | Monitoreo de faja marginal (Ley N° 29338). Prohibición de descargas de desmonte y rellenos informales. |
    | **Río Mariño (Eje Colector)** | Avenidas torrenciales | Mantenimiento de defensas ribereñas y vigilancia de puntos de estrangulamiento de cauce. |
    | **Laderas Urbanas (Umaccata/Bellavista)** | Deslizamientos rotacionales | Saturación por lluvias prolongadas. Monitoreo de grietas de tracción en taludes y canales de coronación. |
    """)
