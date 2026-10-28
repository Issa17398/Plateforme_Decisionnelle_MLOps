"""Module d'audit de qualité des données pour le pipeline de collecte (Étape D).

Ce module applique des règles strictes de contrôle qualité sur les métadonnées vidéo :
- Validation structurelle des identifiants de vidéo (format officiel YouTube 11 caractères).
- Vérification de la présence et de la conformité des titres et dates de publication ISO 8601.
- Détection des doublons au sein d'un échantillon ou d'une page de collecte.
- Identification des vidéos privées ou supprimées.
- Calcul d'un score de conformité qualité sans stocker inutilement les données brutes.
"""

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Dict, List, Optional, Set

from src.youtube_client import PlaylistItem


# Format officiel des identifiants vidéo YouTube : exactement 11 caractères alphanumériques, '-' ou '_'
YOUTUBE_VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")


@dataclass(frozen=True)
class ItemValidationResult:
    """Résultat de validation unitaire d'un élément vidéo."""
    video_id: str
    is_valid: bool
    is_private_or_deleted: bool
    has_valid_id: bool
    has_valid_title: bool
    has_valid_date: bool
    errors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityReport:
    """Rapport d'audit de qualité consolidé pour un échantillon de données collectées.

    Attributes:
        source_name: Nom de la chaîne auditée.
        total_items: Nombre total d'éléments examinés.
        valid_items: Nombre d'éléments conformes à 100%.
        missing_ids_count: Nombre d'éléments dépourvus d'identifiant vidéo valide.
        missing_titles_count: Nombre d'éléments sans titre valide.
        missing_dates_count: Nombre d'éléments sans date de publication valide.
        duplicate_ids: Liste des identifiants vidéo dupliqués.
        private_or_deleted_count: Nombre d'éléments inaccessibles (privés ou supprimés).
        quality_score: Pourcentage d'éléments valides (0.0 à 100.0).
        anomalies: Liste détaillée de toutes les anomalies détectées.
    """
    source_name: str
    total_items: int
    valid_items: int
    missing_ids_count: int
    missing_titles_count: int
    missing_dates_count: int
    duplicate_ids: List[str]
    private_or_deleted_count: int
    quality_score: float
    anomalies: List[str]

    @property
    def is_passed(self) -> bool:
        """Indique si l'échantillon passe l'audit de qualité (aucun doublon, IDs valides)."""
        return self.missing_ids_count == 0 and len(self.duplicate_ids) == 0 and self.valid_items > 0


def validate_single_item(item: PlaylistItem) -> ItemValidationResult:
    """Contrôle la validité des champs essentiels d'une métadonnée vidéo."""
    errors: List[str] = []

    # 1. Contrôle du video_id
    has_valid_id = bool(item.video_id and YOUTUBE_VIDEO_ID_REGEX.match(item.video_id))
    if not has_valid_id:
        errors.append(f"video_id invalide ou manquant : '{item.video_id}'")

    # 2. Détection de vidéo privée ou supprimée
    is_private_or_deleted = (
        item.title.strip() in ("Private video", "Deleted video")
        or not item.video_id
    )
    if is_private_or_deleted:
        errors.append(f"Vidéo inaccessible/privée sur YouTube (Titre : '{item.title}')")

    # 3. Contrôle du titre
    has_valid_title = bool(item.title and item.title.strip() and not is_private_or_deleted)
    if not has_valid_title and not is_private_or_deleted:
        errors.append("Titre manquant ou vide")

    # 4. Contrôle de la date de publication (ISO 8601)
    has_valid_date = False
    if item.published_at:
        try:
            # YouTube retourne 'YYYY-MM-DDTHH:MM:SSZ'
            cleaned_date = item.published_at.replace("Z", "+00:00")
            datetime.fromisoformat(cleaned_date)
            has_valid_date = True
        except ValueError:
            errors.append(f"Format de date non ISO 8601 : '{item.published_at}'")
    else:
        errors.append("Date de publication absente")

    is_valid = has_valid_id and has_valid_title and has_valid_date and not is_private_or_deleted

    return ItemValidationResult(
        video_id=item.video_id or "<INCONNU>",
        is_valid=is_valid,
        is_private_or_deleted=is_private_or_deleted,
        has_valid_id=has_valid_id,
        has_valid_title=has_valid_title,
        has_valid_date=has_valid_date,
        errors=errors,
    )


def audit_playlist_items(source_name: str, items: List[PlaylistItem]) -> QualityReport:
    """Effectue un audit complet de qualité sur une liste d'éléments de playlist.

    Args:
        source_name: Nom de la chaîne d'origine.
        items: Liste des PlaylistItem récupérés via l'API.

    Returns:
        Un QualityReport complet avec indicateurs de conformité.
    """
    total = len(items)
    if total == 0:
        return QualityReport(
            source_name=source_name,
            total_items=0,
            valid_items=0,
            missing_ids_count=0,
            missing_titles_count=0,
            missing_dates_count=0,
            duplicate_ids=[],
            private_or_deleted_count=0,
            quality_score=0.0,
            anomalies=["Aucun élément reçu dans l'échantillon"],
        )

    seen_ids: Set[str] = set()
    duplicate_ids: Set[str] = set()
    missing_ids = 0
    missing_titles = 0
    missing_dates = 0
    private_deleted = 0
    valid_count = 0
    all_anomalies: List[str] = []

    for item in items:
        # Contrôle des doublons
        if item.video_id:
            if item.video_id in seen_ids:
                duplicate_ids.add(item.video_id)
                all_anomalies.append(f"Doublon détecté pour la vidéo ID : '{item.video_id}'")
            else:
                seen_ids.add(item.video_id)

        # Contrôle unitaire des champs
        res = validate_single_item(item)
        if not res.has_valid_id:
            missing_ids += 1
        if not res.has_valid_title:
            missing_titles += 1
        if not res.has_valid_date:
            missing_dates += 1
        if res.is_private_or_deleted:
            private_deleted += 1

        if res.is_valid:
            valid_count += 1
        else:
            for err in res.errors:
                all_anomalies.append(f"Vidéo [{res.video_id}] : {err}")

    score = round((valid_count / total) * 100.0, 1)

    return QualityReport(
        source_name=source_name,
        total_items=total,
        valid_items=valid_count,
        missing_ids_count=missing_ids,
        missing_titles_count=missing_titles,
        missing_dates_count=missing_dates,
        duplicate_ids=sorted(list(duplicate_ids)),
        private_or_deleted_count=private_deleted,
        quality_score=score,
        anomalies=all_anomalies,
    )
