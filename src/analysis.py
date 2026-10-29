"""
Módulo de análise estatística e visualização de dados do setor elétrico.
1. Consulta o banco relacional SQLite (energy_sector.db).
2. Calcula matrizes de correlação paramétrica (Pearson) e não-paramétrica (Spearman).
3. Gera e exporta figuras em alta resolução (300 DPI) para docs/figures/.
"""
import os
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Configuração visual padronizada para relatórios acadêmicos
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8


def load_dataset_from_db(db_path: str) -> pd.DataFrame:
    """Extrai os dados históricos consolidados diretamente do SQLite via SQL."""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT f.data, f.id_submercado, d.nom_submercado, d.regiao,
               f.ear_percentual, f.ear_mwmes, f.ena_mwmed, f.ena_percentual_mlt,
               f.pld_medio, f.pld_min, f.pld_max, f.ano, f.mes, f.dia
        FROM fato_energia_daily f
        JOIN dim_submercado d ON f.id_submercado = d.id_submercado
        ORDER BY f.data, f.id_submercado;
    """
    df = pd.read_sql(query, conn, parse_dates=["data"])
    conn.close()
    return df


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula coeficientes de correlação de Pearson e Spearman juntamente
    com os p-valores de significância para cada submercado do SIN.
    """
    records = []
    submarkets = ["SE/CO", "S", "NE", "N"]

    for sub in submarkets:
        sub_df = df[df["id_submercado"] == sub]
        sub_name = sub_df["nom_submercado"].iloc[0]

        # EAR% vs PLD Médio
        p_r_ear, p_p_ear = stats.pearsonr(sub_df["ear_percentual"], sub_df["pld_medio"])
        s_r_ear, s_p_ear = stats.spearmanr(sub_df["ear_percentual"], sub_df["pld_medio"])

        # ENA% MLT vs PLD Médio
        p_r_ena, p_p_ena = stats.pearsonr(sub_df["ena_percentual_mlt"], sub_df["pld_medio"])
        s_r_ena, s_p_ena = stats.spearmanr(sub_df["ena_percentual_mlt"], sub_df["pld_medio"])

        # EAR% vs ENA% MLT
        p_r_ee, p_p_ee = stats.pearsonr(sub_df["ear_percentual"], sub_df["ena_percentual_mlt"])
        s_r_ee, s_p_ee = stats.spearmanr(sub_df["ear_percentual"], sub_df["ena_percentual_mlt"])

        records.append({
            "Submercado": sub,
            "Nome": sub_name,
            "Pearson (EAR x PLD)": round(p_r_ear, 3),
            "p-valor (Pearson EAR)": f"{p_p_ear:.1e}",
            "Spearman (EAR x PLD)": round(s_r_ear, 3),
            "p-valor (Spearman EAR)": f"{s_p_ear:.1e}",
            "Pearson (ENA x PLD)": round(p_r_ena, 3),
            "Spearman (ENA x PLD)": round(s_r_ena, 3),
            "Spearman (EAR x ENA)": round(s_r_ee, 3),
        })

    return pd.DataFrame(records)


def export_heatmaps_figure(df: pd.DataFrame, output_path: str):
    """Gera matriz 2x2 de mapas de calor de correlação de Spearman para os 4 submercados."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    submarkets = [("SE/CO", 0, 0), ("S", 0, 1), ("NE", 1, 0), ("N", 1, 1)]

    cols_map = {
        "ear_percentual": "EAR (%)",
        "ena_percentual_mlt": "ENA (% MLT)",
        "pld_medio": "PLD (R$/MWh)"
    }

    for sub, row, col in submarkets:
        ax = axes[row, col]
        sub_df = df[df["id_submercado"] == sub][["ear_percentual", "ena_percentual_mlt", "pld_medio"]].rename(columns=cols_map)
        corr_matrix = sub_df.corr(method="spearman")

        sns.heatmap(
            corr_matrix, 
            annot=True, 
            cmap="coolwarm", 
            vmin=-1, 
            vmax=1, 
            fmt=".2f", 
            ax=ax, 
            cbar=True,
            linewidths=0.5,
            annot_kws={"size": 11, "weight": "bold"}
        )
        ax.set_title(f"Submercado: {sub}", fontsize=12, pad=10, weight="bold")

    plt.suptitle("Matriz de Correlação de Spearman: Hidrologia vs. Preço (2021-2026)\n[Azul = Negativa (Inversa) | Vermelho = Positiva (Direta)]", fontsize=13, weight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Figura salva: {output_path} (300 DPI)")


def export_dual_axis_series(df: pd.DataFrame, output_path: str, submarket: str = "SE/CO"):
    """Gera gráfico de série temporal com eixo duplo (EAR% e PLD Médio)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sub_df = df[df["id_submercado"] == submarket].sort_values("data")

    fig, ax1 = plt.subplots(figsize=(14, 6))

    # Eixo 1: EAR (%)
    color1 = "#1f77b4"
    ax1.set_xlabel("Data de Referência", fontsize=11, labelpad=10)
    ax1.set_ylabel("Energia Armazenada - EAR (%)", color=color1, fontsize=11, weight="bold")
    line1 = ax1.plot(sub_df["data"], sub_df["ear_percentual"], color=color1, linewidth=1.8, label="EAR (% Reservatório)")
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_ylim(0, 105)

    # Eixo 2: PLD Médio (R$/MWh)
    ax2 = ax1.twinx()
    color2 = "#d62728"
    ax2.set_ylabel("PLD Médio Diário (R$/MWh)", color=color2, fontsize=11, weight="bold")
    line2 = ax2.plot(sub_df["data"], sub_df["pld_medio"], color=color2, linewidth=1.2, alpha=0.85, label="PLD Médio Diário")
    ax2.tick_params(axis="y", labelcolor=color2)

    # Legenda Unificada
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", frameon=True, facecolor="white", framealpha=0.9)

    sub_name = sub_df["nom_submercado"].iloc[0]
    plt.title(f"Dinâmica Histórica de Armazenamento e Preço ({sub_name}) - 2021 a 2026", fontsize=13, weight="bold", pad=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Figura salva: {output_path} (300 DPI)")


def export_scatter_relationship(df: pd.DataFrame, output_path: str):
    """Gera dispersão EAR vs PLD em matriz 2x2 colorida por ano com curva de tendência."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(15, 11), sharey=True)
    submarkets = [("SE/CO", 0, 0), ("S", 0, 1), ("NE", 1, 0), ("N", 1, 1)]

    palette = {
        2021: "#d62728", 2022: "#2ca02c", 2023: "#1f77b4",
        2024: "#ff7f0e", 2025: "#9467bd", 2026: "#8c564b"
    }

    for sub, row, col in submarkets:
        ax = axes[row, col]
        sub_df = df[df["id_submercado"] == sub].sort_values("ear_percentual").copy()
        sub_name = sub_df["nom_submercado"].iloc[0]

        sns.scatterplot(
            data=sub_df,
            x="ear_percentual",
            y="pld_medio",
            hue="ano",
            palette=palette,
            alpha=0.65,
            s=28,
            ax=ax,
            legend=(row == 0 and col == 0)
        )

        # Curva de tendência não-linear
        x_clean = sub_df["ear_percentual"].dropna()
        y_clean = sub_df["pld_medio"].dropna()
        if len(x_clean) > 10:
            poly_coeff = np.polyfit(x_clean, y_clean, deg=2)
            poly_func = np.poly1d(poly_coeff)
            x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
            ax.plot(x_line, poly_func(x_line), color="black", linestyle="-", linewidth=2.0, label="Tendência")

        ax.axhline(60.0, color="gray", linestyle="--", linewidth=0.9, alpha=0.8)
        ax.set_title(f"{sub} ({sub_name})", fontsize=12, weight="bold", pad=8)
        ax.set_xlabel("Energia Armazenada - EAR (%)", fontsize=10)
        ax.set_ylabel("PLD Médio Diário (R$/MWh)", fontsize=10)
        ax.set_xlim(0, 105)
        ax.set_ylim(0, 750)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    axes[0, 0].legend(handles, labels, title="Ano", loc="upper right", fontsize=8.5, title_fontsize=9, framealpha=0.9)

    plt.suptitle("Dispersão EAR (%) vs. PLD Médio Diário por Submercado e Ano (2021 a 2026)\n[Destaca comportamento em 'L': 2021 (Crise no Teto) vs. 2022-2023 (Abundância no Piso)]", fontsize=13, weight="bold", y=0.99)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Figura salva: {output_path} (300 DPI)")


def export_scatter_ena_pld(df: pd.DataFrame, output_path: str):
    """Gera dispersão ENA vs PLD evidenciando a sensibilidade dominante no Norte."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(15, 11), sharey=True)
    submarkets = [("SE/CO", 0, 0), ("S", 0, 1), ("NE", 1, 0), ("N", 1, 1)]

    palette = {
        2021: "#d62728", 2022: "#2ca02c", 2023: "#1f77b4",
        2024: "#ff7f0e", 2025: "#9467bd", 2026: "#8c564b"
    }

    for sub, row, col in submarkets:
        ax = axes[row, col]
        sub_df = df[df["id_submercado"] == sub].sort_values("ena_percentual_mlt").copy()
        sub_name = sub_df["nom_submercado"].iloc[0]

        sns.scatterplot(
            data=sub_df,
            x="ena_percentual_mlt",
            y="pld_medio",
            hue="ano",
            palette=palette,
            alpha=0.65,
            s=28,
            ax=ax,
            legend=(row == 0 and col == 0)
        )

        ax.axhline(60.0, color="gray", linestyle="--", linewidth=0.9, alpha=0.8)
        ax.set_title(f"{sub} ({sub_name})", fontsize=12, weight="bold", pad=8)
        ax.set_xlabel("Energia Natural Afluente - ENA (% MLT)", fontsize=10)
        ax.set_ylabel("PLD Médio Diário (R$/MWh)", fontsize=10)
        ax.set_xlim(0, 250)
        ax.set_ylim(0, 750)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    axes[0, 0].legend(handles, labels, title="Ano", loc="upper right", fontsize=8.5, title_fontsize=9, framealpha=0.9)

    plt.suptitle("Dispersão ENA (% MLT) vs. PLD Médio Diário por Submercado e Ano (2021 a 2026)", fontsize=13, weight="bold", y=0.99)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Figura salva: {output_path} (300 DPI)")


def run_statistical_analysis(db_path: str, figures_dir: str) -> pd.DataFrame:
    """Executa a rotina completa de análise estatística e geração de figuras."""
    print(f"\n{'='*70}")
    print(" INICIANDO ANÁLISE ESTATÍSTICA E GERAÇÃO DE FIGURAS")
    print(f"{'='*70}\n")

    df = load_dataset_from_db(db_path)
    print(f"-> Base carregada via SQL: {len(df)} registros.")

    print("\n--- Matriz Comparativa de Correlações ---")
    corr_summary = compute_correlations(df)
    print(corr_summary.to_string(index=False))

    print("\n--- Exportação de Figuras (docs/figures/) ---")
    export_heatmaps_figure(df, os.path.join(figures_dir, "figura_matriz_correlacao_submercados.png"))
    export_dual_axis_series(df, os.path.join(figures_dir, "figura_serie_historica_ear_pld_se_co.png"), submarket="SE/CO")
    export_scatter_relationship(df, os.path.join(figures_dir, "figura_dispersao_ear_pld.png"))
    export_scatter_ena_pld(df, os.path.join(figures_dir, "figura_dispersao_ena_pld.png"))

    print(f"\n{'='*70}")
    print(" ANÁLISE ESTATÍSTICA E FIGURAS CONCLUÍDAS COM SUCESSO!")
    print(f"{'='*70}\n")
    return corr_summary


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DB_PATH = str(PROJECT_ROOT / "data" / "processed" / "energy_sector.db")
    FIG_DIR = str(PROJECT_ROOT / "docs" / "figures")
    run_statistical_analysis(DB_PATH, FIG_DIR)