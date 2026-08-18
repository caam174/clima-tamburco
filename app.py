import os
import folium
from folium.plugins import Fullscreen, MeasureControl
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium

# Configuración básica de la ventana
st.set_page_config(
    page_title="Monitor Hídrico - Abancay y Tamburco",
    page_icon="💧",
    layout="wide",
)

# Coordenadas centrales entre Abancay y Tamburco
CENTRO_VALLE = [-13.6200, -72.8750]


@st.cache_data
def cargar_rios():
    ruta = "data/rios_abancay_tamburco.geojson"
    if os.path.exists(ruta):
        gdf = gpd.read_file(ruta)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    return None


st.title("💧 Monitor de Quebradas y Cauces: Abancay - Tamburco")
st.caption(
    "Vigilancia hidrológica focalizada en la microcuenca del Río Mariño y afluentes."
)

gdf_local = cargar_rios()

# Dividimos la pantalla: Mapa a la izquierda, información a la derecha
col_mapa, col_info = st.columns([3, 1])

with col_info:
    st.markdown("### 📌 Cauces Principales")
    st.markdown("""
    * **Río Mariño:** Eje colector.
    * **Quebrada Sahuanay / Chontay**
    * **Quebrada Marcahuasi (Tamburco)**
    """)
    if gdf_local is not None:
        st.success(f"Ríos cargados: {len(gdf_local)} tramos.")
    else:
        st.info("Coloca el archivo de ríos en la carpeta 'data/'.")

with col_mapa:
    # Crear mapa base
    m = folium.Map(location=CENTRO_VALLE, zoom_start=13, tiles="CartoDB positron")

    # Agregar capa satelital
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satélite ESRI",
    ).add_to(m)

    # Dibujar los ríos en color celeste brillante si el archivo existe
    if gdf_local is not None:
        folium.GeoJson(
            gdf_local,
            name="Ríos y Quebradas",
            style_function=lambda x: {
                "color": "#00d4ff",
                "weight": 3,
                "opacity": 0.9,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    c
                    for c in ["Name", "NOMBRE", "Nombre", "nombre"]
                    if c in gdf_local.columns
                ],
                aliases=["Nombre:"],
            )
            if any(
                c in gdf_local.columns
                for c in ["Name", "NOMBRE", "Nombre", "nombre"]
            )
            else None,
        ).add_to(m)

    Fullscreen().add_to(m)
    MeasureControl(position="bottomleft").add_to(m)
    folium.LayerControl(position="topright").add_to(m)

    st_folium(m, width="100%", height=550, returned_objects=[])