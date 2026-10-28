"""DAG Airflow de préparation et d'entraînement ML (Sprint 5 - MLOps).

Ce DAG ordonnance le cycle d'apprentissage automatique supervisé :
1. task_feature_engineering : Extraction des features depuis la table Gold `fct_videos_performance`.
2. task_model_training : Entraînement des modèles de prédiction de performance (Vues / Engagement).
3. task_model_evaluation : Évaluation des métriques (RMSE, R2, MAE) et comparaison de baselines.
4. task_mlflow_registration : Enregistrement du modèle champion dans le Model Registry de MLflow.
"""

from datetime import datetime, timedelta

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


default_args = {
    "owner": "senegal_data_eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="senegal_ml_training_pipeline",
    default_args=default_args,
    description="Pipeline MLOps d'entraînement et de tracking MLflow (Sprint 5)",
    schedule_interval="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["senegal", "mlops", "mlflow", "training", "sprint5"],
) as dag:

    start_ml = EmptyOperator(
        task_id="start_ml_pipeline",
        doc_md="Initialisation du cycle d'entraînement MLOps.",
    )

    task_feature_engineering = BashOperator(
        task_id="task_feature_engineering",
        bash_command="python -m src.ml.features",
        doc_md="Extraction des variables prédictives depuis fct_videos_performance et clustering K-Means.",
    )

    task_model_training = BashOperator(
        task_id="task_model_training",
        bash_command="python -m src.ml.train",
        doc_md="Entraînement multi-modèles (Régression & Classification) et suivi des runs MLflow.",
    )

    task_model_evaluation = BashOperator(
        task_id="task_model_evaluation",
        bash_command="python -m src.ml.evaluate",
        doc_md="Évaluation des métriques sur le test set (R2, ROC-AUC) et génération des graphiques.",
    )

    end_ml = EmptyOperator(
        task_id="end_ml_pipeline",
        doc_md="Fin du cycle d'entraînement et enregistrement du modèle.",
    )

    start_ml >> task_feature_engineering >> task_model_training >> task_model_evaluation >> end_ml
