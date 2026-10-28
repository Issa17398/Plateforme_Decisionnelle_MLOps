"""Tests unitaires pour le module de contrôle de qualité (Étape D).

Vérifie la détection des champs manquants, des doublons, des vidéos privées/supprimées
et le calcul du score de qualité.
"""

import pytest
from src.audit import (
    QualityReport,
    audit_playlist_items,
    validate_single_item,
)
from src.youtube_client import PlaylistItem


def test_validate_single_item_valid():
    """Vérifie la validation réussie d'un élément conforme."""
    item = PlaylistItem(
        video_id="dQw4w9WgXcQ",
        title="Baye Fall - Saison 1 Épisode 10",
        published_at="2026-03-15T19:00:00Z",
        channel_title="Marodi TV Sénégal",
        position=0,
    )
    res = validate_single_item(item)
    assert res.is_valid is True
    assert res.has_valid_id is True
    assert res.has_valid_title is True
    assert res.has_valid_date is True
    assert res.is_private_or_deleted is False
    assert len(res.errors) == 0


def test_validate_single_item_invalid_video_id():
    """Vérifie qu'un video_id de longueur incorrecte ou avec caractères illégaux est rejeté."""
    # Trop court (7 caractères au lieu de 11)
    item = PlaylistItem(
        video_id="short_1",
        title="Titre Valide",
        published_at="2026-01-01T00:00:00Z",
        channel_title="Test",
    )
    res = validate_single_item(item)
    assert res.is_valid is False
    assert res.has_valid_id is False
    assert any("video_id invalide" in e for e in res.errors)


def test_validate_single_item_empty_title():
    """Vérifie qu'un titre vide est signalé comme anomalie."""
    item = PlaylistItem(
        video_id="12345678901",
        title="   ",
        published_at="2026-01-01T00:00:00Z",
        channel_title="Test",
    )
    res = validate_single_item(item)
    assert res.is_valid is False
    assert res.has_valid_title is False


def test_validate_single_item_private_video():
    """Vérifie la détection d'une vidéo privée sur YouTube."""
    item = PlaylistItem(
        video_id="12345678901",
        title="Private video",
        published_at="2026-01-01T00:00:00Z",
        channel_title="Test",
    )
    res = validate_single_item(item)
    assert res.is_valid is False
    assert res.is_private_or_deleted is True


def test_validate_single_item_invalid_date():
    """Vérifie qu'un format de date non ISO 8601 est rejeté."""
    item = PlaylistItem(
        video_id="12345678901",
        title="Titre Valide",
        published_at="15/03/2026 19:00",  # Pas au format ISO 8601
        channel_title="Test",
    )
    res = validate_single_item(item)
    assert res.is_valid is False
    assert res.has_valid_date is False


def test_audit_playlist_items_clean_batch():
    """Vérifie qu'un lot sans anomalie obtient un score de 100%."""
    items = [
        PlaylistItem(
            video_id=f"vid_test_{i:02d}",  # Longueur exacte 11 caractères
            title=f"Episode {i}",
            published_at="2026-05-01T12:00:00Z",
            channel_title="EvenProd",
            position=i,
        )
        for i in range(5)
    ]
    report = audit_playlist_items("EvenProd", items)

    assert isinstance(report, QualityReport)
    assert report.total_items == 5
    assert report.valid_items == 5
    assert report.missing_ids_count == 0
    assert report.quality_score == 100.0
    assert len(report.duplicate_ids) == 0
    assert report.is_passed is True


def test_audit_playlist_items_detects_duplicates():
    """Vérifie la détection des doublons d'ID vidéo dans un lot."""
    items = [
        PlaylistItem(
            video_id="DUP_TEST_01",
            title="Video 1",
            published_at="2026-01-01T00:00:00Z",
            channel_title="Pikini",
        ),
        PlaylistItem(
            video_id="DUP_TEST_01",  # Doublon
            title="Video 1 (bis)",
            published_at="2026-01-01T00:00:00Z",
            channel_title="Pikini",
        ),
        PlaylistItem(
            video_id="UNIQ_TEST02",
            title="Video 2",
            published_at="2026-01-02T00:00:00Z",
            channel_title="Pikini",
        ),
    ]
    report = audit_playlist_items("Pikini", items)

    assert "DUP_TEST_01" in report.duplicate_ids
    assert report.is_passed is False
    assert any("Doublon détecté" in anom for anom in report.anomalies)


def test_audit_playlist_items_empty():
    """Vérifie le traitement d'une liste vide."""
    report = audit_playlist_items("Vide", [])
    assert report.total_items == 0
    assert report.valid_items == 0
    assert report.quality_score == 0.0
    assert report.is_passed is False
