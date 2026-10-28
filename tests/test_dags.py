"""Suite de tests unitaires et de conformité pour les DAGs Airflow et Docker (Sprint 4).

Ce module valide :
- La validité syntaxique de tous les fichiers DAGs via AST.
- La structure et les paramètres par défaut du DAG maître `senegal_audiovisual_pipeline`.
- L'ordonnancement exact des tâches (Bronze -> Silver -> Gold -> Quality Gate -> Summary).
- L'intégrité des commandes Bash exécutées par les opérateurs.
- La conformité du DAG MLOps `senegal_ml_training_pipeline`.
- L'intégrité des fichiers de configuration Docker (Dockerfile, docker-compose.yml).
"""

import ast
import importlib.util
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAGS_DIR = PROJECT_ROOT / "dags"


def test_dags_directory_and_syntax():
    """Vérifie que le dossier dags existe et que tous les fichiers .py ont une syntaxe Python valide."""
    assert DAGS_DIR.exists(), f"Le dossier {DAGS_DIR} doit exister."
    
    dag_files = list(DAGS_DIR.glob("*.py"))
    assert len(dag_files) >= 2, "Au moins 2 DAGs doivent être présents (audiovisual et ml_training)."

    for dag_file in dag_files:
        code = dag_file.read_text(encoding="utf-8")
        try:
            ast.parse(code, filename=str(dag_file))
        except SyntaxError as e:
            pytest.fail(f"Erreur de syntaxe Python dans le DAG {dag_file.name} : {e}")


def test_audiovisual_dag_instantiation():
    """Valide l'instanciation du DAG principal et ses métadonnées de gouvernance."""
    dag_path = DAGS_DIR / "audiovisual_pipeline.py"
    spec = importlib.util.spec_from_file_location("audiovisual_pipeline", dag_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "dag"), "Le module audiovisual_pipeline doit exposer un objet 'dag'."
    dag = module.dag

    assert dag.dag_id == "senegal_audiovisual_pipeline"
    assert dag.catchup is False
    assert dag.default_args.get("owner") == "senegal_data_eng"
    assert dag.default_args.get("retries") == 2
    assert "medallion" in dag.tags
    assert "dbt" in dag.tags


def test_audiovisual_dag_tasks_and_dependencies():
    """Valide la séquence ordonnée des tâches du pipeline Médaillon."""
    dag_path = DAGS_DIR / "audiovisual_pipeline.py"
    spec = importlib.util.spec_from_file_location("audiovisual_pipeline", dag_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dag = module.dag
    expected_tasks = [
        "start_pipeline",
        "task_bronze_ingestion",
        "task_silver_transformation",
        "task_gold_modeling",
        "task_data_quality_gate",
        "task_pipeline_summary",
        "end_pipeline",
    ]

    for task_name in expected_tasks:
        assert hasattr(module, task_name), f"La tâche {task_name} doit être définie dans le DAG."
        task_obj = getattr(module, task_name)
        assert task_obj.task_id == task_name

    # Vérification des dépendances séquentielles
    start_op = getattr(module, "start_pipeline")
    bronze_op = getattr(module, "task_bronze_ingestion")
    silver_op = getattr(module, "task_silver_transformation")
    gold_op = getattr(module, "task_gold_modeling")
    quality_op = getattr(module, "task_data_quality_gate")
    summary_op = getattr(module, "task_pipeline_summary")
    end_op = getattr(module, "end_pipeline")

    assert bronze_op in start_op.downstream_list
    assert silver_op in bronze_op.downstream_list
    assert gold_op in silver_op.downstream_list
    assert quality_op in gold_op.downstream_list
    assert summary_op in quality_op.downstream_list
    assert end_op in summary_op.downstream_list


def test_audiovisual_dag_bash_commands():
    """Vérifie que les commandes Bash déclenchent bien les scripts du projet."""
    dag_path = DAGS_DIR / "audiovisual_pipeline.py"
    spec = importlib.util.spec_from_file_location("audiovisual_pipeline", dag_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    bronze_op = getattr(module, "task_bronze_ingestion")
    assert "collect_dataset.py" in bronze_op.bash_command

    silver_op = getattr(module, "task_silver_transformation")
    assert "transform_silver.py" in silver_op.bash_command

    gold_op = getattr(module, "task_gold_modeling")
    assert "run_gold.py --only-run" in gold_op.bash_command

    quality_op = getattr(module, "task_data_quality_gate")
    assert "run_gold.py --only-test" in quality_op.bash_command

    summary_op = getattr(module, "task_pipeline_summary")
    assert "generate_pdf_report_sprint4.py" in summary_op.bash_command


def test_ml_training_dag_structure():
    """Valide l'existence et la structure du DAG MLOps prévu pour le Sprint 5."""
    dag_path = DAGS_DIR / "ml_training_pipeline.py"
    spec = importlib.util.spec_from_file_location("ml_training_pipeline", dag_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "dag")
    dag = module.dag
    assert dag.dag_id == "senegal_ml_training_pipeline"
    assert "mlops" in dag.tags


def test_docker_and_compose_configs():
    """Valide la présence et la cohérence de Dockerfile et docker-compose.yml."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    assert dockerfile.exists(), "Le fichier Dockerfile doit exister à la racine."
    assert compose_file.exists(), "Le fichier docker-compose.yml doit exister à la racine."

    docker_content = dockerfile.read_text(encoding="utf-8")
    assert "apache/airflow" in docker_content
    assert "requirements.txt" in docker_content

    compose_content = compose_file.read_text(encoding="utf-8")
    assert "postgres" in compose_content
    assert "airflow-webserver" in compose_content
    assert "airflow-scheduler" in compose_content
    assert "airflow-init" in compose_content
    assert "5434:5432" in compose_content
    assert "8080:8080" in compose_content
