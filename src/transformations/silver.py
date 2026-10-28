"""Module de transformation de la couche Bronze vers la couche Silver.

Ce module implémente la logique centrale de transformation avec DuckDB :
- Lecture du fichier Bronze brut CSV en mode all_varchar pour un contrôle strict.
- Nettoyage des chaînes (TRIM, suppression d'espaces insécables).
- Détection et isolation des lignes non conformes dans la table de quarantaine.
- Déduplication idempotente sur video_id (conservation de la version la plus fraîche).
- Typage strict (TIMESTAMPTZ, BIGINT, INTEGER, BOOLEAN, VARCHAR).
- Préservation rigoureuse des NULLs pour les métriques désactivées (likes/commentaires).
- Sérialisation colonnaire haute performance en Apache Parquet compressé en Snappy.
- Audit qualité post-écriture et génération d'un rapport d'exécution complet.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, Optional
import duckdb

from src.quality.silver_checks import QualityAuditResult, audit_silver_parquet

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SilverExecutionReport:
    """Rapport d'exécution horodaté de la transformation Silver."""
    status: str
    source_file: str
    silver_file: str
    quarantine_file: Optional[str]
    total_bronze_rows: int
    valid_silver_rows: int
    quarantine_rows: int
    duplicates_pruned: int
    execution_duration_sec: float
    executed_at_utc: str
    quality_audit: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le rapport en dictionnaire."""
        return asdict(self)

    def save_json(self, destination: Path) -> None:
        """Enregistre le rapport sous forme de fichier JSON indenté."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def transform_bronze_to_silver(
    source_csv_path: Path,
    silver_parquet_path: Path,
    quarantine_parquet_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> SilverExecutionReport:
    """Transforme les données Bronze en données nettoyées et typées Silver au format Parquet.

    Args:
        source_csv_path: Chemin du fichier CSV Bronze d'entrée.
        silver_parquet_path: Chemin de destination pour le fichier Parquet Silver.
        quarantine_parquet_path: Chemin de destination pour les données rejetées (optionnel).
        limit: Nombre maximal de lignes à lire pour les tests contrôlés ou échantillons.

    Returns:
        SilverExecutionReport détaillant l'ensemble des opérations et métriques.

    Raises:
        FileNotFoundError: Si le fichier source Bronze n'existe pas.
        RuntimeError: En cas d'erreur de transformation ou d'échec d'audit qualité.
    """
    start_time = time.time()
    executed_at_utc = datetime.now(timezone.utc).isoformat()

    if not source_csv_path.exists():
        raise FileNotFoundError(f"Fichier source Bronze introuvable : {source_csv_path}")

    # Préparation des répertoires de sortie
    silver_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    if quarantine_parquet_path:
        quarantine_parquet_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Démarrage de la transformation Silver avec DuckDB...")
    logger.info(f"Source Bronze : {source_csv_path} (Taille : {source_csv_path.stat().st_size} octets)")
    logger.info(f"Cible Silver  : {silver_parquet_path}")

    con = duckdb.connect(database=":memory:")

    try:
        source_posix = source_csv_path.as_posix()
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""

        # 1. Étape de lecture initiale (Staging brut, all_varchar=true pour aucun crash silencieux)
        con.execute(f"""
            CREATE TEMP TABLE bronze_stage AS
            SELECT
                TRIM(video_id) AS video_id,
                TRIM(channel_title) AS channel_title,
                TRIM(channel_id) AS channel_id,
                TRIM(REPLACE(title, chr(160), ' ')) AS title,
                TRIM(published_at) AS published_at,
                TRIM(duration) AS duration_iso,
                TRIM(duration_seconds) AS duration_seconds,
                TRIM(view_count) AS view_count,
                NULLIF(TRIM(like_count), '') AS like_count,
                NULLIF(TRIM(comment_count), '') AS comment_count,
                LOWER(TRIM(definition)) AS definition,
                LOWER(TRIM(caption)) AS caption,
                TRIM(collected_at) AS collected_at
            FROM read_csv('{source_posix}', header=true, all_varchar=true)
            {limit_clause};
        """)

        total_bronze_rows = con.execute("SELECT count(*) FROM bronze_stage;").fetchone()[0]
        logger.info(f"Lignes Bronze ingérées dans le staging : {total_bronze_rows}")

        # 2. Évaluation des règles de conformité et étiquetage de quarantaine
        con.execute("""
            CREATE TEMP TABLE evaluated_stage AS
            SELECT
                *,
                CASE
                    -- Contrôle de validité de l'identifiant YouTube
                    WHEN video_id IS NULL OR NOT regexp_matches(video_id, '^[a-zA-Z0-9_-]{11}$')
                        THEN 'INVALID_VIDEO_ID_FORMAT'
                    -- Contrôle de l'identifiant de chaîne (UC + 22 caractères)
                    WHEN channel_id IS NULL OR NOT regexp_matches(channel_id, '^UC[a-zA-Z0-9_-]{22}$')
                        THEN 'INVALID_CHANNEL_ID_FORMAT'
                    -- Contrôle du titre (non vide, pas vidéo privée/supprimée)
                    WHEN title IS NULL OR length(title) = 0
                        THEN 'EMPTY_TITLE'
                    WHEN title IN ('Private video', 'Deleted video')
                        THEN 'INACCESSIBLE_VIDEO'
                    -- Contrôle de validité des dates
                    WHEN try_cast(published_at AS TIMESTAMPTZ) IS NULL
                        THEN 'INVALID_PUBLISHED_AT_DATE'
                    WHEN try_cast(collected_at AS TIMESTAMPTZ) IS NULL
                        THEN 'INVALID_COLLECTED_AT_DATE'
                    WHEN try_cast(published_at AS TIMESTAMPTZ) > try_cast(collected_at AS TIMESTAMPTZ)
                        THEN 'INCONSISTENT_TIMESTAMP_ORDER'
                    -- Contrôle des métriques numériques
                    WHEN try_cast(duration_seconds AS INTEGER) IS NULL OR try_cast(duration_seconds AS INTEGER) < 0
                        THEN 'INVALID_OR_NEGATIVE_DURATION'
                    WHEN try_cast(view_count AS BIGINT) IS NULL OR try_cast(view_count AS BIGINT) < 0
                        THEN 'INVALID_OR_NEGATIVE_VIEW_COUNT'
                    WHEN like_count IS NOT NULL AND (try_cast(like_count AS BIGINT) IS NULL OR try_cast(like_count AS BIGINT) < 0)
                        THEN 'INVALID_OR_NEGATIVE_LIKE_COUNT'
                    WHEN comment_count IS NOT NULL AND (try_cast(comment_count AS BIGINT) IS NULL OR try_cast(comment_count AS BIGINT) < 0)
                        THEN 'INVALID_OR_NEGATIVE_COMMENT_COUNT'
                    -- Contrôle des valeurs catégorielles et booléennes
                    WHEN definition NOT IN ('hd', 'sd')
                        THEN 'INVALID_DEFINITION'
                    WHEN caption NOT IN ('true', 'false')
                        THEN 'INVALID_CAPTION_BOOLEAN'
                    ELSE 'VALID'
                END AS validation_status
            FROM bronze_stage;
        """)

        # 3. Isolation des données de quarantaine (si rejetées)
        quarantine_rows = con.execute(
            "SELECT count(*) FROM evaluated_stage WHERE validation_status != 'VALID';"
        ).fetchone()[0]

        if quarantine_rows > 0:
            logger.warning(f"Anomalies détectées : {quarantine_rows} lignes isolées pour quarantaine")
            if quarantine_parquet_path:
                quarantine_posix = quarantine_parquet_path.as_posix()
                con.execute(f"""
                    COPY (
                        SELECT
                            video_id,
                            channel_title,
                            channel_id,
                            title,
                            published_at,
                            duration_iso,
                            duration_seconds,
                            view_count,
                            like_count,
                            comment_count,
                            definition,
                            caption,
                            collected_at,
                            validation_status AS rejection_reason,
                            CURRENT_TIMESTAMP AS rejected_at
                        FROM evaluated_stage
                        WHERE validation_status != 'VALID'
                    ) TO '{quarantine_posix}' (FORMAT PARQUET, COMPRESSION SNAPPY);
                """)
                logger.info(f"Fichier de quarantaine écrit : {quarantine_parquet_path}")

        # 4. Déduplication et typage fort des données conformes (Silver)
        # Règle d'idempotence : ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY collected_at DESC, view_count DESC) = 1
        source_name = source_csv_path.name
        con.execute(f"""
            CREATE TEMP TABLE silver_clean AS
            SELECT
                video_id,
                channel_title,
                channel_id,
                title,
                CAST(published_at AS TIMESTAMPTZ) AS published_at,
                duration_iso,
                CAST(duration_seconds AS INTEGER) AS duration_seconds,
                CAST(view_count AS BIGINT) AS view_count,
                CAST(like_count AS BIGINT) AS like_count,
                CAST(comment_count AS BIGINT) AS comment_count,
                definition,
                CAST(caption AS BOOLEAN) AS caption,
                CAST(collected_at AS TIMESTAMPTZ) AS collected_at,
                CURRENT_TIMESTAMP AS silver_processed_at,
                '{source_name}' AS source_file
            FROM evaluated_stage
            WHERE validation_status = 'VALID'
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY video_id
                ORDER BY try_cast(collected_at AS TIMESTAMPTZ) DESC, try_cast(view_count AS BIGINT) DESC
            ) = 1
            ORDER BY video_id ASC;
        """)

        valid_silver_rows = con.execute("SELECT count(*) FROM silver_clean;").fetchone()[0]
        duplicates_pruned = total_bronze_rows - quarantine_rows - valid_silver_rows
        logger.info(f"Lignes Silver prêtes : {valid_silver_rows} (Doublons écartés : {duplicates_pruned})")

        # 5. Sérialisation colonnaire en Apache Parquet
        silver_posix = silver_parquet_path.as_posix()
        con.execute(f"""
            COPY silver_clean TO '{silver_posix}' (FORMAT PARQUET, COMPRESSION SNAPPY);
        """)
        logger.info(f"Table Silver exportée en Parquet avec succès : {silver_parquet_path}")

        # 6. Audit qualité post-transformation
        quality_result = audit_silver_parquet(silver_parquet_path)
        if not quality_result.is_passed:
            err_msg = f"Échec de l'audit qualité Silver : {quality_result.failures}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        logger.info(f"Audit qualité Silver VALIDÉ à 100% (Qualité : {quality_result.total_records} enregistrements conformes)")

        execution_duration = round(time.time() - start_time, 3)
        return SilverExecutionReport(
            status="SUCCESS",
            source_file=str(source_csv_path),
            silver_file=str(silver_parquet_path),
            quarantine_file=str(quarantine_parquet_path) if quarantine_rows > 0 and quarantine_parquet_path else None,
            total_bronze_rows=total_bronze_rows,
            valid_silver_rows=valid_silver_rows,
            quarantine_rows=quarantine_rows,
            duplicates_pruned=duplicates_pruned,
            execution_duration_sec=execution_duration,
            executed_at_utc=executed_at_utc,
            quality_audit=quality_result.to_dict(),
        )

    except Exception as e:
        logger.error(f"Erreur durant la transformation Silver : {e}", exc_info=True)
        execution_duration = round(time.time() - start_time, 3)
        return SilverExecutionReport(
            status="FAILED",
            source_file=str(source_csv_path),
            silver_file=str(silver_parquet_path),
            quarantine_file=str(quarantine_parquet_path) if quarantine_parquet_path else None,
            total_bronze_rows=0,
            valid_silver_rows=0,
            quarantine_rows=0,
            duplicates_pruned=0,
            execution_duration_sec=execution_duration,
            executed_at_utc=executed_at_utc,
            error_message=str(e),
        )

    finally:
        con.close()
