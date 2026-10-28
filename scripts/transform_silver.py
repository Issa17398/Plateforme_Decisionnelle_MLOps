"""Script CLI d'exécution de la transformation Silver (Sprint 2).

Usage:
    # Test contrôlé sur un échantillon de 100 vidéos :
    python scripts/transform_silver.py --limit 100

    # Exécution complète sur tout le catalogue Bronze (15 832 vidéos) :
    python scripts/transform_silver.py

    # Personnalisation des chemins :
    python scripts/transform_silver.py --input data/raw/senegal_audiovisual_videos.csv --output data/silver/videos.parquet
"""

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

# Ajout de la racine du projet dans le PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.transformations.silver import transform_bronze_to_silver


def setup_logger() -> logging.Logger:
    """Configure la journalisation dans logs/transform_silver.log et sur la console."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "transform_silver.log"

    logger = logging.getLogger("transform_silver")
    logger.setLevel(logging.INFO)

    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # Handler fichier
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(fh)

    # Handler console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    return logger


def main() -> int:
    """Point d'entrée principal du pipeline de transformation Silver."""
    parser = argparse.ArgumentParser(
        description="Pipeline de transformation Bronze -> Silver pour Senegal Audiovisual Intelligence"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.csv",
        help="Chemin du fichier CSV source Bronze",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "silver" / "videos.parquet",
        help="Chemin du fichier Parquet cible Silver",
    )
    parser.add_argument(
        "--quarantine",
        type=Path,
        default=PROJECT_ROOT / "data" / "quarantine" / "rejected_videos.parquet",
        help="Chemin du fichier Parquet de quarantaine",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de lignes à transformer (pour test contrôlé ou échantillonnage)",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=PROJECT_ROOT / "reports",
        help="Répertoire de stockage des rapports d'exécution",
    )

    args = parser.parse_args()
    logger = setup_logger()

    logger.info("================================================================================")
    logger.info("      SÉNÉGAL AUDIOVISUAL INTELLIGENCE — PIPELINE COUCHE SILVER (SPRINT 2)      ")
    logger.info("================================================================================")
    logger.info(f"Fichier source Bronze : {args.input}")
    logger.info(f"Fichier cible Silver  : {args.output}")
    logger.info(f"Fichier Quarantaine   : {args.quarantine}")
    if args.limit:
        logger.info(f"Mode échantillon actif : limite à {args.limit} lignes")

    try:
        report = transform_bronze_to_silver(
            source_csv_path=args.input,
            silver_parquet_path=args.output,
            quarantine_parquet_path=args.quarantine,
            limit=args.limit,
        )

        # Horodatage du nom de rapport
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_file = args.report_dir / f"silver_execution_report_{timestamp_slug}.json"
        report.save_json(report_file)

        logger.info("--------------------------------------------------------------------------------")
        logger.info("                       RÉSULTAT DU PIPELINE SILVER                              ")
        logger.info("--------------------------------------------------------------------------------")
        logger.info(f"Statut global              : {report.status}")
        logger.info(f"Lignes Bronze lues         : {report.total_bronze_rows}")
        logger.info(f"Lignes Silver écrites      : {report.valid_silver_rows}")
        logger.info(f"Lignes rejetées            : {report.quarantine_rows}")
        logger.info(f"Doublons écartés           : {report.duplicates_pruned}")
        logger.info(f"Durée d'exécution          : {report.execution_duration_sec} secondes")
        logger.info(f"Rapport d'audit exporté    : {report_file}")
        logger.info("================================================================================")

        if report.status != "SUCCESS":
            logger.error(f"Erreur d'exécution : {report.error_message}")
            return 1

        return 0

    except Exception as e:
        logger.critical(f"Échec fatal du pipeline : {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
