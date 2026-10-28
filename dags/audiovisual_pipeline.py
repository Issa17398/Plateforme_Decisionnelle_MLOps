"""DAG Airflow d'orchestration de la plateforme Sénégal Audiovisual Intelligence (Sprint 4).

Ce DAG orchestre la chaîne complète d'ingénierie des données selon l'Architecture Médaillon :
1. task_bronze_ingestion : Ingestion ou validation des données brutes YouTube.
2. task_silver_transformation : Nettoyage, typage strict et conversion Parquet sous DuckDB.
3. task_gold_modeling : Modélisation analytique en schéma en étoile (dim_channels, fct_videos_performance) avec dbt-duckdb.
4. task_data_quality_gate : Exécution des tests d'intégrité et de contraintes dbt (15 tests natifs).
5. task_pipeline_summary : Synthèse et génération du rapport technique officiel en PDF.

Conçu selon le paradigme du "DAG Mince" (Thin DAG) :
Le DAG orchestre et supervise l'exécution des scripts autonomes testables indépendamment d'Airflow.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

# Importation d'Airflow avec shim de résilience pour les environnements de test locaux
try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
    from airflow.operators.empty import EmptyOperator
except ImportError:
    # Shim minimal pour l'exécution des tests hors conteneur Docker sous Windows
    class DAG:  # type: ignore
        def __init__(
            self,
            dag_id,
            default_args=None,
            schedule_interval=None,
            start_date=None,
            catchup=False,
            max_active_runs=1,
            tags=None,
            description=None,
            doc_md=None,
        ):
            self.dag_id = dag_id
            self.default_args = default_args or {}
            self.schedule_interval = schedule_interval
            self.start_date = start_date
            self.catchup = catchup
            self.max_active_runs = max_active_runs
            self.tags = tags or []
            self.description = description
            self.tasks = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class BaseOperator:  # type: ignore
        def __init__(self, task_id, doc_md=None, **kwargs):
            self.task_id = task_id
            self.doc_md = doc_md
            self.upstream_list = []
            self.downstream_list = []
            self.kwargs = kwargs

        def __rshift__(self, other):
            if isinstance(other, BaseOperator):
                if other not in self.downstream_list:
                    self.downstream_list.append(other)
                if self not in other.upstream_list:
                    other.upstream_list.append(self)
            return other

    class EmptyOperator(BaseOperator):  # type: ignore
        pass

    class BashOperator(BaseOperator):  # type: ignore
        def __init__(self, task_id, bash_command, **kwargs):
            super().__init__(task_id, **kwargs)
            self.bash_command = bash_command


# Configuration des paramètres par défaut de résilience
default_args = {
    "owner": "senegal_data_eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(minutes=45),
}

with DAG(
    dag_id="senegal_audiovisual_pipeline",
    default_args=default_args,
    description="Pipeline Médaillon (Bronze -> Silver -> Gold avec dbt-duckdb) et Quality Gate",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["senegal", "audiovisual", "medallion", "dbt", "duckdb", "gold"],
) as dag:

    start_pipeline = EmptyOperator(
        task_id="start_pipeline",
        doc_md="Point d'entrée du pipeline d'ingénierie audiovisuelle.",
    )

    # 1. Couche Bronze : Ingestion incrémentale (reprise automatique où le scraping s'est arrêté)
    task_bronze_ingestion = BashOperator(
        task_id="task_bronze_ingestion",
        bash_command="python scripts/collect_dataset.py --incremental || python scripts/collect_dataset.py --check-existing",
        doc_md="""
        ### Ingestion Bronze
        Vérifie la présence du jeu de données brut ou lance une extraction sécurisée via l'API YouTube Data v3.
        Sauvegarde dans `data/raw/senegal_audiovisual_videos.csv`.
        """,
    )

    # 2. Couche Silver : Nettoyage, déduplication et conversion Parquet sous DuckDB
    task_silver_transformation = BashOperator(
        task_id="task_silver_transformation",
        bash_command="python scripts/transform_silver.py",
        doc_md="""
        ### Transformation Silver
        Lit les données brutes Bronze, applique le typage strict, préserve les NULLs légitimes,
        élimine les doublons et écrit dans `data/silver/videos.parquet`.
        """,
    )

    # 3. Couche Gold : Modélisation en schéma en étoile via dbt-duckdb
    task_gold_modeling = BashOperator(
        task_id="task_gold_modeling",
        bash_command="python scripts/run_gold.py --only-run",
        doc_md="""
        ### Modélisation Gold (dbt run)
        Compile et matérialise la dimension `dim_channels` et la table de faits `fct_videos_performance`
        dans l'entrepôt local `data/gold/analytics.duckdb`.
        """,
    )

    # 4. Barrière de Qualité : Tests d'intégrité déclaratifs dbt
    task_data_quality_gate = BashOperator(
        task_id="task_data_quality_gate",
        bash_command="python scripts/run_gold.py --only-test",
        doc_md="""
        ### Quality Gate (dbt test)
        Exécute les 15 tests d'intégrité (unicité, non-nullité, intégrité référentielle FK,
        valeurs acceptées) avant de valider le lot de données.
        """,
    )

    # 5. Synthèse et Reporting : Génération du rapport officiel PDF
    task_pipeline_summary = BashOperator(
        task_id="task_pipeline_summary",
        bash_command="python scripts/generate_pdf_report_sprint4.py",
        doc_md="""
        ### Synthèse du Run
        Génère le rapport technique d'exécution et de performance en PDF dans `reports/`.
        """,
    )

    end_pipeline = EmptyOperator(
        task_id="end_pipeline",
        doc_md="Fin du pipeline et validation du lot de données.",
    )

    # Définition des dépendances séquentielles
    start_pipeline >> task_bronze_ingestion >> task_silver_transformation >> task_gold_modeling >> task_data_quality_gate >> task_pipeline_summary >> end_pipeline
