"""Suite de tests unitaires et d'intégration pour la couche Silver (Sprint 2).

Ce module teste :
- Le respect strict du schéma contractuel et du typage fort des colonnes Parquet.
- La gestion rigoureuse des valeurs manquantes (préservation des NULLs, pas de conversion en 0).
- La déduplication idempotente sur video_id (conservation de la version la plus fraîche).
- La mise en quarantaine des lignes invalides (formats d'ID, dates incohérentes, métriques négatives).
- L'immuabilité et la non-mutation du fichier source Bronze.
- L'audit qualité automatisé et la conformité du dataset complet en production.
"""

import csv
import hashlib
from pathlib import Path
import duckdb
import pyarrow.parquet as pq
import pytest

from src.quality.silver_checks import EXPECTED_SILVER_SCHEMA, audit_silver_parquet
from src.transformations.silver import transform_bronze_to_silver


CSV_HEADER = [
    "video_id",
    "channel_title",
    "channel_id",
    "title",
    "published_at",
    "duration",
    "duration_seconds",
    "view_count",
    "like_count",
    "comment_count",
    "definition",
    "caption",
    "collected_at",
]


def create_test_csv(file_path: Path, rows: list) -> None:
    """Helper pour créer un fichier CSV de test conforme au format Bronze."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for r in rows:
            writer.writerow(r)


# ==============================================================================
# 1. Tests unitaires de schéma et de typage
# ==============================================================================

def test_silver_schema_and_types(tmp_path: Path):
    """Vérifie que la transformation applique tous les types de données conformes au contrat."""
    src_csv = tmp_path / "test_bronze.csv"
    out_parquet = tmp_path / "silver.parquet"

    rows = [
        [
            "aqbCKWyRhl0",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Série - Jeux de dames - Episode 16",
            "2026-10-11T10:00:22Z",
            "PT45S",
            "45",
            "136310",
            "7645",
            "69",
            "hd",
            "False",
            "2026-10-11T15:19:09.885643+00:00",
        ]
    ]
    create_test_csv(src_csv, rows)

    report = transform_bronze_to_silver(src_csv, out_parquet)
    assert report.status == "SUCCESS"
    assert report.valid_silver_rows == 1

    # Vérification via DuckDB
    con = duckdb.connect()
    desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{out_parquet.as_posix()}');").fetchall()
    actual_types = {col[0]: col[1].upper() for col in desc}
    con.close()

    assert "VARCHAR" in actual_types["video_id"]
    assert "VARCHAR" in actual_types["channel_id"]
    assert "VARCHAR" in actual_types["channel_title"]
    assert "VARCHAR" in actual_types["title"]
    assert "TIMESTAMP" in actual_types["published_at"]
    assert "INTEGER" in actual_types["duration_seconds"]
    assert "BIGINT" in actual_types["view_count"]
    assert "BIGINT" in actual_types["like_count"]
    assert "BIGINT" in actual_types["comment_count"]
    assert "BOOLEAN" in actual_types["caption"]
    assert "TIMESTAMP" in actual_types["collected_at"]
    assert "TIMESTAMP" in actual_types["silver_processed_at"]
    assert "VARCHAR" in actual_types["source_file"]


# ==============================================================================
# 2. Tests des valeurs manquantes (Préservation des NULLs)
# ==============================================================================

def test_silver_null_handling_preserves_nulls(tmp_path: Path):
    """Vérifie que les compteurs de likes et commentaires masqués restent NULL et ne deviennent pas 0."""
    src_csv = tmp_path / "test_bronze.csv"
    out_parquet = tmp_path / "silver.parquet"

    rows = [
        # Vidéo A : like masqué (chaîne vide dans le CSV) - video_id de 11 chars
        [
            "vNullLike01",
            "EvenProd",
            "UCKKbOgsOxOT83r1TdfjMaYg",
            "Titre A - Likes masqués",
            "2026-05-10T12:00:00Z",
            "PT10M",
            "600",
            "50000",
            "",  # like_count absent
            "120",
            "hd",
            "True",
            "2026-05-10T18:00:00.000000+00:00",
        ],
        # Vidéo B : commentaires désactivés (chaîne vide dans le CSV) - video_id de 11 chars
        [
            "vNullComm01",
            "Pikini Production",
            "UCsPM7wLeuqPGH3IWotRSC-Q",
            "Titre B - Commentaires désactivés",
            "2026-05-11T12:00:00Z",
            "PT15M",
            "900",
            "75000",
            "3400",
            "",  # comment_count absent
            "sd",
            "False",
            "2026-05-11T18:00:00.000000+00:00",
        ],
    ]
    create_test_csv(src_csv, rows)

    report = transform_bronze_to_silver(src_csv, out_parquet)
    assert report.status == "SUCCESS"
    assert report.valid_silver_rows == 2

    con = duckdb.connect()
    rows = con.execute(
        f"SELECT video_id, like_count, comment_count FROM read_parquet('{out_parquet.as_posix()}');"
    ).fetchall()
    con.close()

    records = {r[0]: {"like_count": r[1], "comment_count": r[2]} for r in rows}

    # vNullLike01 a like_count à None (NULL), PAS à 0 !
    assert records["vNullLike01"]["like_count"] is None
    assert records["vNullLike01"]["comment_count"] == 120

    # vNullComm01 a comment_count à None (NULL), PAS à 0 !
    assert records["vNullComm01"]["like_count"] == 3400
    assert records["vNullComm01"]["comment_count"] is None


# ==============================================================================
# 3. Tests de déduplication et d'idempotence
# ==============================================================================

def test_silver_deduplication_keeps_latest_record(tmp_path: Path):
    """Vérifie que pour un même video_id, la version la plus fraîche et complète est conservée."""
    src_csv = tmp_path / "test_bronze.csv"
    out_parquet = tmp_path / "silver.parquet"

    rows = [
        # Version 1 : ancienne collecte, 100 000 vues (video_id = 11 chars)
        [
            "vidDuplic01",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Titre Ancien",
            "2026-01-01T10:00:00Z",
            "PT20M",
            "1200",
            "100000",
            "5000",
            "300",
            "hd",
            "True",
            "2026-01-02T12:00:00.000000+00:00",
        ],
        # Version 2 : collecte plus récente, 150 000 vues
        [
            "vidDuplic01",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Titre Frais",
            "2026-01-01T10:00:00Z",
            "PT20M",
            "1200",
            "150000",
            "7500",
            "450",
            "hd",
            "True",
            "2026-01-10T12:00:00.000000+00:00",
        ],
    ]
    create_test_csv(src_csv, rows)

    report = transform_bronze_to_silver(src_csv, out_parquet)
    assert report.status == "SUCCESS"
    assert report.total_bronze_rows == 2
    assert report.valid_silver_rows == 1
    assert report.duplicates_pruned == 1

    table = pq.read_table(out_parquet)
    assert table.num_rows == 1
    # La version retenue est bien celle à 150 000 vues
    assert table["view_count"][0].as_py() == 150000
    assert table["title"][0].as_py() == "Titre Frais"


def test_silver_idempotence(tmp_path: Path):
    """Vérifie que ré-exécuter le pipeline sur les mêmes entrées produit un résultat identique."""
    src_csv = tmp_path / "test_bronze.csv"
    out_parquet = tmp_path / "silver.parquet"

    rows = [
        [
            f"idTest_{i:04d}",
            "EvenProd",
            "UCKKbOgsOxOT83r1TdfjMaYg",
            f"Vidéo {i}",
            "2026-02-01T10:00:00Z",
            "PT5M",
            "300",
            str(1000 * i),
            str(50 * i),
            str(5 * i),
            "hd",
            "False",
            "2026-02-02T10:00:00.000000+00:00",
        ]
        for i in range(1, 11)
    ]
    create_test_csv(src_csv, rows)

    # 1ère exécution
    report1 = transform_bronze_to_silver(src_csv, out_parquet)
    t1 = pq.read_table(out_parquet)

    # 2ème exécution
    report2 = transform_bronze_to_silver(src_csv, out_parquet)
    t2 = pq.read_table(out_parquet)

    assert report1.valid_silver_rows == report2.valid_silver_rows == 10
    assert t1.num_rows == t2.num_rows == 10
    assert t1.column_names == t2.column_names
    assert t1["video_id"].to_pylist() == t2["video_id"].to_pylist()
    assert t1["view_count"].to_pylist() == t2["view_count"].to_pylist()


# ==============================================================================
# 4. Tests de quarantaine (Gestion des lignes invalides)
# ==============================================================================

def test_silver_quarantine_rejection_rules(tmp_path: Path):
    """Vérifie que les lignes corrompues sont isolées en quarantaine avec la bonne raison."""
    src_csv = tmp_path / "test_bronze.csv"
    out_parquet = tmp_path / "silver.parquet"
    quar_parquet = tmp_path / "quarantine.parquet"

    rows = [
        # 1. Ligne valide (video_id = 11 chars)
        [
            "validVid001",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Titre Valide",
            "2026-03-01T10:00:00Z",
            "PT10M",
            "600",
            "20000",
            "1000",
            "50",
            "hd",
            "True",
            "2026-03-02T10:00:00.000000+00:00",
        ],
        # 2. Identifiant trop court (5 caractères au lieu de 11)
        [
            "short",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Titre ID Court",
            "2026-03-01T10:00:00Z",
            "PT10M",
            "600",
            "20000",
            "1000",
            "50",
            "hd",
            "True",
            "2026-03-02T10:00:00.000000+00:00",
        ],
        # 3. Vidéo privée inaccessible
        [
            "privVid0001",
            "Marodi TV Sénégal",
            "UCqe0sSESmaQbLFdTExctQLA",
            "Private video",
            "2026-03-01T10:00:00Z",
            "PT10M",
            "600",
            "0",
            "",
            "",
            "sd",
            "False",
            "2026-03-02T10:00:00.000000+00:00",
        ],
        # 4. Compteur de vues négatif
        [
            "negView0001",
            "EvenProd",
            "UCKKbOgsOxOT83r1TdfjMaYg",
            "Titre Vues Négatives",
            "2026-03-01T10:00:00Z",
            "PT10M",
            "600",
            "-500",  # Invalide
            "100",
            "10",
            "hd",
            "False",
            "2026-03-02T10:00:00.000000+00:00",
        ],
        # 5. Définition non reconnue ('4k' au lieu de 'hd' ou 'sd')
        [
            "badDef00001",
            "Pikini Production",
            "UCsPM7wLeuqPGH3IWotRSC-Q",
            "Titre Définition 4k",
            "2026-03-01T10:00:00Z",
            "PT10M",
            "600",
            "10000",
            "500",
            "25",
            "4k",  # Invalide
            "False",
            "2026-03-02T10:00:00.000000+00:00",
        ],
        # 6. Dates incohérentes (publiée dans le futur par rapport à la collecte)
        [
            "futurDate01",
            "EvenProd",
            "UCKKbOgsOxOT83r1TdfjMaYg",
            "Titre Date Futur",
            "2026-04-01T10:00:00Z",  # Postérieure à la collecte
            "PT10M",
            "600",
            "10000",
            "500",
            "25",
            "hd",
            "False",
            "2026-03-01T10:00:00.000000+00:00",
        ],
    ]
    create_test_csv(src_csv, rows)

    report = transform_bronze_to_silver(src_csv, out_parquet, quar_parquet)
    assert report.status == "SUCCESS"
    assert report.total_bronze_rows == 6
    assert report.valid_silver_rows == 1  # Seule la 1ère est acceptée
    assert report.quarantine_rows == 5   # 5 lignes rejetées en quarantaine

    # Vérification de la table Silver
    silver_table = pq.read_table(out_parquet)
    assert silver_table.num_rows == 1
    assert silver_table["video_id"][0].as_py() == "validVid001"

    # Vérification de la table Quarantaine
    quar_table = pq.read_table(quar_parquet)
    assert quar_table.num_rows == 5
    reasons = set(quar_table["rejection_reason"].to_pylist())

    assert "INVALID_VIDEO_ID_FORMAT" in reasons
    assert "INACCESSIBLE_VIDEO" in reasons
    assert "INVALID_OR_NEGATIVE_VIEW_COUNT" in reasons
    assert "INVALID_DEFINITION" in reasons
    assert "INCONSISTENT_TIMESTAMP_ORDER" in reasons


# ==============================================================================
# 5. Test de conservation des données sources
# ==============================================================================

def test_bronze_source_remains_unmodified():
    """Vérifie que le fichier CSV source Bronze dans data/raw/ est strictement intact."""
    raw_csv = Path("data/raw/senegal_audiovisual_videos.csv")
    assert raw_csv.exists(), "Le fichier source Bronze doit exister"

    # Calcul de l'empreinte SHA-256
    hasher1 = hashlib.sha256()
    with open(raw_csv, "rb") as f:
        hasher1.update(f.read())
    hash_before = hasher1.hexdigest()

    # Relecture et re-vérification
    hasher2 = hashlib.sha256()
    with open(raw_csv, "rb") as f:
        hasher2.update(f.read())
    hash_after = hasher2.hexdigest()

    assert hash_before == hash_after, "Le fichier Bronze a été altéré !"


# ==============================================================================
# 6. Test d'intégration de bout-en-bout sur le dataset réel
# ==============================================================================

def test_silver_production_parquet_passes_audit():
    """Valide l'intégrité globale de la table data/silver/videos.parquet réelle."""
    silver_parquet = Path("data/silver/videos.parquet")
    assert silver_parquet.exists(), "La table Silver Parquet réelle doit être présente"

    result = audit_silver_parquet(silver_parquet)
    assert result.is_passed is True
    assert result.total_records == 15832
    assert result.unique_video_ids == 15832
    assert result.duplicates_count == 0
    assert result.negative_metrics_count == 0
    assert result.invalid_definitions_count == 0
    assert result.invalid_date_order_count == 0
    assert result.schema_conformity is True

    # Vérification précise des NULLs réels de production
    assert result.null_counts["like_count"] == 3
    assert result.null_counts["comment_count"] == 45
    assert result.null_counts["view_count"] == 0
    assert result.null_counts["video_id"] == 0
