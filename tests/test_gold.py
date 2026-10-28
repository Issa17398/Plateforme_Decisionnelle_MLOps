"""Suite de tests unitaires et d'intégration pour la couche Gold (Sprint 3).

Ce module teste :
- L'intégrité de la base analytique DuckDB produite par dbt.
- La dimension dim_channels (exactitude des 3 maisons de production, volume agrégé).
- La table de faits fct_videos_performance (exhaustivité de 15 832 vidéos, unicité de la clé).
- La cohérence des règles de classification (content_type, duration_category).
- La rigueur des métriques d'engagement (préservation des NULLs, aucune division par zéro).
- L'intégrité référentielle entre les faits et les dimensions.
"""

from pathlib import Path
import duckdb
import pytest

GOLD_DB_PATH = Path("data/gold/analytics.duckdb")


def test_gold_database_exists():
    """Vérifie que la base DuckDB générée par dbt est présente."""
    assert GOLD_DB_PATH.exists(), f"La base de données {GOLD_DB_PATH} doit exister après dbt run."
    assert GOLD_DB_PATH.stat().st_size > 0


def test_dim_channels_integrity():
    """Valide l'intégrité et la complétude de la dimension dim_channels."""
    con = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        rows = con.execute("SELECT * FROM dim_channels;").fetchall()
        assert len(rows) == 3, "Il doit y avoir exactement 3 chaînes de production"

        metrics = con.execute("""
            SELECT
                count(distinct channel_id) as unique_channels,
                sum(total_videos) as total_vids,
                min(total_videos) as min_vids
            FROM dim_channels;
        """).fetchone()

        assert metrics[0] == 3, "Les 3 channel_id doivent être uniques"
        assert metrics[1] == 15832, "Le total cumulé des vidéos des chaînes doit être 15 832"
        assert metrics[2] > 0, "Chaque chaîne doit avoir un nombre positif de vidéos"

        titles = con.execute("SELECT channel_title FROM dim_channels ORDER BY channel_title").fetchall()
        channel_names = [t[0] for t in titles]
        assert "EvenProd" in channel_names
        assert "Marodi TV Sénégal" in channel_names
        assert "Pikini Production" in channel_names
    finally:
        con.close()


def test_fct_videos_performance_integrity():
    """Valide la granularité, les volumes et l'absence de doublons dans la table de faits."""
    con = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        res = con.execute("""
            SELECT
                count(*) as total_rows,
                count(distinct video_id) as unique_videos,
                sum(case when video_id is null then 1 else 0 end) as null_vids,
                sum(case when channel_id is null then 1 else 0 end) as null_chids,
                sum(case when published_at is null then 1 else 0 end) as null_dates,
                sum(case when view_count is null then 1 else 0 end) as null_views
            FROM fct_videos_performance;
        """).fetchone()

        assert res[0] == 15832, "La table de faits doit contenir exactement 15 832 vidéos"
        assert res[1] == 15832, "Chaque video_id doit être unique"
        assert res[2] == 0, "Aucun video_id NULL"
        assert res[3] == 0, "Aucun channel_id NULL"
        assert res[4] == 0, "Aucune date NULL"
        assert res[5] == 0, "Aucun view_count NULL"
    finally:
        con.close()


def test_fct_videos_classification_and_metrics():
    """Valide les catégories métier et les calculs de ratios d'engagement."""
    con = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        # 1. Vérification des types de contenu
        types = con.execute("""
            SELECT distinct content_type FROM fct_videos_performance;
        """).fetchall()
        found_types = {t[0] for t in types}
        assert found_types.issubset({"TEASER", "EPISODE", "SHORT", "OTHER"})

        # 2. Vérification des catégories de durée
        dur_cats = con.execute("""
            SELECT distinct duration_category FROM fct_videos_performance;
        """).fetchall()
        found_cats = {d[0] for d in dur_cats}
        assert found_cats.issubset({
            "< 1 min (Short)",
            "1-5 min (Teaser/Clip)",
            "5-20 min (Moyen format)",
            "> 20 min (Épisode long)",
        })

        # 3. Vérification des NULLs légitimes préservés
        null_counts = con.execute("""
            SELECT
                sum(case when like_count is null then 1 else 0 end) as null_likes,
                sum(case when comment_count is null then 1 else 0 end) as null_comments,
                sum(case when like_view_ratio_pct is null then 1 else 0 end) as null_like_ratios,
                sum(case when comment_view_ratio_pct is null then 1 else 0 end) as null_comm_ratios,
                min(engagement_rate_pct) as min_engagement,
                max(engagement_rate_pct) as max_engagement
            FROM fct_videos_performance;
        """).fetchone()

        assert null_counts[0] == 3, "Exactement 3 likes NULL doivent être préservés"
        assert null_counts[1] == 45, "Exactement 45 commentaires NULL doivent être préservés"
        assert null_counts[2] == 3, "Le ratio like/vue doit être NULL pour les 3 likes masqués"
        assert null_counts[3] == 45, "Le ratio comment/vue doit être NULL pour les 45 coms fermés"
        assert null_counts[4] >= 0.0, "Le taux d'engagement minimal ne peut pas être négatif"
    finally:
        con.close()


def test_gold_referential_integrity():
    """Vérifie que chaque vidéo de la table de faits pointe vers une chaîne existante."""
    con = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        orphan_count = con.execute("""
            SELECT count(*)
            FROM fct_videos_performance f
            LEFT JOIN dim_channels c ON f.channel_id = c.channel_id
            WHERE c.channel_id IS NULL;
        """).fetchone()[0]

        assert orphan_count == 0, "Aucune vidéo orpheline ne doit exister"
    finally:
        con.close()
