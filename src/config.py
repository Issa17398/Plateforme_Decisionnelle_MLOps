"""Module de gestion et de validation de la configuration de l'application.

Ce module charge les variables d'environnement depuis le fichier .env,
valide leur présence et leur conformité technique, et garantit que les secrets
(notamment la clé d'API YouTube) ne sont jamais exposés en clair dans les logs.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv


class ConfigError(ValueError):
    """Exception levée lorsqu'une variable de configuration est manquante ou invalide."""
    pass


@dataclass(frozen=True)
class AppConfig:
    """Structure de configuration immuable pour l'application.

    Attributes:
        youtube_api_key: Clé d'API YouTube Data API v3 (confidentielle).
        channel_handles: Dictionnaire associant le nom de la chaîne à son handle officiel.
        request_timeout: Durée maximale en secondes accordée aux requêtes HTTP.
    """
    youtube_api_key: str
    channel_handles: Dict[str, str]
    request_timeout: int

    @property
    def masked_api_key(self) -> str:
        """Retourne une version masquée et sécurisée de la clé d'API pour les logs et diagnostics.

        Exemple : 'AIzaSyBw...QQM' (les caractères intermédiaires sont masqués).
        """
        if not self.youtube_api_key:
            return "<NON_DEFINIE>"
        key = self.youtube_api_key.strip()
        if len(key) <= 8:
            return "***"
        return f"{key[:6]}...{key[-3:]}"


def mask_secret(secret: Optional[str]) -> str:
    """Masque une chaîne sensible pour affichage sécurisé."""
    if not secret:
        return "<NON_DEFINIE>"
    s = secret.strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:6]}...{s[-3:]}"


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    """Charge et valide la configuration depuis un fichier .env ou l'environnement système.

    Args:
        env_path: Chemin optionnel vers un fichier .env spécifique.
                  Par défaut, recherche le fichier .env à la racine du projet.

    Returns:
        Une instance validée de AppConfig.

    Raises:
        ConfigError: Si la clé API est absente, si un handle est vide,
                     ou si le timeout n'est pas un entier strictement positif.
    """
    if env_path is not None:
        if not env_path.exists():
            raise ConfigError(f"Le fichier d'environnement spécifié n'existe pas : {env_path}")
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        # Recherche standard à la racine du projet
        project_root = Path(__file__).resolve().parent.parent
        default_env = project_root / ".env"
        if default_env.exists():
            load_dotenv(dotenv_path=default_env, override=False)
        else:
            # Charge tout .env trouvé dans le CWD
            load_dotenv()

    # 1. Vérification de la clé API
    # Supporte en priorité YOUTUBE_API_KEY et en secours une syntaxe alternative comme "YouTube key"
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        api_key = os.getenv("YouTube key") or os.getenv("YOUTUBE_KEY")

    if not api_key or not api_key.strip():
        raise ConfigError(
            "La variable YOUTUBE_API_KEY est manquante ou vide dans l'environnement. "
            "Veuillez définir YOUTUBE_API_KEY dans votre fichier .env."
        )

    api_key = api_key.strip().strip("'\"")

    # 2. Vérification des handles des chaînes cibles
    marodi = os.getenv("MARODI_HANDLE", "@maroditvprod").strip().strip("'\"")
    evenprod = os.getenv("EVENPROD_HANDLE", "@EvenProd").strip().strip("'\"")
    pikini = os.getenv("PIKINI_HANDLE", "@PikiniProduction").strip().strip("'\"")

    channel_handles: Dict[str, str] = {
        "marodi": marodi,
        "evenprod": evenprod,
        "pikini": pikini,
    }

    for name, handle in channel_handles.items():
        if not handle:
            raise ConfigError(f"Le handle pour la chaîne '{name}' ne peut pas être vide.")

    # 3. Validation du timeout
    raw_timeout = os.getenv("YOUTUBE_REQUEST_TIMEOUT", "30").strip().strip("'\"")
    try:
        timeout = int(raw_timeout)
        if timeout <= 0:
            raise ValueError()
    except ValueError:
        raise ConfigError(
            f"YOUTUBE_REQUEST_TIMEOUT doit être un entier strictement positif (reçu : '{raw_timeout}')."
        )

    return AppConfig(
        youtube_api_key=api_key,
        channel_handles=channel_handles,
        request_timeout=timeout,
    )
