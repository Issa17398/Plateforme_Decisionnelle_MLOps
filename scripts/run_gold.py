"""Script CLI d'exécution et de validation de la couche Gold avec dbt-duckdb (Sprint 3).

Usage:
    # Exécution complète de la modélisation Gold (dbt run + dbt test) :
    python scripts/run_gold.py

    # Exécution des modèles uniquement :
    python scripts/run_gold.py --only-run

    # Exécution des tests uniquement :
    python scripts/run_gold.py --only-test
"""

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"


def setup_logger() -> logging.Logger:
    """Configure la journalisation dans logs/gold_pipeline.log et sur la console."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "gold_pipeline.log"

    logger = logging.getLogger("gold_pipeline")
    logger.setLevel(logging.INFO)

    for h in logger.handlers[:]:
        logger.removeHandler(h)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    return logger


def run_dbt_command(command: list[str], logger: logging.Logger) -> int:
    """Exécute une commande dbt en sous-processus sécurisé."""
    dbt_exe = sys.executable.replace("python.exe", "dbt.exe")
    full_cmd = [
        dbt_exe,
        *command,
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
        "--no-version-check",
        "--no-send-anonymous-usage-stats",
    ]

    logger.info(f"Exécution : {' '.join(full_cmd)}")
    result = subprocess.run(full_cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)

    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            logger.info(f"  [dbt] {line}")
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            logger.warning(f"  [dbt err] {line}")

    return result.returncode


def run_gold_pipeline(skip_tests: bool = False, skip_run: bool = False) -> int:
    """Exécute le pipeline dbt complet pour la couche Gold."""
    logger = setup_logger()
    logger.info("================================================================================")
    logger.info("       SÉNÉGAL AUDIOVISUAL INTELLIGENCE — PIPELINE COUCHE GOLD (SPRINT 3)       ")
    logger.info("================================================================================")
    logger.info(f"Horodatage UTC : {datetime.now(timezone.utc).isoformat()}")

    # 1. dbt run
    if not skip_run:
        logger.info(">>> Étape 1 : Construction des modèles Gold (dim_channels, fct_videos_performance)...")
        rc_run = run_dbt_command(["run"], logger)
        if rc_run != 0:
            logger.error("Échec de la commande 'dbt run' !")
            return rc_run
        logger.info("Modèles Gold construits avec succès dans data/gold/analytics.duckdb.")

    # 2. dbt test
    if not skip_tests:
        logger.info(">>> Étape 2 : Exécution des tests d'intégrité et de conformité dbt...")
        rc_test = run_dbt_command(["test"], logger)
        if rc_test != 0:
            logger.error("Échec de la commande 'dbt test' !")
            return rc_test
        logger.info("Tous les tests dbt ont été validés avec succès.")

    logger.info("================================================================================")
    logger.info("                   COUCHE GOLD VALIDÉE AVEC SUCCÈS                              ")
    logger.info("================================================================================")
    return 0


def main() -> int:
    """Point d'entrée principal en CLI."""
    parser = argparse.ArgumentParser(description="Pipeline Gold avec dbt-duckdb")
    parser.add_argument("--only-run", action="store_true", help="Exécuter uniquement dbt run")
    parser.add_argument("--only-test", action="store_true", help="Exécuter uniquement dbt test")
    args = parser.parse_args()

    return run_gold_pipeline(
        skip_tests=args.only_run,
        skip_run=args.only_test,
    )


if __name__ == "__main__":
    sys.exit(main())
