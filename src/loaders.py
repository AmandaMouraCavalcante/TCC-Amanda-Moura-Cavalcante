"""
Módulo de Carregamento e Exportação de Dados (Loaders)
Centraliza a persistência das tabelas fato e dimensão em formatos CSV, Parquet e SQLite.
"""
import os
import sqlite3
from typing import Union
import pandas as pd


def save_processed_datasets(
    df_fact: pd.DataFrame, 
    df_dim: pd.DataFrame, 
    output_dir: str, 
    label: Union[int, str] = "historical",
    granularity: str = "daily",
    year: Union[int, str] = None
) -> dict:
    """
    Exporta a base consolidada (fato) em CSV e Parquet, a dimensao em CSV
    e persiste as tabelas no banco relacional SQLite (energy_sector.db).
    """
    if year is not None:
        label = year

    os.makedirs(output_dir, exist_ok=True)
    results = {}

    df_to_save = df_fact.copy()
    if "data" in df_to_save.columns:
        dt_series = pd.to_datetime(df_to_save["data"])
        if "ano" not in df_to_save.columns:
            df_to_save["ano"] = dt_series.dt.year
        if "mes" not in df_to_save.columns:
            df_to_save["mes"] = dt_series.dt.month
        if "dia" not in df_to_save.columns:
            df_to_save["dia"] = dt_series.dt.day

    # 1. Base Fato em CSV
    csv_filename = f"energy_metrics_{granularity}_{label}.csv"
    csv_fact_path = os.path.join(output_dir, csv_filename)
    df_to_save.to_csv(csv_fact_path, sep=";", index=False, encoding="utf-8")
    print(f"Salvo com sucesso: {csv_fact_path}")
    results["fact_csv"] = csv_fact_path

    # 2. Base Fato em Parquet (otimizado para Power BI)
    parquet_filename = f"energy_metrics_{granularity}_{label}.parquet"
    parquet_fact_path = os.path.join(output_dir, parquet_filename)
    df_to_save.to_parquet(parquet_fact_path, index=False)
    print(f"Salvo com sucesso: {parquet_fact_path}")
    results["fact_parquet"] = parquet_fact_path

    # 3. Tabela Dimensao em CSV
    if df_dim is not None:
        csv_dim_path = os.path.join(output_dir, "dim_submarket.csv")
        df_dim.to_csv(csv_dim_path, sep=";", index=False, encoding="utf-8")
        print(f"Salvo com sucesso: {csv_dim_path}")
        results["dim_csv"] = csv_dim_path

    # 4. Banco de Dados Relacional SQLite
    db_path = os.path.join(output_dir, "energy_sector.db")
    table_name = f"fato_energia_{granularity}"
    conn = sqlite3.connect(db_path)
    try:
        df_sql = df_to_save.copy()
        if "data" in df_sql.columns:
            df_sql["data"] = df_sql["data"].astype(str)
        df_sql.to_sql(table_name, conn, if_exists="replace", index=False)
        if df_dim is not None:
            df_dim.to_sql("dim_submercado", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()

    print(f"Banco Relacional SQLite gerado: {db_path} (Tabela: '{table_name}')")
    results["sqlite_db"] = db_path

    return results