"""Tests unitaires pour le client YouTube API v3 (Étape B).

Ces tests utilisent des mocks et des objets simulés pour vérifier le comportement
du client dans toutes les situations (succès, 404, quotas, erreurs réseau, JSON invalide)
SANS JAMAIS envoyer de requête réelle sur Internet ni consommer de clé API.
"""

from unittest.mock import MagicMock
import pytest
import requests

from src.youtube_client import (
    ChannelMetadata,
    VideoRecord,
    YouTubeAPIError,
    YouTubeAuthenticationError,
    YouTubeClient,
    YouTubeNetworkError,
    YouTubeQuotaExceededError,
    YouTubeResourceNotFoundError,
    parse_duration_to_seconds,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Fixture retournant un mock de requests.Session."""
    return MagicMock(spec=requests.Session)


@pytest.fixture
def client(mock_session: MagicMock) -> YouTubeClient:
    """Fixture fournissant un client configuré avec une fausse clé et la session mockée."""
    return YouTubeClient(
        api_key="AIzaSy_MOCK_TEST_KEY_987654321",
        timeout=15,
        session=mock_session,
    )


def test_client_init_empty_key():
    """Vérifie qu'initialiser le client avec une clé vide lève ValueError."""
    with pytest.raises(ValueError, match="clé API YouTube non vide est requise"):
        YouTubeClient(api_key="")


def test_get_channel_by_handle_success(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie le parsing réussi d'une réponse valide pour une chaîne YouTube."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": "UC_TEST_CHANNEL_ID_MARODI",
                "snippet": {
                    "title": "Marodi TV Sénégal",
                    "customUrl": "@maroditv",
                    "publishedAt": "2015-01-01T00:00:00Z",
                },
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UU_TEST_PLAYLIST_ID_MARODI",
                    }
                },
                "statistics": {
                    "videoCount": "4500",
                    "subscriberCount": "6200000",
                },
            }
        ]
    }
    mock_session.get.return_value = mock_response

    channel = client.get_channel_by_handle("@maroditv")

    assert isinstance(channel, ChannelMetadata)
    assert channel.channel_id == "UC_TEST_CHANNEL_ID_MARODI"
    assert channel.title == "Marodi TV Sénégal"
    assert channel.uploads_playlist_id == "UU_TEST_PLAYLIST_ID_MARODI"
    assert channel.video_count == 4500
    assert channel.subscriber_count == 6200000
    assert client.total_requests == 1
    assert client.estimated_quota_units == 1


def test_get_channel_by_handle_not_found(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie que la réponse vide (items: []) déclenche YouTubeResourceNotFoundError."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}
    mock_session.get.return_value = mock_response

    with pytest.raises(YouTubeResourceNotFoundError) as exc_info:
        client.get_channel_by_handle("@chaine_inexistante")

    assert "Aucune chaîne YouTube trouvée" in str(exc_info.value)


def test_api_quota_exceeded(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie la détection et la levée spécifique de YouTubeQuotaExceededError."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = False
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {
            "code": 403,
            "message": "The request cannot be completed because you have exceeded your quota.",
            "errors": [
                {
                    "message": "The request cannot be completed because you have exceeded your quota.",
                    "domain": "youtube.quota",
                    "reason": "quotaExceeded",
                }
            ],
        }
    }
    mock_session.get.return_value = mock_response

    with pytest.raises(YouTubeQuotaExceededError) as exc_info:
        client.get_channel_by_handle("@maroditv")

    assert "Quota journalier YouTube dépassé" in str(exc_info.value)


def test_api_invalid_key(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie la détection et la levée spécifique de YouTubeAuthenticationError en cas de clé invalide."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = False
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "errors": [
                {
                    "message": "API key not valid. Please pass a valid API key.",
                    "domain": "global",
                    "reason": "keyInvalid",
                }
            ],
        }
    }
    mock_session.get.return_value = mock_response

    with pytest.raises(YouTubeAuthenticationError) as exc_info:
        client.get_channel_by_handle("@maroditv")

    assert "Clé API YouTube invalide" in str(exc_info.value)


def test_network_timeout(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie qu'un timeout réseau requests est encapsulé dans YouTubeNetworkError."""
    mock_session.get.side_effect = requests.exceptions.Timeout("Connection timed out after 15s")

    with pytest.raises(YouTubeNetworkError) as exc_info:
        client.get_channel_by_handle("@maroditv")

    assert "timeout" in str(exc_info.value).lower()


def test_invalid_json_response(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie qu'une réponse HTML/texte invalide lève YouTubeAPIError."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.text = "<html>502 Bad Gateway</html>"
    mock_response.json.side_effect = ValueError("No JSON object could be decoded")
    mock_session.get.return_value = mock_response

    with pytest.raises(YouTubeAPIError, match="réponse non-JSON"):
        client.get_channel_by_handle("@maroditv")


def test_missing_uploads_playlist(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie qu'une chaîne sans playlist uploads valide soulève une erreur explicite."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": "UC_TEST_ID",
                "snippet": {"title": "Test Channel"},
                "contentDetails": {"relatedPlaylists": {}},
            }
        ]
    }
    mock_session.get.return_value = mock_response

    with pytest.raises(YouTubeAPIError, match="playlist 'uploads' valide"):
        client.get_channel_by_handle("@maroditv")


def test_sanitize_params_for_logging(client: YouTubeClient):
    """Vérifie que la clé est bien masquée lors du formatage pour les logs."""
    raw_params = {"part": "snippet", "key": "AIzaSy_VERY_SECRET_KEY"}
    sanitized = client._sanitize_params_for_logging(raw_params)

    assert "AIzaSy_VERY_SECRET_KEY" not in sanitized["key"]
    assert sanitized["key"].startswith("AIzaSy")
    assert "..." in sanitized["key"]


def test_get_playlist_items_success(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie la récupération et le parsing des éléments de playlist."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "nextPageToken": "NEXT_PAGE_TOKEN_ABC",
        "pageInfo": {"totalResults": 150, "resultsPerPage": 2},
        "items": [
            {
                "snippet": {
                    "title": "Baye Fall Ep 1",
                    "publishedAt": "2026-04-01T18:00:00Z",
                    "channelTitle": "Marodi TV Sénégal",
                    "position": 0,
                    "description": "Episode 1 officiel",
                },
                "contentDetails": {
                    "videoId": "dQw4w9WgXcQ",
                },
            },
            {
                "snippet": {
                    "title": "Baye Fall Ep 2",
                    "publishedAt": "2026-04-02T18:00:00Z",
                    "channelTitle": "Marodi TV Sénégal",
                    "position": 1,
                    "description": "Episode 2 officiel",
                },
                "contentDetails": {
                    "videoId": "L_jWHffIx5E",
                },
            },
        ],
    }
    mock_session.get.return_value = mock_response

    page = client.get_playlist_items("UUqe0sSESmaQbLFdTExctQLA", max_results=2)

    assert len(page.items) == 2
    assert page.items[0].video_id == "dQw4w9WgXcQ"
    assert page.items[0].title == "Baye Fall Ep 1"
    assert page.items[1].video_id == "L_jWHffIx5E"
    assert page.next_page_token == "NEXT_PAGE_TOKEN_ABC"
    assert page.total_results == 150


def test_get_playlist_items_empty_playlist(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie le comportement avec une playlist sans éléments."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [],
        "pageInfo": {"totalResults": 0},
    }
    mock_session.get.return_value = mock_response

    page = client.get_playlist_items("UU_EMPTY_PLAYLIST")

    assert len(page.items) == 0
    assert page.total_results == 0
    assert page.next_page_token is None


def test_get_playlist_items_invalid_empty_id(client: YouTubeClient):
    """Vérifie qu'un identifiant de playlist vide lève ValueError."""
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        client.get_playlist_items("")


def test_parse_duration_to_seconds():
    """Vérifie la conversion correcte des durées ISO 8601 en secondes."""
    assert parse_duration_to_seconds(None) == 0
    assert parse_duration_to_seconds("") == 0
    assert parse_duration_to_seconds("PT0S") == 0
    assert parse_duration_to_seconds("PT45S") == 45
    assert parse_duration_to_seconds("PT12M05S") == 12 * 60 + 5  # 725
    assert parse_duration_to_seconds("PT1H15M30S") == 3600 + 15 * 60 + 30  # 4530
    assert parse_duration_to_seconds("P1DT2H") == 86400 + 7200  # 93600


def test_get_videos_details_batch_success(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie l'enrichissement par lot des métriques via videos.list."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": "vid_batch_01",
                "snippet": {
                    "title": "Titre Enrichi",
                    "publishedAt": "2026-06-01T10:00:00Z",
                    "channelTitle": "EvenProd",
                },
                "contentDetails": {
                    "duration": "PT25M10S",
                    "definition": "hd",
                    "caption": "true",
                },
                "statistics": {
                    "viewCount": "1250000",
                    "likeCount": "45000",
                    "commentCount": "3200",
                },
            }
        ]
    }
    mock_session.get.return_value = mock_response

    details = client.get_videos_details_batch(["vid_batch_01"])

    assert "vid_batch_01" in details
    record = details["vid_batch_01"]
    assert record["view_count"] == 1250000
    assert record["like_count"] == 45000
    assert record["comment_count"] == 3200
    assert record["duration_seconds"] == 25 * 60 + 10  # 1510
    assert record["definition"] == "hd"
    assert record["caption"] is True


def test_collect_channel_videos_flow(client: YouTubeClient, mock_session: MagicMock):
    """Vérifie le flux de collecte paginé et l'assemblage de VideoRecord."""
    # 1. Mock pour playlistItems.list
    playlist_resp = MagicMock(spec=requests.Response)
    playlist_resp.ok = True
    playlist_resp.status_code = 200
    playlist_resp.json.return_value = {
        "items": [
            {
                "snippet": {
                    "title": "Video 1",
                    "publishedAt": "2026-05-01T00:00:00Z",
                    "channelTitle": "Marodi TV",
                    "position": 0,
                },
                "contentDetails": {"videoId": "VID_COLLECT1"},
            }
        ],
        "nextPageToken": None,
        "pageInfo": {"totalResults": 1},
    }

    # 2. Mock pour videos.list
    videos_resp = MagicMock(spec=requests.Response)
    videos_resp.ok = True
    videos_resp.status_code = 200
    videos_resp.json.return_value = {
        "items": [
            {
                "id": "VID_COLLECT1",
                "snippet": {
                    "title": "Video 1 Enrichie",
                    "publishedAt": "2026-05-01T00:00:00Z",
                    "channelTitle": "Marodi TV",
                },
                "contentDetails": {
                    "duration": "PT10M00S",
                    "definition": "hd",
                    "caption": "false",
                },
                "statistics": {
                    "viewCount": "50000",
                    "likeCount": "2000",
                    "commentCount": "150",
                },
            }
        ]
    }

    mock_session.get.side_effect = [playlist_resp, videos_resp]

    records = client.collect_channel_videos(
        playlist_id="UU_TEST_PLAYLIST",
        channel_title="Marodi TV",
        channel_id="UC_MARODI_ID",
        max_videos=1,
        enrich_statistics=True,
    )

    assert len(records) == 1
    assert isinstance(records[0], VideoRecord)
    assert records[0].video_id == "VID_COLLECT1"
    assert records[0].view_count == 50000
    assert records[0].duration_seconds == 600
