"""Service d'inférence combinée pour la plateforme audiovisuelle sénégalaise (Sprint 5).

Ce module expose la classe `AudiovisualPredictor` qui orchestre le modèle hybride :
1. Segmentation comportementale non-supervisée (Cluster d'audience K-Means).
2. Régression continue du volume d'audience (Vues estimées et intervalle de confiance).
3. Classification binaire de hit viral (Probabilité d'atteindre ≥ 1 000 000 vues).
4. Recommandations stratégiques actionnables pour la programmation éditoriale.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optimisation multithread Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import joblib
import numpy as np
import pandas as pd

from src.ml.features import (
    CATEGORICAL_FEATURES,
    CLUSTER_ARCHETYPES,
    CLUSTERING_FEATURES,
    DEFAULT_MODELS_DIR,
    NUMERICAL_FEATURES,
    TOP_FRANCHISES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.predict")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AudiovisualPredictor:
    """Orchestrateur d'inférence pour la prédiction de performance audiovisuelle."""

    def __init__(self, models_dir: Path | str = DEFAULT_MODELS_DIR):
        self.models_dir = Path(models_dir)
        self._load_models()

    def _load_models(self) -> None:
        """Charge en mémoire les artefacts de modèles et les transformateurs."""
        logger.info("Chargement des modèles depuis %s...", self.models_dir)
        reg_path = self.models_dir / "regressor_champion.joblib"
        clf_path = self.models_dir / "classifier_champion.joblib"
        prep_path = self.models_dir / "preprocessor.joblib"
        km_path = self.models_dir / "kmeans_model.joblib"
        scaler_path = self.models_dir / "cluster_scaler.joblib"

        if not all(p.exists() for p in [reg_path, clf_path, prep_path, km_path, scaler_path]):
            raise FileNotFoundError(
                f"Modèles manquants dans {self.models_dir}. Veuillez exécuter 'python -m src.ml.train' au préalable."
            )

        self.regressor = joblib.load(reg_path)
        self.classifier = joblib.load(clf_path)
        self.preprocessor = joblib.load(prep_path)
        self.kmeans = joblib.load(km_path)
        self.cluster_scaler = joblib.load(scaler_path)
        logger.info("Modèles et préprocesseurs chargés avec succès.")

    def _engineer_single_record(self, raw_input: Dict[str, Any]) -> pd.DataFrame:
        """Transforme un dictionnaire d'entrée brute en DataFrame prêt pour le pipeline."""
        channel_title = str(raw_input.get("channel_title", "EvenProd"))
        title = str(raw_input.get("title", "Nouvel Épisode"))
        content_type = str(raw_input.get("content_type", "EPISODE")).upper()
        duration_minutes = float(raw_input.get("duration_minutes", 30.0))
        published_hour = int(raw_input.get("published_hour", 20))
        published_day_name = str(raw_input.get("published_day_name", "Friday"))
        is_weekend = int(raw_input.get("is_weekend", 1 if published_day_name in ["Saturday", "Sunday"] else 0))
        published_month = int(raw_input.get("published_month", 10))
        definition = str(raw_input.get("definition", "hd")).lower()
        has_caption = int(raw_input.get("has_caption", 1))

        # Catégorie de durée
        if duration_minutes < 1.0:
            duration_category = "SHORT"
        elif duration_minutes <= 15.0:
            duration_category = "MEDIUM"
        elif duration_minutes <= 45.0:
            duration_category = "LONG"
        else:
            duration_category = "FEATURE"

        # Traitement textuel
        title_lower = title.lower()
        title_char_length = len(title)
        title_word_count = len(title.split())
        has_saison_keyword = 1 if any(k in title_lower for k in ["saison", "season", "s1", "s2", "s3", "s4"]) else 0
        has_episode_keyword = 1 if any(k in title_lower for k in ["ep", "épisode", "episode", "part"]) else 0

        # Encodage temporel cyclique
        hour_sin = np.sin(2 * np.pi * published_hour / 24.0)
        hour_cos = np.cos(2 * np.pi * published_hour / 24.0)
        month_sin = np.sin(2 * np.pi * published_month / 12.0)
        month_cos = np.cos(2 * np.pi * published_month / 12.0)

        # Attribution du Cluster d'audience
        cluster_input = pd.DataFrame(
            [[duration_minutes, published_hour, is_weekend, title_char_length]],
            columns=CLUSTERING_FEATURES,
        )
        scaled_cluster_input = self.cluster_scaler.transform(cluster_input)
        cluster_label = int(self.kmeans.predict(scaled_cluster_input)[0])
        cluster_id = f"cluster_{cluster_label}"

        channel_content_type = f"{channel_title}__{content_type}"
        horizon_days = float(raw_input.get("horizon_days", 365.0))
        log_age_days = float(np.log1p(horizon_days))

        record = {
            "channel_title": channel_title,
            "content_type": content_type,
            "channel_content_type": channel_content_type,
            "duration_category": duration_category,
            "published_day_name": published_day_name,
            "definition": definition,
            "cluster_id": cluster_id,
            "duration_minutes": duration_minutes,
            "published_hour": published_hour,
            "published_month": published_month,
            "is_weekend": is_weekend,
            "has_caption": has_caption,
            "title_char_length": title_char_length,
            "title_word_count": title_word_count,
            "has_saison_keyword": has_saison_keyword,
            "has_episode_keyword": has_episode_keyword,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "month_sin": month_sin,
            "month_cos": month_cos,
            "log_age_days": log_age_days,
            "_raw_title": title,
            "_cluster_label": cluster_label,
        }
        for f in TOP_FRANCHISES:
            record[f"f_{f.replace(' ', '_')}"] = 1 if f in title_lower else 0

        return pd.DataFrame([record])

    def predict(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prédit la performance complète (Vues, Hit Viral, Cluster, Conseils)."""
        df_single = self._engineer_single_record(video_data)
        cluster_id = df_single["cluster_id"].iloc[0]
        cluster_desc = CLUSTER_ARCHETYPES.get(cluster_id, "Segment personnalisé")

        # Transformation par le ColumnTransformer
        X_transformed = self.preprocessor.transform(df_single)

        # 1. Régression (Log-Vues -> Vues réelles)
        pred_log_views = float(self.regressor.predict(X_transformed)[0])
        pred_views = int(round(np.expm1(pred_log_views)))

        # Intervalle de confiance à 80% (marge d'erreur empirique de 0.8 log-points)
        views_lower = int(max(0, round(np.expm1(pred_log_views - 0.8))))
        views_upper = int(round(np.expm1(pred_log_views + 0.8)))

        # 2. Classification (Hit Viral ≥ 1M)
        if hasattr(self.classifier, "predict_proba"):
            hit_prob = float(self.classifier.predict_proba(X_transformed)[0, 1])
        else:
            hit_prob = 1.0 if self.classifier.predict(X_transformed)[0] == 1 else 0.0

        is_hit = hit_prob >= 0.50

        # 3. Diagnostic & Verdict
        if hit_prob >= 0.80:
            verdict = "[HIT CONFIRME] Hit Viral Quasiment Garanti (Confiance Tres Elevee)"
            editorial_tone = "PRIORITAIRE"
        elif hit_prob >= 0.50:
            verdict = "[FORT POTENTIEL] Potentiel Viral Eleve (Cap des 1M de vues atteignable)"
            editorial_tone = "FORT POTENTIEL"
        elif hit_prob >= 0.25:
            verdict = "[AUDIENCE STABLE] Audience Moderee a Bonne (Succes regulier)"
            editorial_tone = "CONTENU STABLE"
        else:
            verdict = "[FORMAT CIBLE] Audience Format Court / Niche (Moins de 250K vues probables)"
            editorial_tone = "FORMAT COMPLEMENTAIRE"

        # 4. Recommandations actionnables
        recommendations = self._generate_strategic_recommendations(
            video_data, pred_views, hit_prob, df_single.iloc[0]
        )

        return {
            "predicted_views": pred_views,
            "confidence_interval_80pct": {
                "lower_bound": views_lower,
                "upper_bound": views_upper,
            },
            "hit_probability_pct": round(hit_prob * 100, 1),
            "is_hit_predicted": is_hit,
            "verdict": verdict,
            "editorial_category": editorial_tone,
            "audience_archetype": {
                "cluster_code": cluster_id,
                "archetype_name": cluster_desc,
            },
            "strategic_recommendations": recommendations,
        }

    def _generate_strategic_recommendations(
        self,
        raw_input: Dict[str, Any],
        pred_views: int,
        hit_prob: float,
        row: pd.Series,
    ) -> List[str]:
        """Émet des conseils éditoriaux pour optimiser le score de diffusion."""
        recs = []
        hour = row["published_hour"]
        day = row["published_day_name"]
        content_type = row["content_type"]

        # Recommandation Horaire
        if hour < 18 or hour > 22:
            recs.append(
                f"[Horaires] La video est prevue a {hour}h00. Les pics d'audience historiques au Senegal se situent entre 19h30 et 21h30 (Prime-Time). Avancer ou retarder la publication vers 20h00 pourrait booster l'audience initiale de 20 a 35%."
            )
        else:
            recs.append("[Timing Optimal] Publication bien calee sur le Prime-Time senegalais (19h-22h).")

        # Recommandation Format
        if content_type == "TEASER" and row["duration_minutes"] > 3.0:
            recs.append(
                "[Format Teaser] Duree superieure a 3 minutes detectee. Les teasers les plus performants durent entre 45 et 90 secondes."
            )
        elif content_type == "EPISODE" and row["duration_minutes"] < 15.0:
            recs.append(
                "[Format Episode] Duree inferieure a 15 minutes. Les episodes de series leaders (EvenProd, Marodi) realisant le million de vues durent en moyenne entre 25 et 45 minutes."
            )

        # Recommandation Calendaire
        if day in ["Monday", "Tuesday", "Wednesday"]:
            recs.append(
                f"[Jour de diffusion ({day})] Les lancements du week-end (Vendredi soir et Dimanche soir) beneficient historiquement d'une viralite organique superieure de +18%."
            )

        if not row["has_saison_keyword"] and content_type == "EPISODE":
            recs.append(
                "[Referencement Titre] Aucun mot-cle 'Saison' detecte. L'ajout explicite de 'Saison X' et 'Episode Y' dans le titre ameliore la decouverte algorithmique YouTube de 15%."
            )

        return recs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulateur de prediction d'audience audiovisuelle senegalaise.")
    parser.add_argument("--channel", default="EvenProd", help="Chaine (EvenProd, Marodi TV Senegal, Pikini Production)")
    parser.add_argument("--title", default="Bete Bete Saison 2 Episode 15", help="Titre de la video")
    parser.add_argument("--type", default="EPISODE", help="Type (EPISODE, TEASER, SHORT, OTHER)")
    parser.add_argument("--duration", type=float, default=32.0, help="Duree en minutes")
    parser.add_argument("--hour", type=int, default=20, help="Heure de publication (0-23)")
    parser.add_argument("--day", default="Friday", help="Jour (Monday, Friday, Sunday...)")

    args = parser.parse_args()

    predictor = AudiovisualPredictor()
    sim_input = {
        "channel_title": args.channel,
        "title": args.title,
        "content_type": args.type,
        "duration_minutes": args.duration,
        "published_hour": args.hour,
        "published_day_name": args.day,
    }

    result = predictor.predict(sim_input)
    print("\n" + "=" * 70)
    print(" SENEGAL AUDIOVISUAL INTELLIGENCE -- SIMULATEUR D'AUDIENCE ML")
    print("=" * 70)
    print(f"Chaine                 : {args.channel}")
    print(f"Format / Titre         : [{args.type}] {args.title}")
    print(f"Duree / Horaire        : {args.duration} min | {args.day} a {args.hour}h00")
    print("-" * 70)
    print(f"Vues Estimees          : {result['predicted_views']:,} vues")
    print(f"Fourchette (80%)       : [{result['confidence_interval_80pct']['lower_bound']:,} - {result['confidence_interval_80pct']['upper_bound']:,}] vues")
    print(f"Probabilite de Hit     : {result['hit_probability_pct']}% (>= 1 000 000 vues)")
    print(f"Verdict                : {result['verdict']}")
    print(f"Archetype Public       : {result['audience_archetype']['archetype_name']}")
    print("-" * 70)
    print("Recommandations Strategiques :")
    for r in result["strategic_recommendations"]:
        print(f"  * {r}")
    print("=" * 70 + "\n")
