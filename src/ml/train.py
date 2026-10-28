"""Module d'entraînement MLOps avec suivi d'expérimentation MLflow (Sprint 5).

Ce module :
1. Charge les matrices préparées ou exécute le feature pipeline.
2. Compare plusieurs algorithmes de Régression (Ridge, Random Forest, HistGradientBoosting).
3. Compare plusieurs algorithmes de Classification (LogisticRegression, Random Forest, HistGradientBoosting).
4. Logue les hyperparamètres, métriques et artefacts dans MLflow.
5. Sélectionne et sauvegarde les modèles champions dans `models/`.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

# Optimisation multithread Windows et compatibilité MLflow
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score

from src.ml.features import DEFAULT_MODELS_DIR, DEFAULT_OUTPUT_DIR, prepare_ml_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.train")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MLFLOW_DB_PATH = PROJECT_ROOT / "data" / "ml" / "mlflow.db"
MLFLOW_ARTIFACTS_DIR = PROJECT_ROOT / "data" / "ml" / "artifacts"
EXPERIMENT_NAME = "senegal_audiovisual_ml"


def load_or_generate_data(data_dir: Path = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Charge les données sérialisées ou les génère à la volée."""
    npz_path = data_dir / "train_test_data.npz"
    if npz_path.exists():
        logger.info("Chargement des données prétraitées depuis %s", npz_path)
        npz = np.load(npz_path, allow_pickle=True)
        return {
            "X_train": npz["X_train"],
            "X_test": npz["X_test"],
            "y_reg_train": npz["y_reg_train"],
            "y_reg_test": npz["y_reg_test"],
            "y_clf_train": npz["y_clf_train"],
            "y_clf_test": npz["y_clf_test"],
            "views_test": npz["views_test"],
        }
    logger.info("Données non trouvées en cache, extraction et feature engineering...")
    return prepare_ml_data()


def evaluate_regression(model: Any, X_test: np.ndarray, y_test: np.ndarray, views_test: np.ndarray) -> Dict[str, float]:
    """Calcule les métriques de régression (sur log-scale et sur échelle réelle)."""
    y_pred_log = model.predict(X_test)
    rmse_log = float(np.sqrt(mean_squared_error(y_test, y_pred_log)))
    mae_log = float(mean_absolute_error(y_test, y_pred_log))
    r2 = float(r2_score(y_test, y_pred_log))

    # Échelle réelle des vues
    y_pred_views = np.expm1(y_pred_log)
    mae_views = float(mean_absolute_error(views_test, y_pred_views))
    median_ae_views = float(np.median(np.abs(views_test - y_pred_views)))

    return {
        "r2_score": r2,
        "rmse_log": rmse_log,
        "mae_log": mae_log,
        "mae_views_real": mae_views,
        "median_ae_views": median_ae_views,
    }


def evaluate_classification(model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
    """Calcule les métriques de classification pour la détection de Hits Viraux."""
    y_pred = model.predict(X_test)
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
    else:
        y_prob = y_pred

    accuracy = float(accuracy_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    f1 = float(f1_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))

    return {
        "accuracy": accuracy,
        "roc_auc": roc_auc,
        "f1_score": f1,
        "precision": precision,
        "recall": recall,
    }


def log_candidate_model(model: Any, name: str, models_dir: Path) -> None:
    """Logue le modèle dans MLflow comme artefact joblib sérialisé."""
    candidate_path = models_dir / f"{name}.joblib"
    joblib.dump(model, candidate_path)
    mlflow.log_artifact(str(candidate_path), artifact_path="model")


def train_and_track_models(
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Entraîne les modèles candidats, les logue dans MLflow et persiste les champions."""
    models_dir.mkdir(parents=True, exist_ok=True)
    MLFLOW_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    tracking_uri = f"sqlite:///{MLFLOW_DB_PATH.as_posix()}"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    data = load_or_generate_data()
    X_train = data["X_train"]
    X_test = data["X_test"]
    y_reg_train = data["y_reg_train"]
    y_reg_test = data["y_reg_test"]
    y_clf_train = data["y_clf_train"]
    y_clf_test = data["y_clf_test"]
    views_test = data["views_test"]

    # =========================================================================
    # 1. EXPÉRIMENTATIONS RÉGRESSION (Volume de Vues)
    # =========================================================================
    logger.info("=== ENTRAÎNEMENT DES CANDIDATS RÉGRESSION ===")
    regressors = {
        "Ridge_Baseline": Ridge(alpha=10.0, random_state=42),
        "RandomForest_Regressor": RandomForestRegressor(
            n_estimators=100, max_depth=12, random_state=42, n_jobs=2
        ),
        "HistGradientBoosting_Regressor": HistGradientBoostingRegressor(
            max_iter=150, max_depth=8, learning_rate=0.08, random_state=42
        ),
    }

    best_reg_name = ""
    best_reg_model = None
    best_reg_metrics = {}
    best_reg_r2 = -float("inf")

    for name, model in regressors.items():
        with mlflow.start_run(run_name=f"Reg_{name}"):
            logger.info("Entraînement régression : %s", name)
            model.fit(X_train, y_reg_train)
            metrics = evaluate_regression(model, X_test, y_reg_test, views_test)

            # Logging MLflow
            mlflow.log_param("model_name", name)
            mlflow.log_param("task", "regression_views")
            mlflow.log_params(model.get_params())
            mlflow.log_metrics(metrics)
            log_candidate_model(model, name, models_dir)

            logger.info(
                "[%s] R2=%.4f | RMSE_log=%.4f | MAE_log=%.4f | MedAE_vues=%.0f",
                name,
                metrics["r2_score"],
                metrics["rmse_log"],
                metrics["mae_log"],
                metrics["median_ae_views"],
            )

            if metrics["r2_score"] > best_reg_r2:
                best_reg_r2 = metrics["r2_score"]
                best_reg_name = name
                best_reg_model = model
                best_reg_metrics = metrics

    # =========================================================================
    # 2. EXPÉRIMENTATIONS CLASSIFICATION (Probabilité de Hit Viral)
    # =========================================================================
    logger.info("=== ENTRAÎNEMENT DES CANDIDATS CLASSIFICATION ===")
    classifiers = {
        "LogisticRegression_Baseline": LogisticRegression(max_iter=1000, random_state=42),
        "RandomForest_Classifier": RandomForestClassifier(
            n_estimators=100, max_depth=12, random_state=42, n_jobs=2
        ),
        "HistGradientBoosting_Classifier": HistGradientBoostingClassifier(
            max_iter=150, max_depth=8, learning_rate=0.08, random_state=42
        ),
    }

    best_clf_name = ""
    best_clf_model = None
    best_clf_metrics = {}
    best_clf_auc = -float("inf")

    for name, model in classifiers.items():
        with mlflow.start_run(run_name=f"Clf_{name}"):
            logger.info("Entraînement classification : %s", name)
            model.fit(X_train, y_clf_train)
            metrics = evaluate_classification(model, X_test, y_clf_test)

            # Logging MLflow
            mlflow.log_param("model_name", name)
            mlflow.log_param("task", "classification_hit_viral")
            mlflow.log_params(model.get_params())
            mlflow.log_metrics(metrics)
            log_candidate_model(model, name, models_dir)

            logger.info(
                "[%s] ROC-AUC=%.4f | F1=%.4f | Accuracy=%.4f | Precision=%.4f | Recall=%.4f",
                name,
                metrics["roc_auc"],
                metrics["f1_score"],
                metrics["accuracy"],
                metrics["precision"],
                metrics["recall"],
            )

            if metrics["roc_auc"] > best_clf_auc:
                best_clf_auc = metrics["roc_auc"]
                best_clf_name = name
                best_clf_model = model
                best_clf_metrics = metrics

    # =========================================================================
    # 3. SAUVEGARDE DES CHAMPIONS ET METADONNÉES
    # =========================================================================
    reg_champion_path = models_dir / "regressor_champion.joblib"
    clf_champion_path = models_dir / "classifier_champion.joblib"

    joblib.dump(best_reg_model, reg_champion_path)
    joblib.dump(best_clf_model, clf_champion_path)

    metadata = {
        "sprint": "Sprint 5 - MLOps",
        "pipeline": "Hybride (Régression + Classification + Clustering)",
        "regression_champion": {
            "name": best_reg_name,
            "artifact": str(reg_champion_path.name),
            "metrics": best_reg_metrics,
        },
        "classification_champion": {
            "name": best_clf_name,
            "artifact": str(clf_champion_path.name),
            "metrics": best_clf_metrics,
        },
        "clustering": {
            "algorithm": "MiniBatchKMeans",
            "k": 4,
            "artifact": "kmeans_model.joblib",
        },
        "feature_count": X_train.shape[1],
        "train_samples": int(X_train.shape[0]),
        "test_samples": int(X_test.shape[0]),
    }

    metadata_path = models_dir / "ml_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info("Modèles champions enregistrés avec succès dans %s", models_dir)
    logger.info("Champion Régression : %s (R2 = %.4f)", best_reg_name, best_reg_r2)
    logger.info("Champion Classification : %s (ROC-AUC = %.4f)", best_clf_name, best_clf_auc)

    return metadata["regression_champion"], metadata["classification_champion"]


if __name__ == "__main__":
    logger.info("Démarrage du cycle d'entraînement MLOps...")
    train_and_track_models()
