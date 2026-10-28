"""Script de collecte industrielle et d'enrichissement du jeu de données audiovisuel.

Ce script extrait l'intégralité du catalogue vidéo public des 3 chaînes cibles :
- Marodi TV Sénégal
- EvenProd
- Pikini Production

Pour chaque vidéo, il collecte :
- Identifiant unique (video_id)
- Titre complet et nom de chaîne
- Date et heure de publication (ISO 8601 UTC)
- Durée (ISO 8601 et secondes)
- Métriques statistiques (vues, likes, commentaires)
- Qualité technique (définition HD/SD, sous-titres)

Exports générés :
- data/raw/senegal_audiovisual_videos.json (archive brute conforme avec métadonnées)
- data/raw/senegal_audiovisual_videos.csv (table exploitable pour Pandas/Excel/BI)
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigError, load_config
from src.youtube_client import (
    ChannelMetadata,
    VideoRecord,
    YouTubeAPIError,
    YouTubeClient,
)


def setup_logger() -> logging.Logger:
    """Configure la journalisation dans logs/data_collection.log et sur la console."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "data_collection.log"

    logger = logging.getLogger("collect_dataset")
    logger.setLevel(logging.INFO)

    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # Fichier
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    return logger


def export_csv(records: List[VideoRecord], destination: Path) -> None:
    """Exporte les enregistrements dans un fichier CSV tabulaire UTF-8."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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

    with open(destination, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_dict())


def export_json(records: List[VideoRecord], metadata: Dict[str, Any], destination: Path) -> None:
    """Exporte les enregistrements dans un document JSON structuré conforme."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_metadata": metadata,
        "total_records": len(records),
        "records": [r.to_dict() for r in records],
    }

    with open(destination, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_existing_video_ids(csv_path: Path) -> set[str]:
    """Charge l'ensemble des identifiants de vidéos déjà collectées pour le mode incrémental."""
    if not csv_path.exists():
        return set()
    ids = set()
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row.get("video_id")
            if vid:
                ids.add(vid)
    return ids


def run_collection(limit_per_channel: Optional[int] = None, incremental: bool = False) -> int:
    """Lance la collecte complète ou incrémentale multi-sources."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logger = setup_logger()

    print("\n" + "=" * 84)
    print(" 🇸🇳 SÉNÉGAL AUDIOVISUAL INTELLIGENCE PLATFORM — COLLECTE DU JEU DE DONNÉES")
    print(f" Mode d'exécution : {'INCRÉMENTAL (Reprise au watermark)' if incremental else 'COMPLET (Backfill)'}")
    print("=" * 84)

    csv_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.csv"
    json_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.json"

    known_ids: set[str] = set()
    if incremental:
        known_ids = load_existing_video_ids(csv_file)
        print(f"  ℹ️ Base de référence existante : {len(known_ids):,} vidéos déjà archivées.")

    # 1. Chargement de la configuration
    try:
        config = load_config()
        logger.info("Configuration chargée. Clé API : %s", config.masked_api_key)
    except ConfigError as err:
        logger.critical("Erreur de configuration : %s", err)
        return 1

    client = YouTubeClient(api_key=config.youtube_api_key, timeout=config.request_timeout)

    # 2. Résolution des sources
    print("\n[1/3] Résolution des chaînes officielles...")
    channels: Dict[str, ChannelMetadata] = {}
    for name, handle in config.channel_handles.items():
        try:
            m = client.get_channel_by_handle(handle)
            channels[name] = m
            print(f"  • {m.title:<22} (Handle: {m.custom_url}) -> {m.video_count:,} vidéos au total")
        except YouTubeAPIError as e:
            logger.error("Impossible de résoudre la chaîne %s : %s", name, e)
            print(f"  ❌ Erreur sur {name} : {e}")
            return 1

    # 3. Collecte et enrichissement
    print("\n[2/3] Démarrage de la collecte paginée...")
    if limit_per_channel:
        print(f"  ℹ️ Limite configurée : maximum {limit_per_channel} vidéos par chaîne.")
    else:
        print("  ℹ️ Mode complet : extraction de toutes les vidéos publiques disponibles.")

    all_records: List[VideoRecord] = []
    channel_stats: Dict[str, Dict[str, Any]] = {}
    start_time = time.time()

    for name, meta in channels.items():
        print(f"\n▶ Collecte en cours pour : {meta.title}...")
        channel_records: List[VideoRecord] = []

        last_print_time = 0.0

        def on_progress(collected: int, total: Optional[int]):
            nonlocal last_print_time
            now = time.time()
            # Affiche la progression au maximum une fois par seconde
            if now - last_print_time >= 0.8:
                tot_str = f"{total:,}" if total is not None else "?"
                pct = f"({collected/total*100:.1f}%)" if total and total > 0 else ""
                print(f"   ↳ {collected:,} / {tot_str} vidéos récupérées {pct} [Quota utilisé: {client.estimated_quota_units}]", end="\r")
                last_print_time = now

        try:
            channel_records = client.collect_channel_videos(
                playlist_id=meta.uploads_playlist_id,
                channel_title=meta.title,
                channel_id=meta.channel_id,
                max_videos=limit_per_channel,
                enrich_statistics=True,
                progress_callback=on_progress,
                known_video_ids=known_ids if incremental else None,
            )
            print(f"\n   [OK] {len(channel_records):,} nouvelles vidéos récupérées pour {meta.title}.")
        except YouTubeAPIError as coll_err:
            logger.error("Erreur durant la collecte de %s : %s", meta.title, coll_err)
            print(f"\n   [ERREUR] Erreur de collecte : {coll_err}")

        all_records.extend(channel_records)

        # Calcul des métriques cumulées pour cette chaîne
        total_views = sum(r.view_count for r in channel_records)
        total_likes = sum((r.like_count or 0) for r in channel_records)
        total_hours = sum(r.duration_seconds for r in channel_records) / 3600.0

        channel_stats[name] = {
            "title": meta.title,
            "channel_id": meta.channel_id,
            "videos_collected": len(channel_records),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_hours": round(total_hours, 1),
        }

        # Checkpoint de sécurité : écriture progressive sur disque
        csv_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.csv"
        json_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.json"
        export_csv(all_records, csv_file)
        print(f"   💾 Checkpoint sauvegardé : {len(all_records):,} vidéos cumulées écrites dans le CSV.")

    elapsed = round(time.time() - start_time, 1)

    # 4. Exports des données
    print("\n[3/3] Sauvegarde et persistance des données...")
    csv_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.csv"
    json_file = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.json"

    meta_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "quota_units_used": client.estimated_quota_units,
        "total_requests": client.total_requests,
        "channels": channel_stats,
        "compliance_notes": {
            "source": "YouTube Data API v3",
            "policy": "Developer Policies Section III.E (Mise en cache temporaire max 30 jours)",
            "pii_protection": "Aucune donnée personnelle (commentaires utilisateurs exclus)",
            "commercial_usage": "Analyse de métadonnées publiques exclusivement",
        },
    }

    export_csv(all_records, csv_file)
    export_json(all_records, meta_payload, json_file)

    print(f"  💾 Fichier CSV tabulaire : {csv_file.relative_to(PROJECT_ROOT)} ({len(all_records):,} lignes)")
    print(f"  💾 Fichier JSON structuré : {json_file.relative_to(PROJECT_ROOT)}")

    # 5. Grand Récapitulatif Analytique
    print("\n" + "=" * 84)
    print(" 📊 BILAN DE LA COLLECTE DE DONNÉES AUDIOVISUELLES")
    print("=" * 84)
    print(f"{'Chaîne':<22} | {'Vidéos':<8} | {'Total Vues':<16} | {'Total Likes':<13} | {'Heures':<7}")
    print("-" * 84)

    grand_total_views = 0
    grand_total_likes = 0
    grand_total_hours = 0.0

    for _, stats in channel_stats.items():
        grand_total_views += stats["total_views"]
        grand_total_likes += stats["total_likes"]
        grand_total_hours += stats["total_hours"]
        print(
            f"{stats['title'][:22]:<22} | "
            f"{stats['videos_collected']:<8,} | "
            f"{stats['total_views']:<16,} | "
            f"{stats['total_likes']:<13,} | "
            f"{stats['total_hours']:<7.1f}"
        )

    print("-" * 84)
    print(
        f"{'TOTAL DU CATALOGUE':<22} | "
        f"{len(all_records):<8,} | "
        f"{grand_total_views:<16,} | "
        f"{grand_total_likes:<13,} | "
        f"{grand_total_hours:<7.1f}h"
    )
    print("=" * 84)

    # Bilan Quota
    print("\n📈 Bilan de consommation du quota :")
    print(f"  • Requêtes HTTP émises   : {client.total_requests}")
    print(f"  • Unités de quota brûlées : {client.estimated_quota_units} / 10 000 autorisées par jour")
    print(f"  • Quota quotidien restant : {10000 - client.estimated_quota_units} unités ({((10000 - client.estimated_quota_units)/10000)*100:.1f}%)")
    print(f"  • Durée de traitement    : {elapsed} secondes")

    print("\n🎉 [SUCCÈS] Base de données audiovisuelle sénégalaise constituée avec succès !\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collecte complète du catalogue vidéo YouTube.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de vidéos à collecter par chaîne (défaut : tout le catalogue)",
    )
    parser.add_argument(
        "--check-existing",
        action="store_true",
        help="Vérifie si les données brutes existent déjà avant de collecter (évite de brûler du quota)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Mode incrémental : stoppe la collecte dès qu'une vidéo déjà archivée est rencontrée",
    )
    args = parser.parse_args()
    if args.check_existing:
        raw_csv = PROJECT_ROOT / "data" / "raw" / "senegal_audiovisual_videos.csv"
        if raw_csv.exists() and raw_csv.stat().st_size > 1000:
            print(f"[OK] Jeu de donnees Bronze deja present : {raw_csv} ({raw_csv.stat().st_size:,} octets). Ingestion validee sans consommation de quota.")
            sys.exit(0)
    sys.exit(run_collection(limit_per_channel=args.limit, incremental=args.incremental))
