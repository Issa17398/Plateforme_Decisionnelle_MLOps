"""Module client pour interagir avec YouTube Data API v3 de façon sécurisée et conforme.

Ce client implémente :
- La gestion stricte des timeouts et des exceptions réseau.
- L'analyse précise des erreurs YouTube (clés invalides, dépassement de quota, 404).
- Le masquage des secrets dans les logs et messages d'erreur.
- L'extraction des métadonnées de chaîne et de la playlist officielle 'uploads'.
- La comptabilité des unités de quota consommées.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions spécialisées de l'API YouTube
# ==============================================================================

class YouTubeAPIError(Exception):
    """Exception générique de base pour les erreurs de l'API YouTube."""
    pass


class YouTubeAuthenticationError(YouTubeAPIError):
    """Exception levée en cas de clé API invalide ou non autorisée (HTTP 400/403)."""
    pass


class YouTubeQuotaExceededError(YouTubeAPIError):
    """Exception levée lorsque le quota journalier de requêtes est dépassé (HTTP 403)."""
    pass


class YouTubeResourceNotFoundError(YouTubeAPIError):
    """Exception levée lorsqu'une chaîne ou ressource demandée n'existe pas."""
    pass


class YouTubeNetworkError(YouTubeAPIError):
    """Exception levée en cas de timeout ou de rupture de connexion réseau."""
    pass


# ==============================================================================
# Modèles de données de transfert (DTO)
# ==============================================================================

@dataclass(frozen=True)
class ChannelMetadata:
    """Structure immuable encapsulant les métadonnées essentielles d'une chaîne.

    Attributes:
        channel_id: Identifiant unique et pérenne de la chaîne (ex: UC...).
        title: Titre officiel de la chaîne.
        custom_url: Handle ou URL personnalisée (ex: @maroditv).
        uploads_playlist_id: Identifiant de la playlist automatique contenant toutes
                             les vidéos mises en ligne (ex: UU...). Clé maîtresse pour
                             parcourir les vidéos à faible coût de quota (1 unité).
        published_at: Date de création de la chaîne au format ISO 8601.
        video_count: Nombre total de vidéos publiées (si disponible).
        subscriber_count: Nombre d'abonnés arrondi fourni par l'API (si disponible).
    """
    channel_id: str
    title: str
    custom_url: Optional[str]
    uploads_playlist_id: str
    published_at: Optional[str]
    video_count: Optional[int]
    subscriber_count: Optional[int]


@dataclass(frozen=True)
class PlaylistItem:
    """Structure immuable pour un élément d'une playlist YouTube (métadonnées vidéo).

    Attributes:
        video_id: Identifiant unique de la vidéo (ex: 'dQw4w9WgXcQ', 11 caractères).
        title: Titre de la vidéo.
        published_at: Date de publication de la vidéo (format ISO 8601).
        channel_title: Nom de la chaîne publiante.
        description_snippet: Extrait court de la description (facultatif).
        position: Position ordonnée dans la playlist (0-indexed).
    """
    video_id: str
    title: str
    published_at: Optional[str]
    channel_title: Optional[str]
    description_snippet: Optional[str] = None
    position: Optional[int] = None


@dataclass(frozen=True)
class PlaylistPage:
    """Résultat paginé d'une consultation de playlist.

    Attributes:
        items: Liste des éléments de vidéos de la page.
        next_page_token: Jeton de pagination pour la page suivante (si existant).
        prev_page_token: Jeton de pagination pour la page précédente (si existant).
        total_results: Nombre total estimé d'éléments dans la playlist.
    """
    items: List[PlaylistItem]
    next_page_token: Optional[str]
    prev_page_token: Optional[str]
    total_results: int


def parse_duration_to_seconds(duration_str: Optional[str]) -> int:
    """Convertit une durée ISO 8601 YouTube (ex: 'PT1H14M35S', 'PT12M05S', 'PT45S') en secondes.

    Args:
        duration_str: Chaîne de durée au format ISO 8601.

    Returns:
        Durée totale en secondes (entier positif ou 0).
    """
    if not duration_str or not duration_str.startswith("P"):
        return 0
    pattern = re.compile(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )
    match = pattern.match(duration_str)
    if not match:
        return 0
    parts = match.groupdict()
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class VideoRecord:
    """Structure de données enrichie et complète pour l'analyse audiovisuelle.

    Attributes:
        video_id: Identifiant unique YouTube (11 caractères).
        channel_title: Nom de la chaîne (ex: 'Marodi TV Sénégal').
        channel_id: Identifiant immuable de la chaîne (UC...).
        title: Titre de la vidéo.
        published_at: Date et heure de publication (format ISO 8601 UTC).
        duration: Durée brute au format ISO 8601 (ex: 'PT15M30S').
        duration_seconds: Durée convertie en secondes pour l'analyse.
        view_count: Nombre total de vues à la date de collecte.
        like_count: Nombre de mentions j'aime (si public).
        comment_count: Nombre de commentaires sous la vidéo (si activés).
        definition: Définition vidéo ('hd' ou 'sd').
        caption: Présence de sous-titres ('true' ou 'false').
        collected_at: Horodatage UTC de la collecte.
    """
    video_id: str
    channel_title: str
    channel_id: str
    title: str
    published_at: str
    duration: str
    duration_seconds: int
    view_count: int
    like_count: Optional[int]
    comment_count: Optional[int]
    definition: str
    caption: bool
    collected_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'enregistrement en dictionnaire sérialisable en JSON."""
        return {
            "video_id": self.video_id,
            "channel_title": self.channel_title,
            "channel_id": self.channel_id,
            "title": self.title,
            "published_at": self.published_at,
            "duration": self.duration,
            "duration_seconds": self.duration_seconds,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "definition": self.definition,
            "caption": self.caption,
            "collected_at": self.collected_at,
        }


# ==============================================================================
# Client YouTube Data API v3
# ==============================================================================

class YouTubeClient:
    """Client HTTP sécurisé pour l'API YouTube Data v3."""

    BASE_URL: str = "https://www.googleapis.com/youtube/v3"

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialise le client YouTube.

        Args:
            api_key: Clé d'API YouTube Data API v3.
            timeout: Délai d'expiration réseau en secondes.
            session: Session requests optionnelle (utile pour l'injection en tests).
        """
        if not api_key or not api_key.strip():
            raise ValueError("Une clé API YouTube non vide est requise.")

        self._api_key: str = api_key.strip()
        self.timeout: int = timeout
        self.session: requests.Session = session or requests.Session()

        # Compteurs de diagnostic et métriques de quota
        self.total_requests: int = 0
        self.estimated_quota_units: int = 0

    def _sanitize_params_for_logging(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retourne une copie des paramètres où la clé API est masquée."""
        sanitized = dict(params)
        if "key" in sanitized:
            key_val = str(sanitized["key"])
            sanitized["key"] = f"{key_val[:6]}...{key_val[-3:]}" if len(key_val) > 9 else "***"
        return sanitized

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        quota_cost: int = 1,
    ) -> Dict[str, Any]:
        """Exécute une requête HTTP GET vers l'API YouTube avec gestion complète des erreurs.

        Args:
            endpoint: Nom de l'endpoint relatif (ex: 'channels', 'playlistItems').
            params: Paramètres de la requête GET.
            quota_cost: Coût estimé en unités de quota pour cet endpoint (défaut: 1).

        Returns:
            Dictionnaire représentant le corps de la réponse JSON.

        Raises:
            YouTubeNetworkError: Si le réseau ou le timeout échoue.
            YouTubeQuotaExceededError: Si le quota quotidien est épuisé.
            YouTubeAuthenticationError: Si la clé est rejetée.
            YouTubeAPIError: Pour toute autre erreur retournée par l'API.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        full_params = dict(params)
        full_params["key"] = self._api_key

        safe_log_params = self._sanitize_params_for_logging(full_params)
        logger.debug("Requête sortante vers %s avec paramètres : %s", url, safe_log_params)

        try:
            response = self.session.get(url, params=full_params, timeout=self.timeout)
            self.total_requests += 1
            self.estimated_quota_units += quota_cost
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
            logger.error("Erreur réseau/timeout vers %s : %s", endpoint, str(net_err))
            raise YouTubeNetworkError(
                f"Échec de connexion réseau ou timeout ({self.timeout}s) vers YouTube API : {net_err}"
            ) from net_err
        except requests.exceptions.RequestException as req_err:
            logger.error("Erreur de requête HTTP vers %s : %s", endpoint, str(req_err))
            raise YouTubeNetworkError(f"Erreur de communication HTTP : {req_err}") from req_err

        # Traitement du JSON retourné
        try:
            data = response.json()
        except ValueError as json_err:
            logger.error("Réponse non-JSON retournée par l'API (Statut %s) : %s", response.status_code, response.text[:200])
            raise YouTubeAPIError(
                f"Le serveur YouTube a retourné une réponse non-JSON (Code HTTP {response.status_code})."
            ) from json_err

        # Si le code de statut HTTP indique une erreur (>= 400)
        if not response.ok:
            self._handle_api_error(response.status_code, data)

        return data

    def _handle_api_error(self, status_code: int, error_data: Dict[str, Any]) -> None:
        """Analyse la structure d'erreur retournée par Google et lève l'exception idoine."""
        error_info = error_data.get("error", {})
        message = error_info.get("message", "Erreur inconnue de l'API YouTube")
        errors_list = error_info.get("errors", [])

        # Extraction de la première 'reason'
        reasons = [e.get("reason", "") for e in errors_list if isinstance(e, dict)]
        first_reason = reasons[0] if reasons else ""

        logger.warning(
            "Réponse d'erreur YouTube reçue : Code=%s, Raison=%s, Message=%s",
            status_code,
            first_reason,
            message,
        )

        if "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons:
            raise YouTubeQuotaExceededError(
                f"Quota journalier YouTube dépassé (Statut {status_code}) : {message}"
            )

        if "keyInvalid" in reasons or "badRequest" in reasons and "API key not valid" in message:
            raise YouTubeAuthenticationError(
                f"Clé API YouTube invalide ou non autorisée (Statut {status_code}) : {message}"
            )

        if status_code in (401, 403):
            raise YouTubeAuthenticationError(
                f"Accès refusé par l'API YouTube (Statut {status_code}, Raison: {first_reason}) : {message}"
            )

        raise YouTubeAPIError(f"Erreur API YouTube (Statut {status_code}) : {message}")

    def get_channel_by_handle(self, handle: str) -> ChannelMetadata:
        """Résout une chaîne officielle YouTube à partir de son handle (ex: '@maroditv').

        Utilise l'endpoint officiel 'channels.list' avec part='snippet,contentDetails,statistics'.
        Coût de quota : 1 unité.

        Args:
            handle: Le handle officiel de la chaîne, avec ou sans préfixe '@'.

        Returns:
            Une instance ChannelMetadata contenant notamment l'uploads_playlist_id.

        Raises:
            YouTubeResourceNotFoundError: Si aucune chaîne ne correspond au handle.
            YouTubeAPIError: En cas d'erreur de requête ou d'API.
        """
        clean_handle = handle.strip()
        # Assure le format avec '@' attendu par le paramètre forHandle
        if not clean_handle.startswith("@"):
            clean_handle = f"@{clean_handle}"

        params = {
            "part": "snippet,contentDetails,statistics",
            "forHandle": clean_handle,
        }

        data = self._make_request("channels", params=params, quota_cost=1)
        items = data.get("items", [])

        if not items:
            raise YouTubeResourceNotFoundError(
                f"Aucune chaîne YouTube trouvée pour le handle officiel : '{clean_handle}'."
            )

        item = items[0]
        channel_id = item.get("id", "")
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})

        # Récupération de la playlist uploads (clé maîtresse pour parcourir les vidéos)
        related_playlists = content_details.get("relatedPlaylists", {})
        uploads_playlist_id = related_playlists.get("uploads")

        if not uploads_playlist_id:
            raise YouTubeAPIError(
                f"La chaîne '{channel_id}' ne contient pas d'identifiant de playlist 'uploads' valide."
            )

        title = snippet.get("title", "Titre Inconnu")
        custom_url = snippet.get("customUrl", clean_handle)
        published_at = snippet.get("publishedAt")

        # Parsing sécurisé des statistiques
        video_count = None
        if "videoCount" in statistics:
            try:
                video_count = int(statistics["videoCount"])
            except (ValueError, TypeError):
                video_count = None

        subscriber_count = None
        if "subscriberCount" in statistics:
            try:
                subscriber_count = int(statistics["subscriberCount"])
            except (ValueError, TypeError):
                subscriber_count = None

        return ChannelMetadata(
            channel_id=channel_id,
            title=title,
            custom_url=custom_url,
            uploads_playlist_id=uploads_playlist_id,
            published_at=published_at,
            video_count=video_count,
            subscriber_count=subscriber_count,
        )

    def get_channel_by_id(self, channel_id: str) -> ChannelMetadata:
        """Résout une chaîne directement à partir de son ID immuable (ex: 'UC...').

        Coût de quota : 1 unité.
        """
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": channel_id.strip(),
        }

        data = self._make_request("channels", params=params, quota_cost=1)
        items = data.get("items", [])

        if not items:
            raise YouTubeResourceNotFoundError(
                f"Aucune chaîne YouTube trouvée pour l'ID : '{channel_id}'."
            )

        item = items[0]
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})

        uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads")
        if not uploads_playlist_id:
            raise YouTubeAPIError(
                f"La chaîne '{channel_id}' ne contient pas de playlist 'uploads' valide."
            )

        video_count = int(statistics["videoCount"]) if "videoCount" in statistics else None
        subscriber_count = int(statistics["subscriberCount"]) if "subscriberCount" in statistics else None

        return ChannelMetadata(
            channel_id=item.get("id", channel_id),
            title=snippet.get("title", "Titre Inconnu"),
            custom_url=snippet.get("customUrl"),
            uploads_playlist_id=uploads_playlist_id,
            published_at=snippet.get("publishedAt"),
            video_count=video_count,
            subscriber_count=subscriber_count,
        )

    def get_playlist_items(
        self,
        playlist_id: str,
        max_results: int = 5,
        page_token: Optional[str] = None,
    ) -> PlaylistPage:
        """Récupère une page d'éléments d'une playlist YouTube (ex: playlist uploads).

        Utilise l'endpoint officiel 'playlistItems.list' avec part='snippet,contentDetails'.
        Coût de quota : 1 unité par page.

        Args:
            playlist_id: Identifiant de la playlist (ex: 'UUqe0sSESmaQbLFdTExctQLA').
            max_results: Nombre maximal d'éléments à retourner (entre 1 et 50).
            page_token: Jeton de pagination optionnel pour parcourir les pages suivantes.

        Returns:
            Une instance PlaylistPage contenant la liste d'éléments et les jetons de pagination.

        Raises:
            YouTubeResourceNotFoundError: Si la playlist n'existe pas.
            YouTubeAPIError: En cas d'erreur de réponse de l'API.
        """
        clean_playlist_id = playlist_id.strip()
        if not clean_playlist_id:
            raise ValueError("L'identifiant de playlist ne peut pas être vide.")

        bounded_max = max(1, min(max_results, 50))
        params: Dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": clean_playlist_id,
            "maxResults": bounded_max,
        }
        if page_token:
            params["pageToken"] = page_token.strip()

        data = self._make_request("playlistItems", params=params, quota_cost=1)
        raw_items = data.get("items", [])
        page_info = data.get("pageInfo", {})
        total_results = page_info.get("totalResults", len(raw_items))
        next_token = data.get("nextPageToken")
        prev_token = data.get("prevPageToken")

        parsed_items: List[PlaylistItem] = []
        for raw_item in raw_items:
            snippet = raw_item.get("snippet", {})
            content_details = raw_item.get("contentDetails", {})

            # L'ID de la vidéo se trouve prioritairement dans contentDetails.videoId
            video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId", "")
            title = snippet.get("title", "")
            published_at = snippet.get("publishedAt")
            channel_title = snippet.get("channelTitle")
            position = snippet.get("position")
            desc = snippet.get("description", "")
            desc_snippet = desc[:120].strip() if desc else None

            # Journalise les éléments non exploitables (vidéos privées ou supprimées)
            if title in ("Private video", "Deleted video") or not video_id:
                logger.warning(
                    "Élément de playlist non accessible (Privé/Supprimé) : id='%s', titre='%s'",
                    video_id,
                    title,
                )

            parsed_items.append(
                PlaylistItem(
                    video_id=video_id,
                    title=title,
                    published_at=published_at,
                    channel_title=channel_title,
                    description_snippet=desc_snippet,
                    position=position,
                )
            )

        return PlaylistPage(
            items=parsed_items,
            next_page_token=next_token,
            prev_page_token=prev_token,
            total_results=total_results,
        )

    def get_videos_details_batch(self, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Enrichit un lot de vidéos (jusqu'à 50 IDs) via l'endpoint officiel 'videos.list'.

        Coût de quota : exactement 1 unité pour le lot complet de 50 vidéos.

        Args:
            video_ids: Liste d'identifiants de vidéos (maximum 50).

        Returns:
            Dictionnaire associant video_id à ses métriques détaillées.
        """
        if not video_ids:
            return {}

        # Limitation stricte à 50 IDs imposée par l'API YouTube
        valid_ids = [vid.strip() for vid in video_ids if vid.strip()][:50]
        if not valid_ids:
            return {}

        params = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(valid_ids),
        }

        data = self._make_request("videos", params=params, quota_cost=1)
        items = data.get("items", [])
        details_map: Dict[str, Dict[str, Any]] = {}

        for item in items:
            vid_id = item.get("id", "")
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            # Vues
            try:
                views = int(statistics.get("viewCount", 0))
            except (ValueError, TypeError):
                views = 0

            # Likes (optionnel si masqué par le créateur)
            likes = None
            if "likeCount" in statistics:
                try:
                    likes = int(statistics["likeCount"])
                except (ValueError, TypeError):
                    likes = None

            # Commentaires (optionnel si désactivés)
            comments = None
            if "commentCount" in statistics:
                try:
                    comments = int(statistics["commentCount"])
                except (ValueError, TypeError):
                    comments = None

            duration_raw = content_details.get("duration", "PT0S")
            duration_sec = parse_duration_to_seconds(duration_raw)
            definition = content_details.get("definition", "hd")
            caption_str = str(content_details.get("caption", "false")).lower()
            caption_bool = caption_str == "true"

            details_map[vid_id] = {
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "duration": duration_raw,
                "duration_seconds": duration_sec,
                "view_count": views,
                "like_count": likes,
                "comment_count": comments,
                "definition": definition,
                "caption": caption_bool,
            }

        return details_map

    def collect_channel_videos(
        self,
        playlist_id: str,
        channel_title: str,
        channel_id: str,
        max_videos: Optional[int] = None,
        enrich_statistics: bool = True,
        progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
        known_video_ids: Optional[set[str]] = None,
    ) -> List[VideoRecord]:
        """Collecte paginée et enrichissement par lots de toutes les vidéos d'une chaîne.

        Args:
            playlist_id: Identifiant de la playlist 'uploads' (UU...).
            channel_title: Nom de la chaîne.
            channel_id: Identifiant de la chaîne (UC...).
            max_videos: Limite maximale optionnelle de vidéos (None pour tout collecter).
            enrich_statistics: Si True, enrichit avec vues, likes, durée via videos.list.
            progress_callback: Fonction de rappel pour afficher l'avancement (collected, total).
            known_video_ids: Ensemble des video_id déjà collectés. Si renseigné, stoppe
                immédiatement la pagination dès qu'une vidéo connue est rencontrée (mode incrémental).

        Returns:
            Liste ordonnée de VideoRecord prêts pour l'analyse.
        """
        all_playlist_items: List[PlaylistItem] = []
        next_page_token: Optional[str] = None
        total_available: Optional[int] = None
        stop_reached = False

        logger.info(
            "Démarrage de la collecte paginée pour '%s' (Playlist: %s, mode incrémental: %s)...",
            channel_title,
            playlist_id,
            bool(known_video_ids),
        )

        # 1. Parcours de la playlist du plus récent au plus ancien
        while not stop_reached:
            # Calcule combien d'éléments demander pour la page courante (max 50)
            if max_videos is not None:
                remaining = max_videos - len(all_playlist_items)
                if remaining <= 0:
                    break
                page_size = min(50, remaining)
            else:
                page_size = 50

            page = self.get_playlist_items(
                playlist_id=playlist_id,
                max_results=page_size,
                page_token=next_page_token,
            )

            if total_available is None:
                total_available = page.total_results

            # Filtre les éléments sans ID valide ou privés/supprimés
            valid_new_items = []
            for it in page.items:
                if not it.video_id or it.title in ("Private video", "Deleted video"):
                    continue
                if known_video_ids and it.video_id in known_video_ids:
                    logger.info("Frontière incrémentale atteinte sur la vidéo %s. Arrêt du scraping pour %s.", it.video_id, channel_title)
                    stop_reached = True
                    break
                valid_new_items.append(it)

            all_playlist_items.extend(valid_new_items)

            if progress_callback:
                progress_callback(len(all_playlist_items), total_available)

            if stop_reached:
                break

            next_page_token = page.next_page_token
            if not next_page_token:
                # Fin de la playlist atteinte
                break

            # Petite pause courtoise (50ms) pour ménager le rate limiter réseau
            time.sleep(0.05)

        logger.info(
            "%d nouveaux éléments de playlist récupérés pour '%s'.",
            len(all_playlist_items),
            channel_title,
        )

        # 2. Enrichissement des statistiques par lots de 50 (videos.list)
        records: List[VideoRecord] = []
        current_time_iso = datetime.now(timezone.utc).isoformat()

        if enrich_statistics and all_playlist_items:
            # Traitement par paquets de 50
            for i in range(0, len(all_playlist_items), 50):
                batch_items = all_playlist_items[i : i + 50]
                batch_ids = [it.video_id for it in batch_items]

                details_map = self.get_videos_details_batch(batch_ids)

                for item in batch_items:
                    det = details_map.get(item.video_id, {})
                    rec = VideoRecord(
                        video_id=item.video_id,
                        channel_title=det.get("channel_title") or item.channel_title or channel_title,
                        channel_id=channel_id,
                        title=det.get("title") or item.title,
                        published_at=det.get("published_at") or item.published_at or "",
                        duration=det.get("duration", "PT0S"),
                        duration_seconds=det.get("duration_seconds", 0),
                        view_count=det.get("view_count", 0),
                        like_count=det.get("like_count"),
                        comment_count=det.get("comment_count"),
                        definition=det.get("definition", "hd"),
                        caption=det.get("caption", False),
                        collected_at=current_time_iso,
                    )
                    records.append(rec)

                time.sleep(0.05)
        else:
            # Mode sans enrichissement de statistiques
            for item in all_playlist_items:
                records.append(
                    VideoRecord(
                        video_id=item.video_id,
                        channel_title=item.channel_title or channel_title,
                        channel_id=channel_id,
                        title=item.title,
                        published_at=item.published_at or "",
                        duration="PT0S",
                        duration_seconds=0,
                        view_count=0,
                        like_count=None,
                        comment_count=None,
                        definition="hd",
                        caption=False,
                        collected_at=current_time_iso,
                    )
                )

        return records
