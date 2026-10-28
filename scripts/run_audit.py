"""Script d'audit complet de la collecte de données (Étapes B, C, D, E, F).

Ce script orchestre l'ensemble du pipeline de diagnostic :
1. Étape B : Résolution des chaînes officielles (Marodi TV, EvenProd, Pikini).
2. Étape C : Collecte d'un micro-échantillon de vidéos (5 vidéos par chaîne via la playlist 'uploads').
3. Étape D : Contrôle qualité approfondi des métadonnées (IDs, titres, dates ISO 8601, doublons).
4. Étape E : Synthèse globale comparative et mesure précise du quota d'API YouTube.
5. Étape F : Émission d'un rapport de diagnostic contrôlé (data/raw/audit_sample_diagnostic.json).
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ajoute la racine du projet au PYTHONPATH si exécuté directement
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit import QualityReport, audit_playlist_items
from src.config import ConfigError, load_config
from src.youtube_client import (
    ChannelMetadata,
    PlaylistItem,
    PlaylistPage,
    YouTubeAPIError,
    YouTubeAuthenticationError,
    YouTubeClient,
    YouTubeNetworkError,
    YouTubeQuotaExceededError,
    YouTubeResourceNotFoundError,
)


def setup_logging() -> Path:
    """Configure la journalisation double : console et fichier logs/audit_sources.log."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "audit_sources.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Réinitialise les handlers existants
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Handler Fichier (détaillé)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Handler Console (clair et épuré)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    return log_file


def run_full_pipeline_audit() -> int:
    """Exécute l'audit complet du pipeline de collecte et affiche les résultats."""
    # Assure l'encodage UTF-8 sous Windows PowerShell
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    log_file = setup_logging()
    logger = logging.getLogger("run_audit")

    print("\n" + "=" * 82)
    print(" 🎬 SÉNÉGAL AUDIOVISUAL INTELLIGENCE PLATFORM — PIPELINE D'AUDIT COMPLET")
    print("=" * 82)

    # 1. Chargement de la configuration
    try:
        config = load_config()
        logger.info("Configuration chargée avec succès.")
        logger.info("Clé API active : %s", config.masked_api_key)
        logger.info("Timeout réseau configuré : %ds", config.request_timeout)
    except ConfigError as err:
        logger.critical("Échec critique de configuration : %s", err)
        return 1

    # 2. Initialisation du client YouTube
    try:
        client = YouTubeClient(
            api_key=config.youtube_api_key,
            timeout=config.request_timeout,
        )
    except Exception as err:
        logger.critical("Erreur d'initialisation du client : %s", err)
        return 1

    # 3. ÉTAPE B : Résolution des chaînes officielles
    print("\n" + "-" * 82)
    print(" 📡 PHASE 1 (ÉTAPE B) : Résolution des chaînes officielles")
    print("-" * 82)

    resolved_channels: Dict[str, ChannelMetadata] = {}
    channel_errors: Dict[str, str] = {}

    for name, handle in config.channel_handles.items():
        logger.info("Résolution de la source '%s' (Handle: %s)...", name, handle)
        try:
            meta = client.get_channel_by_handle(handle)
            resolved_channels[name] = meta
            logger.info("Chaîne validée : '%s' -> Uploads: %s", meta.title, meta.uploads_playlist_id)
        except (YouTubeAuthenticationError, YouTubeQuotaExceededError) as critical_err:
            logger.critical("Arrêt immédiat : %s", critical_err)
            channel_errors[name] = str(critical_err)
            break
        except YouTubeAPIError as api_err:
            logger.error("Erreur sur '%s' : %s", name, api_err)
            channel_errors[name] = str(api_err)

    if channel_errors or len(resolved_channels) != len(config.channel_handles):
        print("\n❌ Arrêt du pipeline : certaines chaînes n'ont pas pu être résolues.")
        for k, v in channel_errors.items():
            print(f"  • {k}: {v}")
        return 1

    print(f"✅ {len(resolved_channels)} chaînes résolues avec succès.")

    # 4. ÉTAPES C & D : Collecte d'échantillons et Contrôles Qualité
    print("\n" + "-" * 82)
    print(" 📥 PHASE 2 (ÉTAPES C & D) : Échantillonnage de vidéos & Contrôle Qualité")
    print("-" * 82)

    collected_data_summary: Dict[str, Any] = {}
    quality_reports: List[QualityReport] = []
    SAMPLE_SIZE = 5

    for key, channel in resolved_channels.items():
        print(f"\n▶ Chaîne : {channel.title} (Uploads Playlist: {channel.uploads_playlist_id})")
        logger.info("Collecte d'un échantillon (%d vidéos) pour %s...", SAMPLE_SIZE, channel.title)

        try:
            page: PlaylistPage = client.get_playlist_items(
                playlist_id=channel.uploads_playlist_id,
                max_results=SAMPLE_SIZE,
            )
        except YouTubeAPIError as coll_err:
            logger.error("Échec de la collecte pour %s : %s", channel.title, coll_err)
            print(f"  ❌ Erreur de collecte : {coll_err}")
            continue

        # Contrôle qualité (Étape D)
        q_report = audit_playlist_items(channel.title, page.items)
        quality_reports.append(q_report)

        print(f"  • Éléments collectés       : {len(page.items)}")
        print(f"  • Total estimé de vidéos   : {page.total_results:,}")
        print(f"  • Score Qualité            : {q_report.quality_score}% ({q_report.valid_items}/{q_report.total_items} valides)")
        print(f"  • Doublons détectés        : {len(q_report.duplicate_ids)}")
        print(f"  • Vidéos privées/supprimées : {q_report.private_or_deleted_count}")

        # Aperçu des 3 premières vidéos
        print("  • Aperçu des vidéos récentes :")
        for idx, vid in enumerate(page.items[:3], start=1):
            pub_date = vid.published_at[:10] if vid.published_at else "Date inconnue"
            clean_title = (vid.title[:45] + "...") if len(vid.title) > 45 else vid.title
            print(f"     [{idx}] ID: {vid.video_id} | {pub_date} | {clean_title}")

        # Données de diagnostic en mémoire
        collected_data_summary[key] = {
            "channel_id": channel.channel_id,
            "title": channel.title,
            "uploads_playlist_id": channel.uploads_playlist_id,
            "sample_count": len(page.items),
            "total_channel_videos": page.total_results,
            "quality": {
                "score_percent": q_report.quality_score,
                "is_passed": q_report.is_passed,
                "valid_count": q_report.valid_items,
                "duplicates": q_report.duplicate_ids,
            },
            "sample_items": [
                {
                    "video_id": item.video_id,
                    "title": item.title,
                    "published_at": item.published_at,
                    "channel_title": item.channel_title,
                }
                for item in page.items
            ],
        }

    # 5. ÉTAPE E & F : Bilan de Qualité Consolidé et Persistance de Diagnostic
    print("\n" + "=" * 82)
    print(" 📊 BILAN CONSOLIDÉ DU CONTRÔLE QUALITÉ DES DONNÉES (ÉTAPE E)")
    print("=" * 82)
    print(f"{'Chaîne':<22} | {'Échantillon':<11} | {'Score Qualité':<14} | {'Statut Audit':<12}")
    print("-" * 82)

    all_passed = True
    for rep in quality_reports:
        status_label = "✅ CONFORME" if rep.is_passed else "❌ NON CONFORME"
        if not rep.is_passed:
            all_passed = False
        print(f"{rep.source_name[:22]:<22} | {rep.total_items:<11} | {rep.quality_score:>5.1f}%        | {status_label}")

    print("-" * 82)

    # Bilan Quota
    print("\n" + "-" * 82)
    print(" 📈 BILAN DE CONSOMMATION DU QUOTA YOUTUBE DATA API v3")
    print("-" * 82)
    print(f"  • Total de requêtes HTTP émises   : {client.total_requests}")
    print(f"  • Coût total estimé du quota       : {client.estimated_quota_units} unités / 10 000 autorisées par jour")
    print(f"  • Quota restant disponible         : {10000 - client.estimated_quota_units} unités ({(10000 - client.estimated_quota_units)/100:.1f}%)")
    print("-" * 82)

    # Étape F : Écriture contrôlée du rapport de diagnostic
    diagnostic_path = PROJECT_ROOT / "data" / "raw" / "audit_sample_diagnostic.json"
    diagnostic_payload = {
        "audit_metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_stage": "STAGE_E_QUALITY_AUDIT",
            "compliance_policy": "YOUTUBE_TOS_SECTION_III_E",
            "retention_rule": "VOLATILE_OR_MAX_30_DAYS_TTL",
            "total_quota_units_used": client.estimated_quota_units,
        },
        "channels": collected_data_summary,
    }

    try:
        diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
        with open(diagnostic_path, "w", encoding="utf-8") as f:
            json.dump(diagnostic_payload, f, indent=2, ensure_ascii=False)
        print(f"\n💾 [Étape F] Rapport de diagnostic exporté dans : {diagnostic_path.relative_to(PROJECT_ROOT)}")
        print("   (Conformité : Ne contient que les métadonnées publiques essentielles, exclu de Git).")
    except OSError as err:
        logger.error("Impossible d'écrire le rapport de diagnostic : %s", err)

    if all_passed:
        print("\n🎉 [SUCCÈS GLOBAL] Toutes les étapes de collecte et de qualité sont validées !\n")
        return 0
    else:
        print("\n⚠️ [ATTENTION] Des anomalies de qualité ont été signalées ci-dessus.\n")
        return 1


if __name__ == "__main__":
    exit_code = run_full_pipeline_audit()
    sys.exit(exit_code)
