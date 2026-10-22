"""
Pipeline integrado de dados de energia (ONS e CCEE).
Orquestra o ciclo de ETL:
1. Extração: Coleta dados brutos de EAR, ENA e PLD (2021 a 2026).
2. Transformação: Limpeza, padronização de tipos e cruzamento das bases.
3. Validação: Checagem de limites numéricos, ausência de nulos e consistência.
4. Carga: Exportação anual e consolidada em Parquet, CSV e SQLite.
"""
import os
import sys
from pathlib import Path
from typing import Union, List

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd
from src.extractors import fetch_energy_data, get_current_year
from src.transformers import (
    clean_ear_data,
    clean_ena_data,
    clean_pld_data,
    aggregate_pld_daily,
    merge_energy_datasets,
    validate_processed_data,
    build_submarket_dimension,
)
from src.loaders import save_processed_datasets


def run_pipeline(
    years: Union[int, List[int], range] = None, 
    force: bool = False,
    granularity: str = "daily"
) -> dict:
    """
    Executa o pipeline completo de ETL para um ou múltiplos anos (padrão: 2021 a 2026).
    Adota granularidade diária como padrão da base consolidada (adequando o PLD ao EAR/ENA).
    """
    if years is None:
        years = list(range(2021, get_current_year() + 1))
    elif isinstance(years, int):
        years = [years]
    else:
        years = list(years)

    raw_dir = str(PROJECT_ROOT / "data" / "raw")
    processed_dir = str(PROJECT_ROOT / "data" / "processed")

    print(f"\n{'='*70}")
    print(f" INICIANDO PIPELINE DE DADOS SETORIAIS (ANOS: {years})")
    print(f" GRANULARIDADE ALVO: {granularity.upper()}")
    print(f"{'='*70}\n")

    # 1. Extração em Lote
    print("[ETAPA 1/4] Extração de dados brutos (ONS e CCEE)...")
    ingestion_status = fetch_energy_data(raw_data_dir=raw_dir, years=years, force=force)

    # 2. Transformação e Cruzamento por Ano
    print("\n[ETAPA 2/4] Transformação, limpeza e cruzamento dos dados...")
    all_facts = []

    for year in sorted(years):
        year_status = ingestion_status.get(year, {})
        ear_path = year_status.get("ons_ear", {}).get("path")
        ena_path = year_status.get("ons_ena", {}).get("path")
        pld_path = year_status.get("ccee_pld", {}).get("path")

        if not (ear_path and os.path.exists(ear_path) and 
                ena_path and os.path.exists(ena_path) and 
                pld_path and os.path.exists(pld_path)):
            print(f"[AVISO] Arquivos do ano {year} incompletos ou não encontrados. Pulando processamento.")
            continue

        print(f"\n-> Processando ano {year}...")
        df_ear_raw = pd.read_csv(ear_path, sep=";", encoding="utf-8")
        df_ena_raw = pd.read_csv(ena_path, sep=";", encoding="utf-8")
        df_pld_raw = pd.read_csv(pld_path, sep=";", encoding="utf-8")

        df_ear_clean = clean_ear_data(df_ear_raw)
        df_ena_clean = clean_ena_data(df_ena_raw)
        df_pld_clean = clean_pld_data(df_pld_raw)

        if granularity == "hourly":
            # Granularidade horária: EAR e ENA expandidos para coincidir com cada hora do PLD
            df_fact_year = merge_energy_datasets(
                df_ear=df_ear_clean,
                df_ena=df_ena_clean,
                df_pld=df_pld_clean,
                granularity="hourly"
            )
        else:
            # Granularidade diária agregada
            df_pld_daily = aggregate_pld_daily(df_pld_clean)
            df_fact_year = merge_energy_datasets(
                df_ear=df_ear_clean,
                df_ena=df_ena_clean,
                df_pld=df_pld_daily,
                granularity="daily"
            )

        print(f" -> Ano {year}: {len(df_fact_year)} registros processados.")
        save_processed_datasets(
            df_fact=df_fact_year,
            df_dim=None,
            output_dir=processed_dir,
            label=year,
            granularity=granularity
        )
        all_facts.append(df_fact_year)

    if not all_facts:
        raise RuntimeError("Nenhum dado pôde ser processado. Verifique os logs de extração.")

    # 3. Consolidação Histórica e Testes de Validação
    print("\n[ETAPA 3/4] Consolidação histórica e validação dos dados...")
    df_historical = pd.concat(all_facts, ignore_index=True)
    print(f"Base histórica totalizada: {len(df_historical)} registros ({df_historical['data'].min().strftime('%Y-%m-%d')} a {df_historical['data'].max().strftime('%Y-%m-%d')}).")

    # Validação de consistência dos dados
    validate_processed_data(df_historical, granularity=granularity)

    # 4. Carga e Exportação das Bases Consolidadas
    print("[ETAPA 4/4] Exportação das bases consolidadas para Power BI / Parquet...")
    df_dim = build_submarket_dimension()
    load_results = save_processed_datasets(
        df_fact=df_historical,
        df_dim=df_dim,
        output_dir=processed_dir,
        label="historical",
        granularity=granularity
    )

    print(f"\n{'='*70}")
    print(f" PIPELINE HISTÓRICO FINALIZADO COM SUCESSO!")
    print(f" Total de registros: {len(df_historical)}")
    print(f"{'='*70}\n")

    return {
        "years": years,
        "granularity": granularity,
        "total_records": len(df_historical),
        "files": load_results,
    }


if __name__ == "__main__":
    run_pipeline()