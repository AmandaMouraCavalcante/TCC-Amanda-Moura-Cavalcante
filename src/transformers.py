"""
Módulo de Transformação e Tratamento de Dados (ONS e CCEE)
Funções de limpeza, padronização temporal, conversão de tipos e alinhamento dimensional entre as fontes.
"""
import pandas as pd


# Dicionário de mapeamento para os 4 submercados oficiais
SUBMARKET_MAP = {
    "SUDESTE/CENTRO-OESTE": "SE/CO",
    "SUDESTE": "SE/CO",
    "SE/CO": "SE/CO",
    "SE": "SE/CO",
    "SUL": "S",
    "S": "S",
    "NORDESTE": "NE",
    "NE": "NE",
    "NORTE": "N",
    "N": "N"
}


def _to_float(series: pd.Series) -> pd.Series:
    """
    Converte valores para float tratando virgula decimal e strings estranhas ('-', 'N/D')
    sem quebrar a execucao do codigo.
    """
    if series.dtype == object:
        return pd.to_numeric(series.astype(str).str.replace(",", "."), errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def clean_ear_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Limpa e padroniza a base de Energia Armazenada (EAR) do ONS."""
    df = df_raw.copy()
    
    # 1. Padronizacao da data
    df["data"] = pd.to_datetime(df["ear_data"])
    
    # 2. Padronizacao do submercado
    df["id_submercado"] = (
        df["id_subsistema"]
        .astype(str)
        .str.strip()
        .str.upper()
        .map(SUBMARKET_MAP)
        .fillna(df["id_subsistema"])
    )
    
    # 3. Conversao de metricas numericas
    metric_cols = ["ear_verif_subsistema_percentual", "ear_verif_subsistema_mwmes"]
    for col in metric_cols:
        if col in df.columns:
            df[col] = _to_float(df[col])

    # 4. Renomeacao intuitiva
    df = df.rename(columns={
        "ear_verif_subsistema_percentual": "ear_percentual",
        "ear_verif_subsistema_mwmes": "ear_mwmes"
    })
    
    return df[["data", "id_submercado", "ear_percentual", "ear_mwmes"]].sort_values(["data", "id_submercado"]).reset_index(drop=True)


def clean_ena_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Limpa e padroniza a base de Energia Natural Afluente (ENA) do ONS."""
    df = df_raw.copy()
    
    df["data"] = pd.to_datetime(df["ena_data"])
    
    df["id_submercado"] = (
        df["id_subsistema"]
        .astype(str)
        .str.strip()
        .str.upper()
        .map(SUBMARKET_MAP)
        .fillna(df["id_subsistema"])
    )
    
    metric_cols = ["ena_bruta_regiao_mwmed", "ena_bruta_regiao_percentualmlt"]
    for col in metric_cols:
        if col in df.columns:
            df[col] = _to_float(df[col])

    df = df.rename(columns={
        "ena_bruta_regiao_mwmed": "ena_mwmed",
        "ena_bruta_regiao_percentualmlt": "ena_percentual_mlt"
    })
    
    return df[["data", "id_submercado", "ena_mwmed", "ena_percentual_mlt"]].sort_values(["data", "id_submercado"]).reset_index(drop=True)


def clean_pld_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Reconstroi a data e hora do PLD e padroniza submercados da CCEE."""
    df = df_raw.copy()
    
    # Parse vetorizado direto de data (YYYYMMDD)
    mes_clean = df["MES_REFERENCIA"].astype(str).str.replace('"', '').str.strip()
    dia_clean = df["DIA"].astype(str).str.replace('"', '').str.strip().str.zfill(2)
    df["data"] = pd.to_datetime(mes_clean + dia_clean, format="%Y%m%d")
    
    # Padronizacao do submercado
    df["id_submercado"] = (
        df["SUBMERCADO"]
        .astype(str)
        .str.replace('"', '')
        .str.strip()
        .str.upper()
        .map(SUBMARKET_MAP)
        .fillna(df["SUBMERCADO"])
    )
    
    df["hora"] = pd.to_numeric(df["HORA"].astype(str).str.replace('"', '').str.strip(), errors="coerce").fillna(0).astype(int)
    df["pld_valor"] = _to_float(df["PLD_HORA"])
        
    return df[["data", "hora", "id_submercado", "pld_valor"]].sort_values(["data", "hora", "id_submercado"]).reset_index(drop=True)


def aggregate_pld_daily(df_pld_clean: pd.DataFrame) -> pd.DataFrame:
    """Harmoniza o PLD de horario para diario (media, minimo, maximo e contagem de horas)."""
    df_daily = (
        df_pld_clean.groupby(["data", "id_submercado"])
        .agg(
            pld_medio=("pld_valor", "mean"),
            pld_min=("pld_valor", "min"),
            pld_max=("pld_valor", "max"),
            horas_registradas=("pld_valor", "count")
        )
        .reset_index()
    )
    df_daily["pld_medio"] = df_daily["pld_medio"].round(2)
    df_daily["pld_min"] = df_daily["pld_min"].round(2)
    df_daily["pld_max"] = df_daily["pld_max"].round(2)
    df_daily["horas_registradas"] = df_daily["horas_registradas"].astype(int)
    
    return df_daily


def merge_energy_datasets(
    df_ear: pd.DataFrame, 
    df_ena: pd.DataFrame, 
    df_pld: pd.DataFrame,
    granularity: str = "daily"
) -> pd.DataFrame:
    """Cruza as bases hidricas (ONS) com os precos (CCEE) pela chave (data, id_submercado)."""
    df_hidro = pd.merge(
        df_ear,
        df_ena,
        on=["data", "id_submercado"],
        how="inner"
    )

    if granularity == "hourly":
        df_final = pd.merge(df_pld, df_hidro, on=["data", "id_submercado"], how="inner")
        sort_cols = ["data", "hora", "id_submercado"]
    elif granularity == "daily":
        df_final = pd.merge(df_hidro, df_pld, on=["data", "id_submercado"], how="inner")
        sort_cols = ["data", "id_submercado"]
    else:
        raise ValueError(f"Granularidade invalida: {granularity}")

    # Auditoria de dias cruzados
    dias_ear = df_ear["data"].nunique()
    dias_pld = df_pld["data"].nunique()
    dias_final = df_final["data"].nunique()

    if dias_final < max(dias_ear, dias_pld):
        print(f"[AUDITORIA] Cobertura temporal parcial: ONS={dias_ear} dias, CCEE={dias_pld} dias -> Cruzados={dias_final} dias")
    else:
        print(f"[AUDITORIA] Cobertura 100% alinhada: {dias_final} dias cruzados com sucesso.")

    return df_final.sort_values(sort_cols).reset_index(drop=True)


def validate_processed_data(df: pd.DataFrame, granularity: str = "daily") -> bool:
    """Verifica regras de integridade física e de dados antes de autorizar a gravação."""
    print("\n--- Validação de Sanidade dos Dados ---")

    # 1. Chave primaria
    pk = ["data", "hora", "id_submercado"] if granularity == "hourly" else ["data", "id_submercado"]
    duplicates = df.duplicated(subset=pk).sum()
    if duplicates > 0:
        raise ValueError(f"[FALHA] Detectadas {duplicates} linhas duplicadas para a chave {pk}.")
    print(f" [OK] Unicidade da Chave Primária {pk}: 0 duplicatas.")

    # 2. Ausencia de Nulos nas chaves
    null_cols = df[pk].isnull().sum().to_dict()
    for col, count in null_cols.items():
        if count > 0:
            raise ValueError(f"[FALHA] Coluna '{col}' contém {count} valores nulos.")
    print(" [OK] Integridade de Chaves: Nenhum valor nulo detectado.")

    # 3. Submercados validos
    expected_submarkets = {"SE/CO", "S", "NE", "N"}
    actual_submarkets = set(df["id_submercado"].unique())
    if not actual_submarkets.issubset(expected_submarkets):
        raise ValueError(f"[FALHA] Submercados inesperados encontrados: {actual_submarkets - expected_submarkets}")
    print(f" [OK] Submercados Válidos: {actual_submarkets}")

    # 4. Limites fisicos de EAR [0, 100]%
    if "ear_percentual" in df.columns:
        ear_anomalies = df[~df["ear_percentual"].between(0.0, 100.0, inclusive="both")]["ear_percentual"]
        if not ear_anomalies.empty:
            raise ValueError(f"[FALHA] Detectados {len(ear_anomalies)} registros de EAR% fora de [0, 100].")
        print(" [OK] Limites Físicos de EAR%: Todos os valores dentro de [0.0%, 100.0%].")

    # 5. Preco nao-negativo
    price_col = "pld_valor" if "pld_valor" in df.columns else "pld_medio"
    if price_col in df.columns:
        neg_pld = df[df[price_col] < 0]
        if not neg_pld.empty:
            raise ValueError(f"[FALHA] Detectados {len(neg_pld)} registros de PLD negativo.")
        print(f" [OK] Domínio de Preços ({price_col}): Nenhum valor negativo detectado.")

    print("[SANIDADE APROVADA] Todos os testes passaram com sucesso.\n")
    return True


def build_submarket_dimension() -> pd.DataFrame:
    """Cria a tabela dimensão canônica de submercados para o modelo analítico."""
    submarkets = [
        {"id_submercado": "SE/CO", "nom_submercado": "SUDESTE / CENTRO-OESTE", "regiao": "Centro-Sul"},
        {"id_submercado": "S", "nom_submercado": "SUL", "regiao": "Sul"},
        {"id_submercado": "NE", "nom_submercado": "NORDESTE", "regiao": "Nordeste"},
        {"id_submercado": "N", "nom_submercado": "NORTE", "regiao": "Norte"}
    ]
    return pd.DataFrame(submarkets)