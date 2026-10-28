"""Module de contrôles qualité (Data Quality Checks) pour la couche Silver.

Ce module implémente des vérifications rigoureuses sur la table Parquet Silver :
- Respect strict du schéma colonnaire et des types de données.
- Vérification de l'unicité de la clé primaire (video_id).
- Contrôle des contraintes de non-nullité (NOT NULL).
- Préservation explicite des NULLs légitimes (like_count, comment_count).
- Cohérence temporelle (published_at <= collected_at).
- Bornes de validité des métriques numériques (durée, vues, likes, commentaires).
"""

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb

logger = logging.getLogger(__name__)

# Schéma contractuel attendu pour la couche Silver
EXPECTED_SILVER_SCHEMA: Dict[str, str] = {
    "video_id": "VARCHAR",
    "channel_title": "VARCHAR",
    "channel_id": "VARCHAR",
    "title": "VARCHAR",
    "published_at": "TIMESTAMP WITH TIME ZONE",
    "duration_iso": "VARCHAR",
    "duration_seconds": "INTEGER",
    "view_count": "BIGINT",
    "like_count": "BIGINT",
    "comment_count": "BIGINT",
    "definition": "VARCHAR",
    "caption": "BOOLEAN",
    "collected_at": "TIMESTAMP WITH TIME ZONE",
    "silver_processed_at": "TIMESTAMP WITH TIME ZONE",
    "source_file": "VARCHAR",
}

# Colonnes obligatoires ne devant contenir aucun NULL
MANDATORY_NON_NULL_COLUMNS: List[str] = [
    "video_id",
    "channel_title",
    "channel_id",
    "title",
    "published_at",
    "duration_iso",
    "duration_seconds",
    "view_count",
    "definition",
    "caption",
    "collected_at",
    "silver_processed_at",
    "source_file",
]


@dataclass(frozen=True)
class QualityAuditResult:
    """Résultat consolidé de l'audit qualité de la table Silver."""
    total_records: int
    unique_video_ids: int
    duplicates_count: int
    null_counts: Dict[str, int]
    negative_metrics_count: int
    invalid_definitions_count: int
    invalid_date_order_count: int
    schema_conformity: bool
    is_passed: bool
    failures: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'audit en dictionnaire sérialisable."""
        return asdict(self)


def audit_silver_parquet(parquet_path: Path) -> QualityAuditResult:
    """Exécute un audit de qualité complet sur un fichier Parquet Silver.

    Args:
        parquet_path: Chemin absolu ou relatif vers le fichier Parquet Silver.

    Returns:
        QualityAuditResult contenant l'ensemble des métriques de conformité.

    Raises:
        FileNotFoundError: Si le fichier Parquet n'existe pas.
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Fichier Parquet introuvable : {parquet_path}")

    failures: List[str] = []
    con = duckdb.connect(database=":memory:")

    try:
        # 1. Vérification du schéma réel
        schema_query = f"DESCRIBE SELECT * FROM read_parquet('{parquet_path.as_posix()}');"
        columns_desc = con.execute(schema_query).fetchall()
        actual_schema = {col[0]: col[1].upper() for col in columns_desc}

        schema_conformity = True
        for col_name, expected_type in EXPECTED_SILVER_SCHEMA.items():
            if col_name not in actual_schema:
                failures.append(f"Colonne manquante dans le schéma : '{col_name}'")
                schema_conformity = False
            else:
                actual_type = actual_schema[col_name]
                # DuckDB peut exprimer TIMESTAMP_TZ ou TIMESTAMP WITH TIME ZONE
                if expected_type == "TIMESTAMP WITH TIME ZONE" and "TIMESTAMP" in actual_type:
                    continue
                if expected_type not in actual_type:
                    failures.append(
                        f"Type incohérent pour '{col_name}' : attendu '{expected_type}', obtenu '{actual_type}'"
                    )
                    schema_conformity = False

        # 2. Métriques globales (volume et doublons)
        metrics = con.execute(f"""
            SELECT
                count(*) AS total_records,
                count(DISTINCT video_id) AS unique_video_ids,
                count(*) - count(DISTINCT video_id) AS duplicates_count,
                sum(CASE WHEN duration_seconds < 0 THEN 1 ELSE 0 END) +
                sum(CASE WHEN view_count < 0 THEN 1 ELSE 0 END) +
                sum(CASE WHEN like_count IS NOT NULL AND like_count < 0 THEN 1 ELSE 0 END) +
                sum(CASE WHEN comment_count IS NOT NULL AND comment_count < 0 THEN 1 ELSE 0 END) AS negative_metrics_count,
                sum(CASE WHEN definition NOT IN ('hd', 'sd') THEN 1 ELSE 0 END) AS invalid_definitions_count,
                sum(CASE WHEN published_at > collected_at THEN 1 ELSE 0 END) AS invalid_date_order_count
            FROM read_parquet('{parquet_path.as_posix()}');
        """).fetchone()

        total_records = metrics[0] or 0
        unique_video_ids = metrics[1] or 0
        duplicates_count = metrics[2] or 0
        negative_metrics_count = metrics[3] or 0
        invalid_definitions_count = metrics[4] or 0
        invalid_date_order_count = metrics[5] or 0

        if duplicates_count > 0:
            failures.append(f"Présence de {duplicates_count} doublons sur la clé primaire video_id")

        if negative_metrics_count > 0:
            failures.append(f"Présence de {negative_metrics_count} métriques numériques négatives")

        if invalid_definitions_count > 0:
            failures.append(f"Présence de {invalid_definitions_count} définitions vidéo hors 'hd'/'sd'")

        if invalid_date_order_count > 0:
            failures.append(f"Présence de {invalid_date_order_count} dates incohérentes (published_at > collected_at)")

        # 3. Vérification des contraintes NULL
        null_counts: Dict[str, int] = {}
        for col_name in actual_schema.keys():
            res = con.execute(
                f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}') WHERE {col_name} IS NULL;"
            ).fetchone()
            cnt = res[0] if res else 0
            null_counts[col_name] = cnt
            if col_name in MANDATORY_NON_NULL_COLUMNS and cnt > 0:
                failures.append(f"La colonne obligatoire '{col_name}' contient {cnt} valeurs NULL")

        is_passed = len(failures) == 0 and total_records > 0 and schema_conformity

        return QualityAuditResult(
            total_records=total_records,
            unique_video_ids=unique_video_ids,
            duplicates_count=duplicates_count,
            null_counts=null_counts,
            negative_metrics_count=negative_metrics_count,
            invalid_definitions_count=invalid_definitions_count,
            invalid_date_order_count=invalid_date_order_count,
            schema_conformity=schema_conformity,
            is_passed=is_passed,
            failures=failures,
        )

    finally:
        con.close()
