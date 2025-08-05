import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def ejecutar_pca_avanzado(gdf, columnas):
    if not columnas or len(columnas) < 2:
        st.warning("Selecciona al menos dos variables numéricas para realizar PCA.")
        return gdf

    df = gdf[columnas].dropna()
    scaler = StandardScaler()
    X = scaler.fit_transform(df)

    pca = PCA(n_components=2)
    componentes = pca.fit_transform(X)
    explained_var = pca.explained_variance_ratio_

    # --- Biplot personalizado ---
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_facecolor('white')
    circle = plt.Circle((0, 0), 1, color='grey', fill=False, linestyle='--', alpha=0.4)
    ax.add_patch(circle)
    ax.axhline(0, color='grey', linestyle='--', alpha=0.5)
    ax.axvline(0, color='grey', linestyle='--', alpha=0.5)

    for i, var in enumerate(columnas):
        x, y = pca.components_[0, i], pca.components_[1, i]
        ax.arrow(0, 0, x, y, head_width=0.03, head_length=0.05, fc='steelblue', ec='black', alpha=0.8, width=0.005)
        text = ax.text(x * 1.1, y * 1.1, var, ha='center', va='center',
                       fontsize=10, fontweight='bold', color='steelblue')
        text.set_path_effects([pe.withStroke(linewidth=1.5, foreground='white')])

    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_xlabel(f"PC1 ({explained_var[0]*100:.1f}%)", fontsize=12)
    ax.set_ylabel(f"PC2 ({explained_var[1]*100:.1f}%)", fontsize=12)
    ax.set_title("Biplot de PCA", fontsize=14)
    ax.grid(True, linestyle='--', alpha=0.3)

    st.pyplot(fig)
    plt.close(fig)

    # Guardar los resultados en el GeoDataFrame
    gdf["PC1"] = componentes[:, 0]
    gdf["PC2"] = componentes[:, 1]

    return gdf
