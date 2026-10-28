"""Module de chargement et de mise en cache des données pour l'application Streamlit (Sprint 6).

Optimisé pour les performances et la résilience mémoire :
- Connexion lecture seule à DuckDB Gold (`data/gold/analytics.duckdb`)
- Chargement sécurisé avec fallback automatique sur `data/silver/videos.parquet`
- Mise en cache intelligente pour une réactivité instantanée de l'interface
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

# Verrouillage multithread pour la stabilité mémoire sous Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import duckdb
import pandas as pd
import streamlit as st

logger = logging.getLogger("app.data_loader")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DB_PATH = PROJECT_ROOT / "data" / "gold" / "analytics.duckdb"
SILVER_PARQUET_PATH = PROJECT_ROOT / "data" / "silver" / "videos.parquet"


@st.cache_data(ttl=3600, show_spinner="Chargement des métriques Gold...")
def load_gold_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Charge les dimensions et faits de la couche Gold DuckDB.
    
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (dim_channels, fct_videos)
    """
    if GOLD_DB_PATH.exists():
        try:
            con = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
            df_channels = con.execute("SELECT * FROM dim_channels ORDER BY total_cumulative_views DESC").df()
            df_videos = con.execute("""
                SELECT 
                    v.video_id,
                    v.channel_id,
                    c.channel_title,
                    v.title,
                    v.content_type,
                    v.duration_minutes,
                    v.duration_category,
                    v.published_at,
                    v.published_date,
                    v.published_year,
                    v.published_month,
                    v.published_day_name,
                    v.published_hour,
                    v.is_weekend,
                    v.view_count,
                    v.like_count,
                    v.comment_count,
                    v.engagement_rate_pct,
                    v.like_view_ratio_pct,
                    v.definition,
                    v.has_caption
                FROM fct_videos_performance v
                LEFT JOIN dim_channels c ON v.channel_id = c.channel_id
            """).df()
            con.close()
            return df_channels, df_videos
        except Exception as exc:
            logger.warning("Échec de lecture DuckDB (%s), bascule sur Parquet Silver...", exc)

    # Fallback direct sur le fichier Parquet Silver
    if SILVER_PARQUET_PATH.exists():
        df_silver = pd.read_parquet(SILVER_PARQUET_PATH)
        # Reconstitution rapide des métriques
        df_channels = df_silver.groupby(["channel_id", "channel_title"]).agg(
            total_videos=("video_id", "count"),
            total_cumulative_views=("view_count", "sum"),
            total_identified_likes=("like_count", "sum"),
            total_identified_comments=("comment_count", "sum"),
        ).reset_index().sort_values("total_cumulative_views", ascending=False)
        return df_channels, df_silver

    raise FileNotFoundError("Aucune source de données disponible dans data/gold ou data/silver.")


@st.cache_data(ttl=3600)
def compute_kpis_summary(df_channels: pd.DataFrame, df_videos: pd.DataFrame) -> Dict[str, Any]:
    """Calcule les indicateurs clés de performance macro-économiques et statistiques enrichis."""
    views = df_videos["view_count"].dropna()
    likes = df_videos["like_count"].dropna()
    comments = df_videos["comment_count"].dropna()
    eng = df_videos["engagement_rate_pct"].dropna()

    total_views = float(views.sum())
    total_likes = float(likes.sum())
    total_comments = float(comments.sum())
    total_videos_count = len(df_videos)

    # Statistiques avancées de distribution
    mean_views = float(views.mean())
    median_views = float(views.median())
    std_views = float(views.std())
    p25_views = float(views.quantile(0.25))
    p75_views = float(views.quantile(0.75))
    p90_views = float(views.quantile(0.90))
    p95_views = float(views.quantile(0.95))
    p99_views = float(views.quantile(0.99))
    max_views = int(views.max()) if len(views) > 0 else 0

    # Niveaux de viralité
    hits_1m = int((views >= 1_000_000).sum())
    mega_hits_2m = int((views >= 2_000_000).sum())
    ultra_hits_5m = int((views >= 5_000_000).sum())

    hit_ratio_pct = (hits_1m / total_videos_count * 100) if total_videos_count > 0 else 0.0
    mega_hit_ratio_pct = (mega_hits_2m / total_videos_count * 100) if total_videos_count > 0 else 0.0

    # Taux d'engagement et interactions
    global_engagement_pct = ((total_likes + total_comments) * 100.0 / total_views) if total_views > 0 else 0.0
    mean_engagement_pct = float(eng.mean()) if len(eng) > 0 else 0.0
    median_engagement_pct = float(eng.median()) if len(eng) > 0 else 0.0

    # Indice de débat public : ratio Likes / Commentaires (un ratio faible indique un fort débat)
    like_comment_ratio = float(total_likes / total_comments) if total_comments > 0 else 0.0

    # Qualité technique
    hd_count = int((df_videos["definition"].str.lower() == "hd").sum())
    hd_ratio_pct = (hd_count / total_videos_count * 100) if total_videos_count > 0 else 0.0
    caption_count = int((df_videos["has_caption"] == 1).sum())
    caption_ratio_pct = (caption_count / total_videos_count * 100) if total_videos_count > 0 else 0.0

    # Répartition des formats
    format_counts = df_videos["content_type"].value_counts().to_dict()

    return {
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_videos_count": total_videos_count,
        "mean_views": mean_views,
        "avg_views": mean_views,
        "median_views": median_views,
        "std_views": std_views,
        "p25_views": p25_views,
        "p75_views": p75_views,
        "p90_views": p90_views,
        "p95_views": p95_views,
        "p99_views": p99_views,
        "max_views": max_views,
        "hit_videos_count": hits_1m,
        "hit_ratio_pct": hit_ratio_pct,
        "mega_hits_2m": mega_hits_2m,
        "mega_hit_ratio_pct": mega_hit_ratio_pct,
        "ultra_hits_5m": ultra_hits_5m,
        "global_engagement_pct": global_engagement_pct,
        "mean_engagement_pct": mean_engagement_pct,
        "median_engagement_pct": median_engagement_pct,
        "like_comment_ratio": like_comment_ratio,
        "hd_ratio_pct": hd_ratio_pct,
        "caption_ratio_pct": caption_ratio_pct,
        "channels_count": len(df_channels),
        "format_counts": format_counts,
    }


@st.cache_data(ttl=3600)
def compute_channel_benchmarks(df_videos: pd.DataFrame) -> pd.DataFrame:
    """Génère un tableau comparatif détaillé des 3 géants audiovisuels sénégalais."""
    summary = []
    for ch_name, grp in df_videos.groupby("channel_title"):
        total_v = len(grp)
        tot_views = grp["view_count"].sum()
        avg_v = grp["view_count"].mean()
        med_v = grp["view_count"].median()
        p90_v = grp["view_count"].quantile(0.90)
        tot_likes = grp["like_count"].sum()
        tot_comments = grp["comment_count"].sum()
        eng_rate = ((tot_likes + tot_comments) * 100.0 / tot_views) if tot_views > 0 else 0.0
        hits_count = (grp["view_count"] >= 1_000_000).sum()
        hit_pct = hits_count / total_v * 100 if total_v > 0 else 0.0
        avg_dur = grp["duration_minutes"].mean()
        hd_pct = (grp["definition"].str.lower() == "hd").sum() / total_v * 100 if total_v > 0 else 0.0

        summary.append({
            "Chaîne": ch_name,
            "Vidéos": total_v,
            "Vues Totales": tot_views,
            "Vues Médianes": med_v,
            "Vues Moyennes": avg_v,
            "P90 Vues": p90_v,
            "Taux d'Engagement (%)": eng_rate,
            "Hits (≥ 1M)": hits_count,
            "Taux de Hits (%)": hit_pct,
            "Durée Moyenne (min)": avg_dur,
            "Taux HD (%)": hd_pct,
        })
    df_res = pd.DataFrame(summary).sort_values("Vues Totales", ascending=False)
    return df_res


@st.cache_data(ttl=3600)
def compute_behavioral_heatmap_matrix(df_videos: pd.DataFrame) -> pd.DataFrame:
    """Calcule la matrice d'audience 2D (Jour de la semaine x Heure de la journée)."""
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    days_fr = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    pivot = df_videos.pivot_table(
        index="published_day_name",
        columns="published_hour",
        values="view_count",
        aggfunc="median",
        fill_value=0,
    )
    # Réorganisation ordonnée des jours
    existing_days = [d for d in days_order if d in pivot.index]
    pivot = pivot.reindex(existing_days)
    pivot.index = [days_fr.get(d, d) for d in pivot.index]
    return pivot


@st.cache_data(ttl=3600)
def compute_franchise_performance(df_videos: pd.DataFrame, franchises: list[str]) -> pd.DataFrame:
    """Analyse les performances des sagas et séries télévisées cultes."""
    results = []
    titles_lower = df_videos["title"].str.lower()

    for franchise in franchises:
        mask = titles_lower.str.contains(franchise, regex=False)
        sub = df_videos[mask]
        count = len(sub)
        if count >= 3:  # Au moins 3 épisodes/teasers pour être significatif
            tot_views = sub["view_count"].sum()
            med_views = sub["view_count"].median()
            avg_views = sub["view_count"].mean()
            hits = (sub["view_count"] >= 1_000_000).sum()
            hit_rate = hits / count * 100 if count > 0 else 0.0
            avg_eng = sub["engagement_rate_pct"].mean()
            main_channel = sub["channel_title"].mode().iloc[0] if len(sub) > 0 else "N/A"

            results.append({
                "Franchise": franchise.title(),
                "Chaîne Principale": main_channel,
                "Nombre d'Épisodes": count,
                "Vues Totales": tot_views,
                "Vues Médianes": med_views,
                "Vues Moyennes": avg_views,
                "Hits (≥ 1M)": hits,
                "Taux de Hits (%)": hit_rate,
                "Engagement Moyen (%)": avg_eng,
            })

    df_fr = pd.DataFrame(results).sort_values("Vues Médianes", ascending=False)
    return df_fr


@st.cache_data(ttl=3600)
def compute_monthly_timeseries(df_videos: pd.DataFrame) -> pd.DataFrame:
    """Agrège la cadence de publication et les audiences par mois historique."""
    df_temp = df_videos.copy()
    df_temp["year_month"] = pd.to_datetime(df_temp["published_at"]).dt.to_period("M").astype(str)
    
    monthly = df_temp.groupby("year_month").agg(
        videos_count=("video_id", "count"),
        total_views=("view_count", "sum"),
        median_views=("view_count", "median"),
        avg_views=("view_count", "mean"),
    ).reset_index().sort_values("year_month")
    
    return monthly

