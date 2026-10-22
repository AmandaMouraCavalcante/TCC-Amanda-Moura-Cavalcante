"""
Interface CLI para o pipeline de dados de energia (ONS e CCEE).

Exemplos de uso:
    python main.py                          # Executa o histórico completo (2021 a 2026) em granularidade diária
    python main.py --year 2026             # Executa apenas o ano corrente
    python main.py --start 2023 --end 2025 # Executa intervalo de anos
    python main.py --force                 # Força re-download ignorando cache local
    python main.py --granularity hourly    # Executa com granularidade horária
"""
import argparse
from datetime import datetime
from src.pipeline import run_pipeline


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL de dados de energia (ONS e CCEE)."
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Ano único específico para execução do pipeline (ex: 2026)."
    )
    parser.add_argument(
        "--start",
        type=int,
        default=2021,
        help="Ano inicial para execução histórica em lote (padrão: 2021)."
    )
    parser.add_argument(
        "--end",
        type=int,
        default=datetime.now().year,
        help=f"Ano final para execução histórica em lote (padrão: {datetime.now().year})."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força o download dos arquivos brutos mesmo que já existam em cache local."
    )
    parser.add_argument(
        "--granularity",
        choices=["daily", "hourly"],
        default="daily",
        help="Granularidade temporal alvo da base fato (padrão: 'daily', agregando o PLD horário na média diária)."
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.year:
        years = [args.year]
    else:
        if args.start > args.end:
            raise ValueError(f"Ano inicial ({args.start}) não pode ser maior que o ano final ({args.end}).")
        years = list(range(args.start, args.end + 1))

    run_pipeline(
        years=years,
        force=args.force,
        granularity=args.granularity
    )


if __name__ == "__main__":
    main()