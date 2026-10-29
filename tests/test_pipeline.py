"""
Bateria de testes unitários do pipeline de dados.

Testa:
1. Limpeza defensiva de strings e conversão numérica.
2. Mapeamento canônico dos 4 submercados (SE/CO, S, NE, N).
3. Agregação diária das médias horárias do PLD.
4. Bloqueio de duplicatas na chave composta (data + submercado).
5. Validação de limites físicos (EAR entre 0 e 100%, PLD não negativo).
6. Integridade relacional e modelo dimensional no SQLite.
"""
import os
import sqlite3
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from src.transformers import (
    _to_float,
    clean_ear_data,
    clean_ena_data,
    clean_pld_data,
    aggregate_pld_daily,
    validate_processed_data,
    SUBMARKET_MAP,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPipeline(unittest.TestCase):
    """Testes unitários para validação de dados e integridade do pipeline."""

    def test_01_numeric_cleaning_defensive_to_float(self):
        """Valida conversão de strings numéricas brasileiras e tratamento de nulos/ruídos."""
        sample_series = pd.Series(["123,45", " - ", "N/D", "  98.7  ", None, "1.500,50", 42])
        cleaned = _to_float(sample_series)

        # 123,45 deve ser convertido para 123.45
        self.assertAlmostEqual(cleaned.iloc[0], 123.45)
        # Strings sem valor numérico viram NaN de forma controlada
        self.assertTrue(np.isnan(cleaned.iloc[1]))
        self.assertTrue(np.isnan(cleaned.iloc[2]))
        # Espaços em branco com ponto
        self.assertAlmostEqual(cleaned.iloc[3], 98.7)
        # Valor numérico original preservado
        self.assertEqual(cleaned.iloc[6], 42.0)

    def test_02_submarket_canonical_mapping(self):
        """Garante que as variações de siglas e nomes convergem aos 4 submercados oficiais."""
        test_inputs = ["SUDESTE/CENTRO-OESTE", "SE", "SE/CO", "SUL", "S", "NORDESTE", "NE", "NORTE", "N"]
        mapped = [SUBMARKET_MAP.get(item.upper()) for item in test_inputs]
        expected = ["SE/CO", "SE/CO", "SE/CO", "S", "S", "NE", "NE", "N", "N"]
        self.assertEqual(mapped, expected)

    def test_03_daily_aggregation_and_hours_completeness(self):
        """Verifica se a agregação diária calcula média, mínimo e máximo e conta as horas."""
        dummy_pld = pd.DataFrame({
            "data": pd.to_datetime(["2026-01-01"] * 24),
            "hora": list(range(24)),
            "id_submercado": ["SE/CO"] * 24,
            "pld_valor": [100.0] * 12 + [200.0] * 12  # Média esperada: 150.0
        })
        daily = aggregate_pld_daily(dummy_pld)

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily["horas_registradas"].iloc[0], 24)
        self.assertAlmostEqual(daily["pld_medio"].iloc[0], 150.0)
        self.assertAlmostEqual(daily["pld_min"].iloc[0], 100.0)
        self.assertAlmostEqual(daily["pld_max"].iloc[0], 200.0)

    def test_04_validation_raises_on_duplicated_primary_key(self):
        """Testa se a validação impede registros duplicados para o mesmo dia e submercado."""
        df_duplicate = pd.DataFrame({
            "data": pd.to_datetime(["2026-01-01", "2026-01-01"]),
            "id_submercado": ["SE/CO", "SE/CO"],  # Duplicado
            "ear_percentual": [50.0, 50.0],
            "pld_medio": [60.0, 60.0]
        })
        with self.assertRaises(ValueError) as ctx:
            validate_processed_data(df_duplicate, granularity="daily")
        self.assertIn("duplicadas", str(ctx.exception).lower())

    def test_05_validation_raises_on_physical_bound_violations(self):
        """Testa se a validação barra valores de EAR fora de [0, 100]% e PLD negativo."""
        # 1. EAR acima de 100%
        df_invalid_ear = pd.DataFrame({
            "data": pd.to_datetime(["2026-01-01"]),
            "id_submercado": ["SE/CO"],
            "ear_percentual": [125.0],  # Impossível fisicamente
            "pld_medio": [100.0]
        })
        with self.assertRaises(ValueError):
            validate_processed_data(df_invalid_ear, granularity="daily")

        # 2. PLD negativo
        df_invalid_pld = pd.DataFrame({
            "data": pd.to_datetime(["2026-01-01"]),
            "id_submercado": ["SE/CO"],
            "ear_percentual": [60.0],
            "pld_medio": [-10.5]  # Inválido
        })
        with self.assertRaises(ValueError):
            validate_processed_data(df_invalid_pld, granularity="daily")

    def test_06_sqlite_database_integrity_and_star_schema(self):
        """Audita as tabelas e a integridade relacional no SQLite caso o banco já tenha sido gerado."""
        db_path = str(PROJECT_ROOT / "data" / "processed" / "energy_sector.db")
        if not os.path.exists(db_path):
            self.skipTest(f"Banco {db_path} ainda não gerado. Execute main.py antes deste teste.")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Verifica existência das tabelas fato e dimensão
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        self.assertIn("fato_energia_daily", tables)
        self.assertIn("dim_submercado", tables)

        # Verifica que a tabela fato contém registros
        cur.execute("SELECT COUNT(*) FROM fato_energia_daily;")
        fact_count = cur.fetchone()[0]
        self.assertGreater(fact_count, 0)

        # Verifica que a dimensão tem exatamente os 4 submercados
        cur.execute("SELECT COUNT(*) FROM dim_submercado;")
        dim_count = cur.fetchone()[0]
        self.assertEqual(dim_count, 4)

        # Integridade referencial: INNER JOIN não pode perder registros da fato
        join_query = """
            SELECT COUNT(*)
            FROM fato_energia_daily f
            JOIN dim_submercado d ON f.id_submercado = d.id_submercado;
        """
        cur.execute(join_query)
        joined_count = cur.fetchone()[0]
        self.assertEqual(joined_count, fact_count, "Falha de chave estrangeira entre Fato e Dimensão!")

        conn.close()


if __name__ == "__main__":
    unittest.main()