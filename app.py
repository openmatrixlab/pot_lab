import streamlit as st
import geopandas as gpd
import os, tempfile, zipfile, base64
from modulos import pca
import folium
from streamlit_folium import st_folium
import mapclassify
from folium import plugins


# --------------------------
# 🔧 Cache para funciones pesadas
# --------------------------
@st.cache_data
def set_background_cached(image_path):
    try:
        with open(image_path, "rb") as img:
            return base64.b64encode(img.read()).decode()
    except FileNotFoundError:
        return None


@st.cache_data
def load_shapefile(zip_content):
    with tempfile.TemporaryDirectory() as tmp:
        zf_path = os.path.join(tmp, "uploaded.zip")
        with open(zf_path, "wb") as f:
            f.write(zip_content)
        with zipfile.ZipFile(zf_path, "r") as zf:
            zf.extractall(tmp)
        shp = next(
            (os.path.join(r, fname)
             for r, _, files in os.walk(tmp)
             for fname in files
             if fname.endswith(".shp") and "__MACOSX" not in r),
            None
        )
        if shp:
            gdf = gpd.read_file(shp)
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            return gdf
    return None


def create_folium_map(_gdf, field, method="Natural Breaks"):
    try:
        # Eliminar valores nulos para la clasificación
        valid_data = _gdf[field].dropna()
        if len(valid_data) == 0:
            st.error("El campo seleccionado no tiene valores válidos para mapear")
            return None

        # Selección de esquema
        if method == "Quantiles":
            scheme = mapclassify.Quantiles(valid_data, k=5)
        else:
            scheme = mapclassify.NaturalBreaks(valid_data, k=5)

        df = _gdf.copy()
        df["clase"] = scheme.yb

        # Calcular centroide con manejo de CRS
        proj = df.to_crs(epsg=3857)
        cent = proj.geometry.centroid.union_all().centroid
        cent = (
            gpd.GeoSeries([cent], crs=proj.crs)
            .to_crs(epsg=4326)
            .geometry[0]
        )

        m = folium.Map(
            location=[cent.y, cent.x],
            zoom_start=12.2,
            zoomSnap=0.1,
            zoomDelta=0.1,
            tiles="CartoDB positron",
            control_scale=True,
            prefer_canvas=True,
            width='100%',
            height='100%'
        )

        # Paleta de colores
        cmap = folium.LinearColormap(
            ["#f7fcf5", "#a1d99b", "#31a354", "#006d2c", "#00441b"],
            vmin=df[field].min(),
            vmax=df[field].max(),
            caption=field
        )

        # Función de estilo con borde delgado
        def style_fn(feat):
            v = feat["properties"][field]
            return {
                "fillOpacity": 0.7,
                "weight": 0.2,
                "color": "black",
                "fillColor": cmap(v) if v is not None else "gray"
            }

        # Capa GeoJSON con tooltip
        folium.GeoJson(
            df,
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=[field],
                aliases=[f"Valor {field}: "],
                localize=True,
                sticky=True,
                labels=True,
                style="""
                    background-color: #F0EFEF;
                    border: 1px solid black;
                    border-radius: 3px;
                    box-shadow: 3px;
                """
            )
        ).add_to(m)

        # Añadir control de paleta y plugins
        cmap.add_to(m)
        plugins.MiniMap().add_to(m)
        plugins.Fullscreen().add_to(m)

        return m

    except Exception as e:
        st.error(f"Error al generar el mapa: {str(e)}")
        return None


# --------------------------
# 🔧 Fondo sin tapar mapas
# --------------------------
def apply_background():
    enc = set_background_cached("otros/fondo.jpg")
    if enc:
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpg;base64,{enc}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .leaflet-container {{
                background: rgba(255, 255, 255, 0.9) !important;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.2);
            }}
            .folium-map {{
                width: 100% !important;
                height: 700px !important;
            }}
            .st-emotion-cache-1v0mbdj {{
                width: 100% !important;
            }}
            /* Hacemos el contenedor derecho más vertical */
            .st-emotion-cache-1wrcr25 {{
                flex-direction: column;
            }}
            .st-emotion-cache-1p1nwyz {{
                min-height: 750px;
            }}
            </style>
        """, unsafe_allow_html=True)


# --------------------------
# 🔧 Estado inicial
# --------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("gdf", None)
    ss.setdefault("loaded", False)
    ss.setdefault("show_map", False)
    ss.setdefault("map_field", None)
    ss.setdefault("map_obj", None)
    ss.setdefault("pca_done", False)


# --------------------------
# 🚀 Setup
# --------------------------
st.set_page_config(layout="wide", page_title="Análisis Espacial con PCA")
apply_background()
init_state()

st.markdown("""
    <h1 style='font-size:64x; text-align: left;
               font-weight:800; color: #2E86AB;
               font-family: "Arial Black", sans-serif;'>
      POT Lab
    </h1>
""", unsafe_allow_html=True)

# === Carga de Datos ===
st.markdown("### Carga de Datos")
c1, c2 = st.columns([1, 2])

with c1:
    uploaded = st.file_uploader("Shapefile (.zip)", type=["zip"], key="upload")
    if uploaded and st.button("Cargar shapefile", key="load_btn"):
        with st.spinner("Procesando archivo..."):
            gdf = load_shapefile(uploaded.getvalue())
            if gdf is None:
                st.error("No se encontró un archivo .shp válido dentro del ZIP")
            else:
                st.session_state.gdf = gdf
                st.session_state.loaded = True
                st.session_state.show_map = False
                st.session_state.map_field = None
                st.session_state.map_obj = None
                st.session_state.pca_done = False
                st.success(f"✅ {len(gdf)} registros cargados correctamente")

with c2:
    if st.session_state.loaded:
        df = st.session_state.gdf.drop(columns="geometry")
        st.markdown("#### Vista previa de datos")
        st.dataframe(df.head(), use_container_width=True, height=200)

# === Análisis ===
if st.session_state.loaded:
    st.markdown("---")
    st.markdown("### Análisis de Datos")
    gdf = st.session_state.gdf
    num_cols = gdf.select_dtypes("number").columns.tolist()

    # Columnas izquierda/derecha
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("#### Controles de Visualización")
        if not num_cols:
            st.warning("No se encontraron campos numéricos para visualización.")
        else:
            fld = st.selectbox("Campo para mapa:", num_cols, key="map_field_selector")
            method = st.selectbox(
                "Método de clasificación:",
                ["Natural Breaks", "Quantiles"],
                index=0,
                key="class_method"
            )

            if st.button("Generar mapa", key="gen_map_btn"):
                if gdf[fld].isnull().all():
                    st.error("El campo seleccionado no contiene valores válidos")
                else:
                    with st.spinner("Generando mapa..."):
                        st.session_state.map_field = fld
                        st.session_state.show_map = True
                        m = create_folium_map(gdf, fld, method)
                        if m:
                            st.session_state.map_obj = m
                            st.success("Mapa generado correctamente")
                        else:
                            st.error("Error al generar el mapa")

        st.markdown("---")
        st.markdown("#### Análisis PCA")
        if num_cols:
            pcs = st.multiselect(
                "Seleccione variables para PCA:",
                num_cols,
                key="pca_vars",
                help="Seleccione al menos 2 variables numéricas"
            )
            if len(pcs) >= 2:
                if st.button("Ejecutar PCA", key="pca_btn"):
                    with st.spinner("Calculando PCA..."):
                        pca.ejecutar_pca_avanzado(gdf, pcs)
                        st.session_state.pca_done = True
                        st.success("Análisis PCA completado")
            elif len(pcs) == 1:
                st.warning("Seleccione al menos 2 variables para PCA")
        else:
            st.info("No hay suficientes campos numéricos para PCA.")

        st.markdown("---")
        st.markdown("#### Clustering Espacial")
        st.info("Módulo en desarrollo", icon="ℹ️")

    with col_right:
        if st.session_state.show_map and st.session_state.map_obj:
            with st.container():
                st.markdown("#### Mapa Interactivo")
                st_folium(
                    st.session_state.map_obj,
                    width='100%',
                    height=750,
                    returned_objects=[],
                    key="folium_map",
                    zoom=13
                )

# Mensaje final
if not st.session_state.loaded:
    st.info("""
        💡 Suba un archivo ZIP que contenga un shapefile (.shp) 
        para comenzar el análisis espacial.
    """)
