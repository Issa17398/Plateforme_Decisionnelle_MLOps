"""Module d'évaluation approfondie et génération des rapports graphiques (Sprint 5).

Ce module :
1. Évalue les modèles champions sur l'échantillon de test indépendant (Holdout 20%).
2. Calcule les métriques industrielles (R2, RMSE, MAE, ROC-AUC, F1-score, Confusion Matrix).
3. Produit les visualisations décisionnelles sauvegardées dans `reports/figures/`.
4. Exporte un rapport JSON synthétique dans `reports/ml_evaluation_metrics.json`.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

# Optimisation multithread Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    explained_variance_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from src.ml.features import (
    CLUSTER_ARCHETYPES,
    DEFAULT_MODELS_DIR,
    DEFAULT_OUTPUT_DIR,
    NUMERICAL_FEATURES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.evaluate")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


def generate_evaluation_artifacts(
    models_dir: Path = DEFAULT_MODELS_DIR,
    data_dir: Path = DEFAULT_OUTPUT_DIR,
    figures_dir: Path = FIGURES_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> Dict[str, Any]:
    """Exécute l'évaluation complète et génère tous les graphiques et métriques."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Chargement des données de test
    npz_path = data_dir / "train_test_data.npz"
    if not npz_path.exists():
        raise FileNotFoundError(f"Fichier de données {npz_path} introuvable.")

    data = np.load(npz_path, allow_pickle=True)
    X_test = data["X_test"]
    y_reg_test = data["y_reg_test"]
    y_clf_test = data["y_clf_test"]
    views_test = data["views_test"]

    # Chargement des champions et préprocesseurs
    reg_model = joblib.load(models_dir / "regressor_champion.joblib")
    clf_model = joblib.load(models_dir / "classifier_champion.joblib")
    preprocessor = joblib.load(models_dir / "preprocessor.joblib")
    kmeans = joblib.load(models_dir / "kmeans_model.joblib")

    # =========================================================================
    # A. ÉVALUATION DE LA RÉGRESSION (Volume de Vues)
    # =========================================================================
    logger.info("Calcul des métriques de régression sur le test set...")
    pred_log_views = reg_model.predict(X_test)
    pred_views = np.expm1(pred_log_views)

    r2 = float(r2_score(y_reg_test, pred_log_views))
    rmse_log = float(np.sqrt(mean_squared_error(y_reg_test, pred_log_views)))
    mae_log = float(mean_absolute_error(y_reg_test, pred_log_views))
    exp_var = float(explained_variance_score(y_reg_test, pred_log_views))

    mae_real_views = float(mean_absolute_error(views_test, pred_views))
    med_ae_real_views = float(np.median(np.abs(views_test - pred_views)))

    regression_metrics = {
        "model_type": reg_model.__class__.__name__,
        "r2_score": round(r2, 4),
        "rmse_log": round(rmse_log, 4),
        "mae_log": round(mae_log, 4),
        "explained_variance": round(exp_var, 4),
        "mae_real_views": round(mae_real_views, 2),
        "median_absolute_error_views": round(med_ae_real_views, 2),
    }

    # =========================================================================
    # B. ÉVALUATION DE LA CLASSIFICATION (Hit Viral)
    # =========================================================================
    logger.info("Calcul des métriques de classification sur le test set...")
    pred_clf = clf_model.predict(X_test)
    if hasattr(clf_model, "predict_proba"):
        prob_clf = clf_model.predict_proba(X_test)[:, 1]
    else:
        prob_clf = pred_clf

    acc = float(accuracy_score(y_clf_test, pred_clf))
    roc_auc = float(roc_auc_score(y_clf_test, prob_clf))
    f1 = float(f1_score(y_clf_test, pred_clf))
    prec = float(precision_score(y_clf_test, pred_clf, zero_division=0))
    rec = float(recall_score(y_clf_test, pred_clf, zero_division=0))

    cm = confusion_matrix(y_clf_test, pred_clf)
    tn, fp, fn, tp = cm.ravel()

    classification_metrics = {
        "model_type": clf_model.__class__.__name__,
        "accuracy": round(acc, 4),
        "roc_auc": round(roc_auc, 4),
        "f1_score": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
    }

    # =========================================================================
    # C. SEGMENTATION & CLUSTERING ARCHETYPES
    # =========================================================================
    cluster_counts = {k: 0 for k in CLUSTER_ARCHETYPES.keys()}
    train_df_path = models_dir / "preprocessor.joblib"
    # Centroids information
    cluster_summary = {}
    for c_idx, desc in CLUSTER_ARCHETYPES.items():
        cluster_summary[c_idx] = {
            "name": desc,
            "description": f"Archétype de diffusion n°{c_idx.split('_')[-1]}",
        }

    # =========================================================================
    # D. GÉNÉRATION DES FIGURES MATPLOTLIB
    # =========================================================================
    logger.info("Génération des figures analytiques dans %s...", figures_dir)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Figure 1 : Courbe ROC
    fig_roc, ax_roc = plt.subplots(figsize=(7, 6))
    fpr, tpr, _ = roc_curve(y_clf_test, prob_clf)
    ax_roc.plot(fpr, tpr, color="#008080", lw=2.5, label=f"Champion HistGB (ROC-AUC = {roc_auc:.3f})")
    ax_roc.plot([0, 1], [0, 1], color="#999999", lw=1.5, linestyle="--", label="Aléatoire (AUC = 0.500)")
    ax_roc.set_title("Courbe ROC — Détection des Hits Viraux (≥ 1M Vues)", fontsize=13, fontweight="bold", pad=12)
    ax_roc.set_xlabel("Taux de Faux Positifs (1 - Spécificité)", fontsize=11)
    ax_roc.set_ylabel("Taux de Vrais Positifs (Sensibilité / Rappel)", fontsize=11)
    ax_roc.legend(loc="lower right", frameon=True, fontsize=10)
    fig_roc.tight_layout()
    fig_roc.savefig(figures_dir / "roc_curve.png", dpi=200)
    plt.close(fig_roc)

    # Figure 2 : Matrice de Confusion
    fig_cm, ax_cm = plt.subplots(figsize=(6, 5))
    im = ax_cm.imshow(cm, interpolation="nearest", cmap="Blues")
    ax_cm.set_title("Matrice de Confusion — Détection de Hit Viral", fontsize=13, fontweight="bold", pad=12)
    classes = ["Standard (<1M)", "Hit (≥1M)"]
    tick_marks = np.arange(len(classes))
    ax_cm.set_xticks(tick_marks)
    ax_cm.set_xticklabels(classes, fontsize=10)
    ax_cm.set_yticks(tick_marks)
    ax_cm.set_yticklabels(classes, fontsize=10)

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val = cm[i, j]
            pct = val / np.sum(cm[i, :]) * 100
            ax_cm.text(
                j,
                i,
                f"{val:,}\n({pct:.1f}%)",
                ha="center",
                va="center",
                color="white" if val > thresh else "black",
                fontweight="bold",
                fontsize=11,
            )
    ax_cm.set_ylabel("Classe Réelle", fontsize=11)
    ax_cm.set_xlabel("Classe Prédite", fontsize=11)
    fig_cm.tight_layout()
    fig_cm.savefig(figures_dir / "confusion_matrix.png", dpi=200)
    plt.close(fig_cm)

    # Figure 3 : Régression Réel vs Prédit
    fig_reg, ax_reg = plt.subplots(figsize=(7, 6))
    ax_reg.scatter(y_reg_test, pred_log_views, alpha=0.25, color="#1b4965", s=18, edgecolors="none")
    min_val = min(y_reg_test.min(), pred_log_views.min())
    max_val = max(y_reg_test.max(), pred_log_views.max())
    ax_reg.plot([min_val, max_val], [min_val, max_val], color="#e63946", lw=2, linestyle="--", label="Idéal (y = ŷ)")
    ax_reg.set_title(f"Régression d'Audience — Log(Vues) Réel vs Prédit ($R^2$ = {r2:.3f})", fontsize=13, fontweight="bold", pad=12)
    ax_reg.set_xlabel("Log(1 + Vues Réelles)", fontsize=11)
    ax_reg.set_ylabel("Log(1 + Vues Prédites)", fontsize=11)
    ax_reg.legend(loc="upper left", frameon=True, fontsize=10)
    fig_reg.tight_layout()
    fig_reg.savefig(figures_dir / "regression_actual_vs_predicted.png", dpi=200)
    plt.close(fig_reg)

    # Figure 4 : Feature Importances (Random Forest)
    if hasattr(reg_model, "feature_importances_"):
        cat_names = preprocessor.named_transformers_["cat"].get_feature_names_out().tolist()
        num_names = NUMERICAL_FEATURES
        all_feat_names = cat_names + num_names
        importances = reg_model.feature_importances_
        sorted_idx = np.argsort(importances)[-12:]

        fig_fi, ax_fi = plt.subplots(figsize=(8, 6))
        ax_fi.barh(range(len(sorted_idx)), importances[sorted_idx], color="#2a9d8f")
        clean_labels = [
            all_feat_names[i]
            .replace("channel_title_", "Chaîne: ")
            .replace("content_type_", "Format: ")
            .replace("channel_content_type_", "Combo: ")
            .replace("f_", "Franchise: ")
            for i in sorted_idx
        ]
        ax_fi.set_yticks(range(len(sorted_idx)))
        ax_fi.set_yticklabels(clean_labels, fontsize=10)
        ax_fi.set_title("Top 12 des Variables les Plus Prédictives d'Audience", fontsize=13, fontweight="bold", pad=12)
        ax_fi.set_xlabel("Importance Relative (Gini)", fontsize=11)
        fig_fi.tight_layout()
        fig_fi.savefig(figures_dir / "feature_importances.png", dpi=200)
        plt.close(fig_fi)

    # Synthèse complète
    evaluation_summary = {
        "evaluation_timestamp": pd.Timestamp.now().isoformat(),
        "test_dataset_size": int(len(y_reg_test)),
        "regression": regression_metrics,
        "classification": classification_metrics,
        "clustering_archetypes": cluster_summary,
        "generated_figures": [
            "reports/figures/roc_curve.png",
            "reports/figures/confusion_matrix.png",
            "reports/figures/regression_actual_vs_predicted.png",
            "reports/figures/feature_importances.png",
        ],
    }

    summary_json_path = reports_dir / "ml_evaluation_metrics.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_summary, f, indent=2, ensure_ascii=False)

    logger.info("Évaluation terminée avec succès. Rapport sauvegardé dans %s", summary_json_path)
    return evaluation_summary


if __name__ == "__main__":
    logger.info("Lancement de l'évaluation du pipeline MLOps...")
    res = generate_evaluation_artifacts()
    print("\n--- RAPPORT SYNTHÉTIQUE D'ÉVALUATION SPRINT 5 ---")
    print(f"Régression (Vues) : R2 = {res['regression']['r2_score']} | RMSE_log = {res['regression']['rmse_log']} | MedAE = {res['regression']['median_absolute_error_views']:,} vues")
    print(f"Classification (Hit) : ROC-AUC = {res['classification']['roc_auc']} | F1 = {res['classification']['f1_score']} | Accuracy = {res['classification']['accuracy'] * 100:.2f}%")
