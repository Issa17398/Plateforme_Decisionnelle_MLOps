"""Module d'ingénierie des caractéristiques (Feature Engineering) et Clustering (Sprint 5).

Ce module extrait les données Gold depuis DuckDB, calcule les variables explicatives,
entraîne une segmentation comportementale non-supervisée (K-Means) et prépare
les matrices d'apprentissage pour la régression et la classification.
"""

from __future__ import annotations

import os
# Optimisation des threads OpenBLAS / OpenMP sur Windows pour éviter les conflits d'allocation
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.features")

# Chemins par défaut
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_GOLD_DB = PROJECT_ROOT / "data" / "gold" / "analytics.duckdb"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "ml"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"

TOP_FRANCHISES = [
    "karma", "bété", "bete", "infidèle", "infidele", "emprise", 
    "virginie", "maîtresse", "maitresse", "pod", "marichou", 
    "idole", "golden", "wiri", "tailleur", "buur", "salma"
]
FRANCHISE_FEATURES = [f"f_{f.replace(' ', '_')}" for f in TOP_FRANCHISES]

# Définition des colonnes
CATEGORICAL_FEATURES = [
    "channel_title",
    "content_type",
    "channel_content_type",
    "duration_category",
    "published_day_name",
    "definition",
    "cluster_id",
]

NUMERICAL_FEATURES = [
    "duration_minutes",
    "published_hour",
    "published_month",
    "is_weekend",
    "has_caption",
    "title_char_length",
    "title_word_count",
    "has_saison_keyword",
    "has_episode_keyword",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
    "log_age_days",
] + FRANCHISE_FEATURES

CLUSTERING_FEATURES = [
    "duration_minutes",
    "published_hour",
    "is_weekend",
    "title_char_length",
]

CLUSTER_ARCHETYPES = {
    "cluster_0": "Prime-Time Long Formats (Séries phares diffusées en soirée)",
    "cluster_1": "Teasers & Micro-capsules virales (Formats courts promo)",
    "cluster_2": "Shorts & Contenus mobiles verticaux",
    "cluster_3": "Programmes après-midi & talk-shows / débats réguliers",
}


def extract_gold_dataset(db_path: Path | str = DEFAULT_GOLD_DB) -> pd.DataFrame:
    """Extrait le dataset d'analyse consolidé depuis la base Gold DuckDB.
    
    Effectue la jointure entre `fct_videos_performance` et `dim_channels`.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Base de données Gold introuvable à l'emplacement : {db_path}")

    query = """
        SELECT 
            f.video_id,
            c.channel_title,
            f.content_type,
            f.title,
            f.duration_seconds,
            f.duration_minutes,
            f.duration_category,
            f.published_at,
            f.published_year,
            f.published_month,
            f.published_day_name,
            f.published_hour,
            f.is_weekend,
            f.definition,
            f.has_caption,
            f.view_count,
            f.like_count,
            f.comment_count,
            f.engagement_rate_pct
        FROM fct_videos_performance f
        JOIN dim_channels c ON f.channel_id = c.channel_id
        WHERE f.view_count >= 0
    """

    logger.info("Connexion à DuckDB : %s", db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(query).df()
        logger.info("Extraction réussie : %d vidéos chargées.", len(df))
    finally:
        con.close()

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les variables explicatives enrichies à partir du DataFrame brut."""
    df_feat = df.copy()

    # Nettoyage et typage de base
    df_feat["channel_title"] = df_feat["channel_title"].fillna("Autre").astype(str)
    df_feat["content_type"] = df_feat["content_type"].fillna("OTHER").astype(str)
    df_feat["duration_category"] = df_feat["duration_category"].fillna("MEDIUM").astype(str)
    df_feat["published_day_name"] = df_feat["published_day_name"].fillna("Unknown").astype(str)
    df_feat["definition"] = df_feat["definition"].fillna("hd").astype(str)
    df_feat["is_weekend"] = df_feat["is_weekend"].astype(int)
    df_feat["has_caption"] = df_feat["has_caption"].astype(int)

    # Durée
    df_feat["duration_minutes"] = df_feat["duration_minutes"].clip(lower=0.1, upper=180.0)

    # Analyse textuelle du titre
    titles = df_feat["title"].fillna("").astype(str)
    df_feat["title_char_length"] = titles.apply(len)
    df_feat["title_word_count"] = titles.apply(lambda t: len(t.split()))

    titles_lower = titles.str.lower()
    df_feat["has_saison_keyword"] = titles_lower.apply(
        lambda t: 1 if any(k in t for k in ["saison", "season", "s1", "s2", "s3", "s4", "s5"]) else 0
    )
    df_feat["has_episode_keyword"] = titles_lower.apply(
        lambda t: 1 if any(k in t for k in ["ep", "épisode", "episode", "part", "partie"]) else 0
    )

    # Encodage cyclique de l'heure (0 à 23)
    df_feat["hour_sin"] = np.sin(2 * np.pi * df_feat["published_hour"] / 24.0)
    df_feat["hour_cos"] = np.cos(2 * np.pi * df_feat["published_hour"] / 24.0)

    # Encodage cyclique du mois (1 à 12)
    df_feat["month_sin"] = np.sin(2 * np.pi * df_feat["published_month"] / 12.0)
    df_feat["month_cos"] = np.cos(2 * np.pi * df_feat["published_month"] / 12.0)

    # Interaction Chaîne x Type
    df_feat["channel_content_type"] = df_feat["channel_title"] + "__" + df_feat["content_type"]

    # Âge et maturité de diffusion (en jours)
    ref_date = pd.to_datetime("2026-10-27", utc=True)
    if "published_at" in df_feat.columns:
        published_dt = pd.to_datetime(df_feat["published_at"], utc=True, errors="coerce").fillna(ref_date)
        age_days = (ref_date - published_dt).dt.days.clip(lower=1).fillna(365)
    else:
        age_days = pd.Series([365] * len(df_feat), index=df_feat.index)
    df_feat["log_age_days"] = np.log1p(age_days)

    # Franchises phares du Sénégal
    for f in TOP_FRANCHISES:
        col_name = f"f_{f.replace(' ', '_')}"
        df_feat[col_name] = titles_lower.apply(lambda t: 1 if f in t else 0)

    # Cibles prédictives
    if "view_count" in df_feat.columns:
        df_feat["target_log_views"] = np.log1p(df_feat["view_count"])
        df_feat["target_is_hit"] = (df_feat["view_count"] >= 1_000_000).astype(int)

    return df_feat


def train_kmeans_segmentation(
    df_train: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> Tuple[MiniBatchKMeans, StandardScaler]:
    """Entraîne un modèle MiniBatchKMeans pour segmenter les types de contenus.
    
    Retourne le modèle entraîné et le scaler associé.
    """
    logger.info("Entraînement de la segmentation K-Means (k=%d)...", n_clusters)
    scaler = StandardScaler()
    X_cluster = scaler.fit_transform(df_train[CLUSTERING_FEATURES])

    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        batch_size=2048,
        n_init=5,
    )
    kmeans.fit(X_cluster)
    logger.info("K-Means entraîné avec succès (Inertie = %.2f).", kmeans.inertia_)
    return kmeans, scaler


def assign_clusters(
    df: pd.DataFrame,
    kmeans: MiniBatchKMeans,
    cluster_scaler: StandardScaler,
) -> pd.DataFrame:
    """Attribue les clusters prédits comme variable catégorielle."""
    df_res = df.copy()
    X_cluster = cluster_scaler.transform(df_res[CLUSTERING_FEATURES])
    cluster_labels = kmeans.predict(X_cluster)
    df_res["cluster_id"] = [f"cluster_{c}" for c in cluster_labels]
    return df_res


def build_preprocessor_pipeline() -> ColumnTransformer:
    """Construit le ColumnTransformer sklearn pour transformer les variables explicatives."""
    categorical_transformer = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    numerical_transformer = StandardScaler()

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
            ("num", numerical_transformer, NUMERICAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


def prepare_ml_data(
    db_path: Path | str = DEFAULT_GOLD_DB,
    test_size: float = 0.2,
    random_state: int = 42,
    save_artifacts: bool = True,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    models_dir: Path | str = DEFAULT_MODELS_DIR,
) -> Dict[str, Any]:
    """Pipeline complet d'ingénierie des caractéristiques et split train/test.
    
    Retourne un dictionnaire contenant les matrices X_train, X_test, y_reg_train,
    y_reg_test, y_clf_train, y_clf_test, le préprocesseur, et les métadonnées.
    """
    output_dir = Path(output_dir)
    models_dir = Path(models_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extraction et Feature Engineering
    df_raw = extract_gold_dataset(db_path)
    df_engineered = engineer_features(df_raw)

    # 2. Split Train/Test stratifié sur target_is_hit
    logger.info("Split Train/Test (ratio test=%.2f, random_state=%d)...", test_size, random_state)
    train_df, test_df = train_test_split(
        df_engineered,
        test_size=test_size,
        random_state=random_state,
        stratify=df_engineered["target_is_hit"],
    )

    # 3. K-Means Clustering sur le Train Set uniquement pour éviter tout data leakage
    kmeans, cluster_scaler = train_kmeans_segmentation(train_df, n_clusters=4, random_state=random_state)
    train_df = assign_clusters(train_df, kmeans, cluster_scaler)
    test_df = assign_clusters(test_df, kmeans, cluster_scaler)

    # 4. Pipeline de préprocessing Sklearn
    preprocessor = build_preprocessor_pipeline()
    logger.info("Ajustement du ColumnTransformer sur le Train Set...")
    X_train_transformed = preprocessor.fit_transform(train_df)
    X_test_transformed = preprocessor.transform(test_df)

    # Obtenir les noms des features
    cat_names = preprocessor.named_transformers_["cat"].get_feature_names_out(CATEGORICAL_FEATURES).tolist()
    all_feature_names = cat_names + NUMERICAL_FEATURES

    # Cibles
    y_reg_train = train_df["target_log_views"].to_numpy()
    y_reg_test = test_df["target_log_views"].to_numpy()
    y_clf_train = train_df["target_is_hit"].to_numpy()
    y_clf_test = test_df["target_is_hit"].to_numpy()

    # Raw views pour évaluation en échelle réelle
    views_test = test_df["view_count"].to_numpy()

    result = {
        "X_train": X_train_transformed,
        "X_test": X_test_transformed,
        "y_reg_train": y_reg_train,
        "y_reg_test": y_reg_test,
        "y_clf_train": y_clf_train,
        "y_clf_test": y_clf_test,
        "views_test": views_test,
        "train_df": train_df,
        "test_df": test_df,
        "feature_names": all_feature_names,
        "preprocessor": preprocessor,
        "kmeans": kmeans,
        "cluster_scaler": cluster_scaler,
    }

    if save_artifacts:
        preprocessor_path = models_dir / "preprocessor.joblib"
        kmeans_path = models_dir / "kmeans_model.joblib"
        cluster_scaler_path = models_dir / "cluster_scaler.joblib"

        joblib.dump(preprocessor, preprocessor_path)
        joblib.dump(kmeans, kmeans_path)
        joblib.dump(cluster_scaler, cluster_scaler_path)

        # Sauvegarde des matrices numpy pour accélération
        np.savez_compressed(
            output_dir / "train_test_data.npz",
            X_train=X_train_transformed,
            X_test=X_test_transformed,
            y_reg_train=y_reg_train,
            y_reg_test=y_reg_test,
            y_clf_train=y_clf_train,
            y_clf_test=y_clf_test,
            views_test=views_test,
        )

        logger.info("Artefacts sauvegardés dans %s et %s.", output_dir, models_dir)

    return result


if __name__ == "__main__":
    logger.info("Démarrage de l'ingénierie des caractéristiques...")
    data = prepare_ml_data()
    print("\n--- RAPPORT FEATURE ENGINEERING ---")
    print(f"X_train shape : {data['X_train'].shape}")
    print(f"X_test shape  : {data['X_test'].shape}")
    print(f"Nombre de features : {len(data['feature_names'])}")
    print(f"Cibles : Log-Views (Régression), Is-Hit (Classification)")
    print(f"Distribution Hits Train : {np.mean(data['y_clf_train']) * 100:.2f}%")
    print(f"Distribution Hits Test  : {np.mean(data['y_clf_test']) * 100:.2f}%")
