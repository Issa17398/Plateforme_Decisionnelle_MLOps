r"""Tests unitaires et d'intégration du module MLOps (Sprint 5).

Valide :
- L'extraction et l'ingénierie des caractéristiques depuis DuckDB Gold.
- Le clustering K-Means non-supervisé.
- La persistance et la conformité des artefacts champions.
- Les seuils de qualité des métriques ML ($R^2 \ge 0.65$, $\text{ROC-AUC} \ge 0.85$).
- L'API d'inférence combinée `AudiovisualPredictor`.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.ml.features import (
    DEFAULT_GOLD_DB,
    DEFAULT_MODELS_DIR,
    DEFAULT_OUTPUT_DIR,
    extract_gold_dataset,
    engineer_features,
    train_kmeans_segmentation,
    assign_clusters,
    build_preprocessor_pipeline,
)
from src.ml.predict import AudiovisualPredictor


@pytest.fixture(scope="module")
def gold_df():
    """Charge un sous-échantillon de données Gold pour les tests."""
    df = extract_gold_dataset(DEFAULT_GOLD_DB)
    return df


def test_gold_dataset_extraction(gold_df):
    """Vérifie que la table Gold est correctement extraite et intègre."""
    assert not gold_df.empty, "Le DataFrame extrait de DuckDB ne doit pas être vide"
    assert len(gold_df) >= 10000, "Le catalogue Gold doit comporter plus de 10 000 vidéos"
    required_cols = [
        "video_id",
        "channel_title",
        "content_type",
        "title",
        "duration_minutes",
        "published_hour",
        "published_day_name",
        "view_count",
    ]
    for col in required_cols:
        assert col in gold_df.columns, f"Colonne requise manquante : {col}"


def test_feature_engineering_enrichment(gold_df):
    """Vérifie l'enrichissement des variables temporelles, textuelles et des cibles."""
    sample = gold_df.head(200).copy()
    df_feat = engineer_features(sample)

    assert "hour_sin" in df_feat.columns
    assert "hour_cos" in df_feat.columns
    assert "month_sin" in df_feat.columns
    assert "month_cos" in df_feat.columns
    assert "title_char_length" in df_feat.columns
    assert "title_word_count" in df_feat.columns
    assert "has_saison_keyword" in df_feat.columns
    assert "has_episode_keyword" in df_feat.columns
    assert "target_log_views" in df_feat.columns
    assert "target_is_hit" in df_feat.columns

    # Vérification des bornes
    assert df_feat["hour_sin"].between(-1.0, 1.0).all()
    assert df_feat["hour_cos"].between(-1.0, 1.0).all()
    assert (df_feat["target_log_views"] >= 0).all()
    assert set(df_feat["target_is_hit"].unique()).issubset({0, 1})


def test_kmeans_clustering_assignment(gold_df):
    """Vérifie le partitionnement non-supervisé K-Means."""
    sample = gold_df.head(500).copy()
    df_feat = engineer_features(sample)
    kmeans, scaler = train_kmeans_segmentation(df_feat, n_clusters=4, random_state=42)

    df_clustered = assign_clusters(df_feat, kmeans, scaler)
    assert "cluster_id" in df_clustered.columns
    unique_clusters = set(df_clustered["cluster_id"].unique())
    assert len(unique_clusters) == 4, "4 clusters distincts doivent être assignés"
    for c in unique_clusters:
        assert c.startswith("cluster_")


def test_preprocessor_pipeline_transformation(gold_df):
    """Vérifie l'encodage et la mise à l'échelle par le ColumnTransformer."""
    sample = gold_df.head(300).copy()
    df_feat = engineer_features(sample)
    kmeans, scaler = train_kmeans_segmentation(df_feat, n_clusters=4, random_state=42)
    df_clustered = assign_clusters(df_feat, kmeans, scaler)

    preprocessor = build_preprocessor_pipeline()
    X_transformed = preprocessor.fit_transform(df_clustered)

    assert isinstance(X_transformed, np.ndarray)
    assert X_transformed.shape[0] == len(sample)
    assert X_transformed.shape[1] > 20, "La matrice transformée doit comporter au moins 20 colonnes"
    assert not np.isnan(X_transformed).any(), "Aucune valeur NaN tolérée dans la matrice de features"


def test_champion_artifacts_persistence():
    """Vérifie que les artefacts champions et métadonnées sont bien sauvegardés."""
    reg_path = DEFAULT_MODELS_DIR / "regressor_champion.joblib"
    clf_path = DEFAULT_MODELS_DIR / "classifier_champion.joblib"
    prep_path = DEFAULT_MODELS_DIR / "preprocessor.joblib"
    km_path = DEFAULT_MODELS_DIR / "kmeans_model.joblib"
    meta_path = DEFAULT_MODELS_DIR / "ml_metadata.json"

    assert reg_path.exists(), "Le modèle champion de régression doit exister"
    assert clf_path.exists(), "Le modèle champion de classification doit exister"
    assert prep_path.exists(), "Le préprocesseur ColumnTransformer doit exister"
    assert km_path.exists(), "Le modèle K-Means doit exister"
    assert meta_path.exists(), "Le fichier de métadonnées ml_metadata.json doit exister"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "regression_champion" in meta
    assert "classification_champion" in meta
    assert meta["regression_champion"]["metrics"]["r2_score"] >= 0.65
    assert meta["classification_champion"]["metrics"]["roc_auc"] >= 0.85


def test_evaluation_report_metrics():
    """Vérifie les métriques calculées dans le rapport officiel d'évaluation."""
    report_path = Path("reports/ml_evaluation_metrics.json")
    assert report_path.exists(), "Le rapport reports/ml_evaluation_metrics.json doit exister"

    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    reg = rep["regression"]
    clf = rep["classification"]

    # R2 >= 0.70 et ROC-AUC >= 0.90
    assert reg["r2_score"] >= 0.70, f"R2 trop faible : {reg['r2_score']}"
    assert clf["roc_auc"] >= 0.90, f"ROC-AUC trop faible : {clf['roc_auc']}"
    assert clf["accuracy"] >= 0.90, f"Accuracy trop faible : {clf['accuracy']}"
    assert clf["f1_score"] >= 0.80, f"F1-score trop faible : {clf['f1_score']}"

    # Vérification des graphiques
    for fig in rep["generated_figures"]:
        fig_path = Path(fig)
        assert fig_path.exists(), f"Figure générée manquante : {fig}"


def test_predictor_single_inference():
    """Vérifie le bon fonctionnement du service de prédiction `AudiovisualPredictor`."""
    predictor = AudiovisualPredictor()

    input_data = {
        "channel_title": "EvenProd",
        "title": "Idoles Saison 4 Episode 12",
        "content_type": "EPISODE",
        "duration_minutes": 35.0,
        "published_hour": 20,
        "published_day_name": "Friday",
    }

    result = predictor.predict(input_data)

    assert "predicted_views" in result
    assert "confidence_interval_80pct" in result
    assert "hit_probability_pct" in result
    assert "is_hit_predicted" in result
    assert "verdict" in result
    assert "audience_archetype" in result
    assert "strategic_recommendations" in result

    assert result["predicted_views"] > 0
    assert result["confidence_interval_80pct"]["lower_bound"] <= result["predicted_views"]
    assert result["confidence_interval_80pct"]["upper_bound"] >= result["predicted_views"]
    assert 0.0 <= result["hit_probability_pct"] <= 100.0
    assert len(result["strategic_recommendations"]) > 0


def test_predictor_comparative_logic():
    """Vérifie la cohérence métier des prédictions (Prime Time Episode vs Short décalé)."""
    predictor = AudiovisualPredictor()

    blockbuster = {
        "channel_title": "Marodi TV Sénégal",
        "title": "Karma Saison 3 Episode Final",
        "content_type": "EPISODE",
        "duration_minutes": 45.0,
        "published_hour": 20,
        "published_day_name": "Friday",
    }

    short_clip = {
        "channel_title": "Pikini Production",
        "title": "Coulisses du tournage",
        "content_type": "SHORT",
        "duration_minutes": 0.5,
        "published_hour": 4,
        "published_day_name": "Tuesday",
    }

    res_blockbuster = predictor.predict(blockbuster)
    res_short = predictor.predict(short_clip)

    assert res_blockbuster["predicted_views"] > res_short["predicted_views"], (
        "Un épisode prime-time de Marodi doit avoir une prédiction d'audience supérieure à un short de nuit"
    )
    assert res_blockbuster["hit_probability_pct"] > res_short["hit_probability_pct"], (
        "La probabilité de hit viral doit être significativement supérieure pour le blockbuster"
    )
