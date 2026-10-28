"""Tests automatisés pour l'application décisionnelle Streamlit enrichie (Sprint 6)."""

import os
from pathlib import Path
import pytest
import pandas as pd

# Fix multithread pour OpenBLAS sous Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from app.charts import (
    plot_ab_comparison,
    plot_behavioral_heatmap_2d,
    plot_confidence_interval,
    plot_confusion_matrix_interactive,
    plot_debate_vs_consensus_scatter,
    plot_engagement_vs_views_scatter,
    plot_format_distribution_box,
    plot_franchises_benchmark,
    plot_hit_gauge,
    plot_hourly_audience,
    plot_market_share,
    plot_monthly_evolution,
    plot_views_by_content_type,
)
from app.data_loader import (
    compute_behavioral_heatmap_matrix,
    compute_channel_benchmarks,
    compute_franchise_performance,
    compute_kpis_summary,
    compute_monthly_timeseries,
    load_gold_data,
)
from app.sentiment_data import (
    compute_franchise_sentiment_benchmarks,
    compute_sentiment_kpis,
    generate_extended_sentiment_dataset,
    plot_sentiment_by_franchise,
    plot_sentiment_donut,
    plot_sentiment_nss_benchmark,
)
from src.ml.features import TOP_FRANCHISES
from src.ml.sentiment import SenegalSentimentAnalyzer


def test_data_loader_returns_valid_dataframes():
    """Vérifie que le chargeur de données retourne deux DataFrames cohérents."""
    df_channels, df_videos = load_gold_data()
    assert isinstance(df_channels, pd.DataFrame)
    assert isinstance(df_videos, pd.DataFrame)
    assert len(df_channels) >= 3
    assert len(df_videos) > 1000
    assert "channel_title" in df_channels.columns
    assert "view_count" in df_videos.columns
    assert "content_type" in df_videos.columns


def test_compute_kpis_summary_enriched():
    """Vérifie le calcul des KPIs macro-économiques et statistiques de distribution."""
    df_channels, df_videos = load_gold_data()
    kpis = compute_kpis_summary(df_channels, df_videos)
    assert kpis["total_views"] > 0
    assert kpis["total_videos_count"] == len(df_videos)
    assert kpis["hit_videos_count"] > 0
    assert kpis["median_views"] > 0
    assert kpis["p90_views"] >= kpis["median_views"]
    assert 0 <= kpis["hit_ratio_pct"] <= 100
    assert 0 <= kpis["global_engagement_pct"] <= 100
    assert kpis["like_comment_ratio"] > 0


def test_channel_benchmarks_and_behavioral_matrices():
    """Vérifie les fonctions analytiques de benchmark et de matrice 2D."""
    df_channels, df_videos = load_gold_data()
    
    df_bench = compute_channel_benchmarks(df_videos)
    assert isinstance(df_bench, pd.DataFrame)
    assert len(df_bench) >= 3
    assert "Vues Totales" in df_bench.columns

    pivot_heat = compute_behavioral_heatmap_matrix(df_videos)
    assert isinstance(pivot_heat, pd.DataFrame)
    assert pivot_heat.shape[0] >= 5
    assert pivot_heat.shape[1] >= 12

    df_fr = compute_franchise_performance(df_videos, TOP_FRANCHISES)
    assert isinstance(df_fr, pd.DataFrame)
    assert len(df_fr) > 0

    df_month = compute_monthly_timeseries(df_videos)
    assert isinstance(df_month, pd.DataFrame)
    assert len(df_month) > 10


def test_all_plotly_charts_generation():
    """Vérifie que l'ensemble des graphiques Plotly se génèrent sans erreur."""
    df_channels, df_videos = load_gold_data()
    pivot_heat = compute_behavioral_heatmap_matrix(df_videos)
    df_fr = compute_franchise_performance(df_videos, TOP_FRANCHISES)
    df_month = compute_monthly_timeseries(df_videos)

    assert plot_market_share(df_channels) is not None
    assert plot_views_by_content_type(df_videos) is not None
    assert plot_hourly_audience(df_videos) is not None
    assert plot_behavioral_heatmap_2d(pivot_heat) is not None
    assert plot_engagement_vs_views_scatter(df_videos) is not None
    assert plot_debate_vs_consensus_scatter(df_videos) is not None
    assert plot_format_distribution_box(df_videos) is not None
    assert plot_monthly_evolution(df_month) is not None
    assert plot_franchises_benchmark(df_fr) is not None
    assert plot_hit_gauge(88.5) is not None
    assert plot_confidence_interval(500000, 200000, 1200000) is not None
    assert plot_ab_comparison(400000, 650000, "A", "B") is not None

    cm_data = {"true_negatives": 2400, "false_positives": 43, "false_negatives": 81, "true_positives": 643}
    assert plot_confusion_matrix_interactive(cm_data) is not None


def test_sentiment_analysis_engine_and_dataset():
    """Vérifie le fonctionnement du moteur NLP de sentiment bilingue et des visualisations."""
    analyzer = SenegalSentimentAnalyzer()

    # Test phrase positive en wolof/français
    res_pos = analyzer.analyze_comment("Machallah actrice bi dafa meun série bi nekh na torop ! Bravo aux acteurs.")
    assert res_pos["sentiment"] == "POSITIF"
    assert res_pos["polarity"] > 0
    assert len(res_pos["keywords_positive"]) > 0

    # Test phrase négative avec critique
    res_neg = analyzer.analyze_comment("Doy na waar trop de publicités et lenteur, le scénario est complètement gâché.")
    assert res_neg["sentiment"] == "NÉGATIF"
    assert res_neg["polarity"] < 0
    assert len(res_neg["keywords_negative"]) > 0

    # Test phrase neutre / question
    res_neu = analyzer.analyze_comment("À quelle heure sort l'épisode 45 ?")
    assert res_neu["sentiment"] == "NEUTRE"

    # Test dataset et KPIs
    df_sent = generate_extended_sentiment_dataset(n_samples=50)
    assert len(df_sent) == 50
    assert "sentiment" in df_sent.columns

    kpis = compute_sentiment_kpis(df_sent)
    assert kpis["total_comments"] == 50
    assert -100 <= kpis["net_sentiment_score"] <= 100

    df_bench = compute_franchise_sentiment_benchmarks(df_sent)
    assert len(df_bench) > 0
    assert "Score NSS (Net)" in df_bench.columns

    # Test graphiques de sentiment
    assert plot_sentiment_donut(kpis) is not None
    assert plot_sentiment_by_franchise(df_bench) is not None
    assert plot_sentiment_nss_benchmark(df_bench) is not None


def test_streamlit_app_renders_all_7_tabs():
    """Vérifie que l'application complète s'exécute sans exception et affiche 7 onglets."""
    from streamlit.testing.v1 import AppTest
    
    app_path = Path(__file__).resolve().parent.parent / "app" / "main.py"
    at = AppTest.from_file(str(app_path), default_timeout=35)
    at.run()
    assert not at.exception
    assert len(at.tabs) == 7
