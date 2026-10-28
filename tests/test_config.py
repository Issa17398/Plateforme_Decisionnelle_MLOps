"""Tests unitaires pour le module de configuration (Étape A).

Ces tests s'exécutent entièrement en local, sans dépendre d'une connexion réseau
ni d'une véritable clé d'API YouTube.
"""

from pathlib import Path
import pytest
from src.config import AppConfig, ConfigError, load_config, mask_secret


def test_load_config_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Vérifie que la configuration se charge correctement avec des valeurs valides."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "YOUTUBE_API_KEY=AIzaSy_FAKE_TEST_KEY_123456789\n"
        "MARODI_HANDLE=@maroditv\n"
        "EVENPROD_HANDLE=@EvenProd\n"
        "PIKINI_HANDLE=@PikiniProduction\n"
        "YOUTUBE_REQUEST_TIMEOUT=45\n",
        encoding="utf-8",
    )
    # Réinitialise les variables d'environnement pouvant interférer
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YouTube key", raising=False)

    config = load_config(env_path=env_file)

    assert isinstance(config, AppConfig)
    assert config.youtube_api_key == "AIzaSy_FAKE_TEST_KEY_123456789"
    assert config.request_timeout == 45
    assert config.channel_handles["marodi"] == "@maroditv"
    assert config.channel_handles["evenprod"] == "@EvenProd"
    assert config.channel_handles["pikini"] == "@PikiniProduction"


def test_load_config_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Vérifie qu'une ConfigError explicite est levée si la clé API est absente."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MARODI_HANDLE=@maroditv\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YouTube key", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=env_file)

    assert "YOUTUBE_API_KEY est manquante ou vide" in str(exc_info.value)


def test_load_config_empty_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Vérifie qu'une clé API vide ou constituée d'espaces est rejetée."""
    env_file = tmp_path / ".env"
    env_file.write_text("YOUTUBE_API_KEY=   \n", encoding="utf-8")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YouTube key", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=env_file)

    assert "YOUTUBE_API_KEY est manquante ou vide" in str(exc_info.value)


def test_load_config_invalid_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Vérifie qu'un timeout non numérique ou négatif déclenche une ConfigError."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "YOUTUBE_API_KEY=AIzaSy_FAKE_TEST_KEY\n"
        "YOUTUBE_REQUEST_TIMEOUT=-10\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YouTube key", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=env_file)

    assert "doit être un entier strictement positif" in str(exc_info.value)


def test_load_config_non_integer_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Vérifie qu'un timeout alphabétique déclenche une ConfigError."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "YOUTUBE_API_KEY=AIzaSy_FAKE_TEST_KEY\n"
        "YOUTUBE_REQUEST_TIMEOUT=trente\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YouTube key", raising=False)

    with pytest.raises(ConfigError):
        load_config(env_path=env_file)


def test_masked_api_key():
    """Vérifie que le masquage protège intégralement la clé sans l'exposer."""
    secret = "AIzaSyBwvpt5gJxdTf07Kt0CXZu67w-Zv2wlQQM"
    config = AppConfig(
        youtube_api_key=secret,
        channel_handles={"test": "@test"},
        request_timeout=30,
    )
    masked = config.masked_api_key

    # La clé complète ne doit JAMAIS apparaître
    assert secret not in masked
    assert masked.startswith("AIzaSy")
    assert masked.endswith("QQM")
    assert "..." in masked


def test_mask_secret_helper():
    """Vérifie le comportement de la fonction utilitaire mask_secret."""
    assert mask_secret(None) == "<NON_DEFINIE>"
    assert mask_secret("") == "<NON_DEFINIE>"
    assert mask_secret("short") == "***"
    assert mask_secret("1234567890") == "123456...890"


def test_load_config_non_existent_env_file():
    """Vérifie qu'un chemin de fichier .env inexistant soulève une ConfigError."""
    fake_path = Path("un/chemin/qui/n/existe/pas/.env")
    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=fake_path)

    assert "Le fichier d'environnement spécifié n'existe pas" in str(exc_info.value)
