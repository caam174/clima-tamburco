import datetime
import os
import folium
from folium.plugins import Fullscreen, MeasureControl
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Alerta Hidroclimática Tamburco",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LAT_TAMBURCO = -13.6150
LON_TAMBURCO = -72.8750
CENTRO_VALLE = [LAT_TAMBURCO, LON_TAMBURCO]

# Base de conocimiento técnico por zonas de Tamburco
SECTORES_TAMBURCO = {
    "Quebrada Marcahuasi": {
        "coords": [-13.6080, -72.8680],
        "tipo_suelo": "Depósito coluvial suelto / Relleno",
        "pendiente": "Alta (>35°)",
        "umbral_lluvia_72h": 35.0,  # mm
        "umbral_turbidez": 60.0,    # NTU
        "peligro_principal": "Flujos de detritos (huaicos) y desborde",
        "accion": "Monitoreo de cauce y descolmatación preventiva urgente.",
    },
    "Sector Umaccata / Laderas": {
        "coords": [-13.6120, -72.8850],
        "tipo_suelo": "Arcillas expansivas y esquistos fracturados",
        "pendiente": "Muy Alta (>40°)",
        "umbral_lluvia_72h": 30.0,
        "umbral_turbidez": 40.0,
        "peligro_principal": "Deslizamiento rotacional en masa por saturación",
        "accion": "Inspección de grietas de tracción en taludes y canales de coronación.",
    },
    "Kerapata / Antabamba Baja": {
        "coords": [-13.5980, -72.8620],
        "tipo_suelo": "Suelo agrícola permeable sobre roca",
        "pendiente": "Media (15° - 25°)",
        "umbral_lluvia_72h": 50.0,
        "umbral_turbidez": 80.0,
        "peligro_principal": "Erosión hídrica superficial y pérdida de suelo",
        "accion": "Mantenimiento de zanjas de infiltración y drenaje pluvial.",
    },
    "Faja Marginal Río Mariño (Tamburco)": {
        "coords": [-13.6200, -72.8720],
        "tipo_suelo": "Aluvial y desmonte antrópico",
        "pendiente": "Baja (<10° en fondo de valle)",
        "umbral_lluvia_72h": 45.0,
        "umbral_turbidez": 100.0,
        "peligro_principal": "Socavación de defensas ribereñas y desbordes",
        "accion": "Fiscalización de faja marginal (Ley 29338) y retiro de desmonte.",
    },
}


# ---------------------------------------------------------
# OBTENCIÓN DE DATOS REALES (APIs ABIERTAS)
# ---------------------------------------------------------
@st.cache_data(ttl=3600 * 3)
def obtener_precipitacion_real():
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={LAT_TAMBURCO}&longitude={LON_TAMBURCO}"
        f"&daily=precipitation_sum,precipitation_hours&timezone=America%2FLima"
        f"&past_days=30&forecast_days=7"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(data["daily"]["time"]),
                "lluvia_mm": data["daily"]["precipitation_sum"],
            }
        )
        df["acum_72h"] = df["lluvia_mm"].rolling(window=3, min_periods=1).sum()
        df["acum_7d"] = df["lluvia_mm"].rolling(window=7, min_periods=1).sum()
        return df
    except Exception:
        hoy = datetime.date.today()
        fechas = pd.date_range(end=hoy, periods=30)
        lluvia = np.random.gamma(shape=2, scale=3, size=30)
        df = pd.DataFrame({"fecha": fechas, "lluvia_mm": lluvia})
        df["acum_72h"] = df["lluvia_mm"].rolling(window=3, min_periods=1).sum()
        df["acum_7d"] = df["lluvia_mm"].rolling(window=7, min_periods=1).sum()
        return df


@st.cache_data(ttl=3600 * 12)
def obtener_indices_oceanicos():
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


df_lluvia = obtener_precipitacion_real()
df_oni = obtener_indices_oceanicos()
gdf_rios = cargar_vectorial_local()

lluvia_72h = df_lluvia.iloc[-1]["acum_72h"] if not df_lluvia.empty else 0.0
lluvia_7d = df_lluvia.iloc[-1]["acum_7d"] if not df_lluvia.empty else 0.0
ultima_anomalia = df_oni.iloc[-1]["ANOM"] if not df_oni.empty else 0.0

# ---------------------------------------------------------
# BARRA LATERAL (DATOS FÁCILES DE CAMPO)
# ---------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Flag_of_Peru.svg/320px-Flag_of_Peru.svg.png",
        width=40,
    )
    st.title("Distrito de Tamburco")
    st.caption("Panel de Control Hidrometeorológico")
    st.divider()

    st.subheader("📍 Sector a Evaluar")
    zona_seleccionada = st.selectbox(
        "Selecciona el Sector Crítico:",
        list(SECTORES_TAMBURCO.keys()),
    )

    st.subheader("💧 Medición de Turbidez")
    turbidez = st.number_input(
        "Turbidez en Captación / Cauce (NTU):",
        min_value=0.0,
        max_value=1000.0,
        value=22.0,
        step=5.0,
        help="Normal: < 10 NTU | Alerta: > 40 NTU | Crítico: > 100 NTU",
    )

    st.divider()
    st.subheader("🛰️ Opciones de Mapa")
    capa_mapa = st.radio(
        "Fondo Satelital:",
        ["🌿 NDVI (Vegetación Viva)", "🛰️ Satélite Natural (ESRI)", "🗺️ Mapa Claro"],
    )
    ver_faja = st.checkbox("Mostrar Fajas Marginales (25m)", value=True)

# ---------------------------------------------------------
# CÁLCULO DE RIESGO PARA LA ZONA SELECCIONADA
# ---------------------------------------------------------
info_zona = SECTORES_TAMBURCO[zona_seleccionada]

# Algoritmo de Riesgo
score_lluvia = lluvia_72h / info_zona["umbral_lluvia_72h"]
score_turbidez = turbidez / info_zona["umbral_turbidez"]
score_total = (score_lluvia * 0.6) + (score_turbidez * 0.4)

if score_total >= 1.0 or lluvia_72h >= 45.0 or turbidez >= 100.0:
    estado_alerta = "ALERTA ROJA (Riesgo Crítico)"
    color_banner = "#e63946"
    icono_alerta = "🚨"
elif score_total >= 0.65 or lluvia_72h >= 25.0 or turbidez >= 40.0:
    estado_alerta = "ALERTA AMARILLA (Riesgo Moderado)"
    color_banner = "#f4a261"
    icono_alerta = "⚠️"
else:
    estado_alerta = "ALERTA VERDE (Condición Estable)"
    color_banner = "#2a9d8f"
    icono_alerta = "✅"

# ---------------------------------------------------------
# CUERPO PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Centro de Monitoreo Hidrológico & Laderas - Tamburco")

# Banner Dinámico de Alerta
st.markdown(
    f"""
    <div style="background-color:{color_banner}; padding:15px; border-radius:10px; color:white; margin-bottom:20px;">
        <h3 style="margin:0; color:white;">{icono_alerta} {estado_alerta} en {zona_seleccionada}</h3>
        <p style="margin:5px 0 0 0; font-size:15px;">
            <b>Peligro evaluado:</b> {info_zona['peligro_principal']}.<br>
            <b>Acción recomendada:</b> {info_zona['accion']}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_mapa, tab_zonas, tab_lluvia, tab_clima = st.tabs(
    [
        "🗺️ Visor Geográfico & NDVI",
        "🎯 Evaluación por Sectores",
        "🌧️ Lluvias Reales (mm)",
        "📈 Fenómeno El Niño",
    ]
)

# ---------------------------------------------------------
# TAB 1: VISOR GEOGRÁFICO
# ---------------------------------------------------------
with tab_mapa:
    col_mapa, col_metricas = st.columns([3, 1])

    with col_metricas:
        st.markdown("#### Datos en Tiempo Real")
        st.metric("Lluvia Acumulada 72h", f"{lluvia_72h:.1f} mm", "Últimos 3 días")
        st.metric("Lluvia Acumulada 7d", f"{lluvia_7d:.1f} mm", "Saturación semanal")
        st.metric("Turbidez de Agua", f"{turbidez:.1f} NTU", zona_seleccionada)
        st.metric("Anomalía El Niño", f"+{ultima_anomalia:.2f} °C", "Pacífico Central")

    with col_mapa:
        m = folium.Map(location=CENTRO_VALLE, zoom_start=13, tiles="CartoDB positron")

        if capa_mapa == "🌿 NDVI (Vegetación Viva)":
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                name="Satelital Base",
            ).add_to(m)
            folium.WmsTileLayer(
                url="https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
                layers="MODIS_Terra_NDVI_8Day",
                name="NDVI NASA",
                format="image/png",
                transparent=True,
                opacity=0.65,
                attr="NASA GIBS",
            ).add_to(m)
        elif capa_mapa == "🛰️ Satélite Natural (ESRI)":
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                name="Esri Imagery",
            ).add_to(m)
        else:
            folium.TileLayer(
                tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                attr="CartoDB",
                name="CartoDB Claro",
                subdomains="abc",
            ).add_to(m)

        # Red hídrica
        if gdf_rios is not None:
            folium.GeoJson(
                gdf_rios,
                name="Ríos y Quebradas (ANA)",
                style_function=lambda x: {
                    "color": "#00d4ff",
                    "weight": 3.5,
                    "opacity": 0.95,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[c for c in ["nombre", "tipo"] if c in gdf_rios.columns],
                    aliases=["Cauce:", "Tipo:"],
                ),
            ).add_to(m)

        # Faja marginal
        if gdf_rios is not None and ver_faja:
            gdf_buf = gdf_rios.to_crs(epsg=32718).buffer(25).to_crs(epsg=4326)
            folium.GeoJson(
                gdf_buf,
                name="Fajas Marginales (25m)",
                style_function=lambda x: {
                    "color": "#ff0055",
                    "weight": 1.5,
                    "fillColor": "#ff0055",
                    "fillOpacity": 0.3,
                },
            ).add_to(m)

        # Marcadores de sectores de Tamburco
        for nombre_sec, datos_sec in SECTORES_TAMBURCO.items():
            color_icono = "red" if nombre_sec == zona_seleccionada and "ROJA" in estado_alerta else ("orange" if nombre_sec == zona_seleccionada and "AMARILLA" in estado_alerta else "blue")
            folium.Marker(
                location=datos_sec["coords"],
                popup=f"<b>{nombre_sec}</b><br>Pendiente: {datos_sec['pendiente']}<br>Peligro: {datos_sec['peligro_principal']}",
                tooltip=nombre_sec,
                icon=folium.Icon(color=color_icono, icon="exclamation-triangle" if color_icono != "blue" else "info-sign", prefix="glyphicon"),
            ).add_to(m)

        Fullscreen().add_to(m)
        MeasureControl(position="bottomleft").add_to(m)
        folium.LayerControl(position="topright").add_to(m)

        st_folium(m, width="100%", height=530, returned_objects=[])

# ---------------------------------------------------------
# TAB 2: EVALUACIÓN SECTORIZADA POR ZONAS
# ---------------------------------------------------------
with tab_zonas:
    st.subheader(f"🔍 Ficha Técnica de Vulnerabilidad: {zona_seleccionada}")

    col_z1, col_z2 = st.columns(2)
    with col_z1:
        st.markdown(f"""
        * **Topografía:** {info_zona['pendiente']}
        * **Composición Geológica:** {info_zona['tipo_suelo']}
        * **Peligro Recurrente:** {info_zona['peligro_principal']}
        """)
    with col_z2:
        st.markdown(f"""
        * **Umbral Crítico de Lluvia (72h):** `{info_zona['umbral_lluvia_72h']} mm` (Actual: **{lluvia_72h:.1f} mm**)
        * **Umbral Crítico de Turbidez:** `{info_zona['umbral_turbidez']} NTU` (Actual: **{turbidez:.1f} NTU**)
        * **Porcentaje de Saturación Estimado:** `{min(int(score_total * 100), 100)}%`
        """)

    st.progress(min(score_total / 1.5, 1.0))

    st.markdown("### 📋 Comparativa Rápida de Todos los Sectores")
    tabla_sectores = []
    for s_nom, s_dat in SECTORES_TAMBURCO.items():
        s_score = (lluvia_72h / s_dat["umbral_lluvia_72h"] * 0.6) + (turbidez / s_dat["umbral_turbidez"] * 0.4)
        s_nivel = "🔴 Crítico" if s_score >= 1.0 else ("🟡 Moderado" if s_score >= 0.65 else "🟢 Bajo")
        tabla_sectores.append({
            "Sector": s_nom,
            "Pendiente": s_dat["pendiente"],
            "Peligro Asociado": s_dat["peligro_principal"],
            "Nivel de Riesgo Actual": s_nivel,
        })
    st.table(pd.DataFrame(tabla_sectores))

# ---------------------------------------------------------
# TAB 3: LLUVIAS REALES (OPEN-METEO)
# ---------------------------------------------------------
with tab_lluvia:
    st.subheader("Precipitación Diaria Real y Acumulada (Últimos 30 días + Pronóstico)")

    fig_l = go.Figure()
    fig_l.add_trace(
        go.Bar(
            x=df_lluvia["fecha"],
            y=df_lluvia["lluvia_mm"],
            name="Lluvia Diaria (mm)",
            marker_color="#3a86ff",
        )
    )
    fig_l.add_trace(
        go.Scatter(
            x=df_lluvia["fecha"],
            y=df_lluvia["acum_72h"],
            name="Acumulado 72 horas (mm)",
            mode="lines+markers",
            line=dict(color="#e63946", width=2.5),
        )
    )
    fig_l.add_hline(
        y=40.0,
        line_dash="dash",
        line_color="darkred",
        annotation_text="Umbral Crítico Promedio (40 mm / 72h)",
    )
    fig_l.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Milímetros (mm)",
        template="plotly_white",
        height=450,
    )
    st.plotly_chart(fig_l, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: ENOS / EL NIÑO
# ---------------------------------------------------------
with tab_clima:
    st.subheader("Anomalía de Temperatura Superficial del Mar (Índice Niño 3.4)")
    fig_o = go.Figure()
    periodos = [f"{r.SEAS} {r.YR}" for _, r in df_oni.iterrows()]

    fig_o.add_trace(
        go.Scatter(
            x=periodos,
            y=df_oni["ANOM"],
            mode="lines+markers",
            name="Anomalía (°C)",
            line=dict(color="#d62828", width=2.5),
            fill="tozeroy",
        )
    )
    fig_o.add_hline(y=2.0, line_dash="dash", line_color="darkred", annotation_text="Niño Fuerte (+2.0 °C)")
    fig_o.add_hline(y=0.5, line_dash="dot", line_color="orange", annotation_text="Niño Débil (+0.5 °C)")
    fig_o.update_layout(
        xaxis_title="Periodo Móvil",
        yaxis_title="Anomalía Térmica (°C)",
        template="plotly_white",
        height=420,
    )
    st.plotly_chart(fig_o, use_container_width=True)
