"""Moteur d'Analyse des Sentiments adapté au contexte audiovisuel sénégalais (NLP Hybride).

Prend en charge :
- Le français standard & expressions familières audiovisuelles
- Le wolof sénégalais (lexique des éloges et des critiques)
- Le métissage linguistique (franco-wolof) typique des commentaires YouTube
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple


def normalize_text(text: str) -> str:
    """Normalise une chaîne de caractères pour faciliter la correspondance lexicale."""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return text


# Lexique Positif (Français, Wolof & Franco-Wolof)
LEXICON_POSITIVE = {
    # Wolof & Franco-Wolof
    "machallah": 2.5, "macha allah": 2.5, "machaallah": 2.5, "mashallah": 2.5,
    "nekh": 2.0, "neex": 2.0, "nekhna": 2.2, "neexna": 2.2, "safna": 2.0,
    "rafet": 2.0, "rafetna": 2.2, "rafet na": 2.2, "meun": 1.8, "meunna": 2.0,
    "jerejef": 1.5, "dieuredieuf": 1.8, "dieureudieuf": 1.8, "merci": 1.2,
    "doundeul": 1.7, "sa kaw sa kanam": 2.5, "bilahi": 1.2, "wallahi": 1.2,
    "yalnako yallah defal diam": 2.0, "amin": 1.0, "teranga": 1.5,
    "bayil": -0.5, "yow la": 1.5, "waaw": 1.2, "waaw goor": 2.0,
    "amna solo": 2.2, "am na solo": 2.2, "nitt": 0.5, "baye": 1.0,
    
    # Français
    "bravo": 2.0, "felicitations": 2.2, "magnifique": 2.4, "excellent": 2.3,
    "incroyable": 2.0, "masterclass": 2.5, "pepite": 2.2, "chef d'oeuvre": 2.5,
    "genial": 1.9, "parfait": 2.2, "superbe": 2.0, "top": 1.5, "topissime": 2.2,
    "adore": 2.0, "aime": 1.5, "captivant": 2.0, "emouvant": 1.9, "touchant": 1.8,
    "talent": 2.0, "actrice": 1.0, "acteur": 1.0, "jeu": 1.2, "suspense": 1.5,
    "fier": 1.8, "fierte": 2.0, "reussite": 1.8, "qualite": 1.7, "beaute": 1.8,
    "respect": 1.7, "force": 1.5, "meilleure": 2.0, "meilleur": 2.0, "propre": 1.6,
    "puissant": 1.8, "professionnel": 1.9, "lourd": 1.6, "chapeau": 1.8,
}

# Lexique Négatif (Français, Wolof & Franco-Wolof)
LEXICON_NEGATIVE = {
    # Wolof & Franco-Wolof
    "yakhou": -2.2, "yakhou na": -2.5, "sof": -2.0, "soof": -2.0, "sofna": -2.3,
    "tite": -1.5, "bone": -2.0, "doyna waar": -2.0, "doy na waar": -2.2,
    "ay thiakhane": -2.2, "tiakhane": -2.0, "niaw": -2.0, "niawna": -2.3,
    "gathie": -2.2, "sonal nanu": -2.2, "sonal": -1.8, "rousslou": -2.4,
    "tas": -1.8, "ragal": -1.5, "torokh": -2.3, "mer": -1.8, "merr": -2.0,
    
    # Français
    "decu": -2.0, "deception": -2.2, "nul": -2.4, "nulle": -2.4, "zero": -2.5,
    "ennuyeux": -2.0, "lenteur": -1.8, "lent": -1.5, "lente": -1.5, "ridicule": -2.2,
    "catastrophe": -2.5, "massacre": -2.5, "perte de temps": -2.4, "inutile": -1.8,
    "honte": -2.3, "honteux": -2.4, "marre": -1.9, "en a marre": -2.2,
    "pub": -1.5, "publicite": -1.5, "publicites": -1.6, "trop de pub": -2.2,
    "repetitif": -1.8, "incoherent": -2.0, "incoherence": -2.0, "scandale": -2.2,
    "mal joue": -2.2, "surjoue": -1.9, "gache": -2.2, "pire": -2.3,
    "manque": -1.2, "mauvais": -2.0, "mauvaise": -2.0, "fatiguant": -1.8,
    "degoute": -2.3, "faux": -1.4, "foutaise": -2.5, "n'importe quoi": -2.3,
}

# Modificateurs d'intensité
INTENSIFIERS = {
    "trop": 1.4, "tres": 1.3, "tellement": 1.3, "grave": 1.4, "vraiment": 1.3,
    "trop de": 1.4, "hyper": 1.4, "super": 1.3, "extraordinaire": 1.5,
    "torop": 1.5, "lol": 1.4, "deug deug": 1.5, "bilahi": 1.2,
}

NEGATIONS = {
    "pas", "ne", "ni", "jamais", "aucun", "aucune", "sans", "dou", "du", "bul", "boul",
}


class SenegalSentimentAnalyzer:
    """Analyseur de sentiments bilingue adapté à la production audiovisuelle sénégalaise."""

    def __init__(self):
        self.pos_lexicon = {normalize_text(k): v for k, v in LEXICON_POSITIVE.items()}
        self.neg_lexicon = {normalize_text(k): v for k, v in LEXICON_NEGATIVE.items()}
        self.intensifiers = {normalize_text(k): v for k, v in INTENSIFIERS.items()}
        self.negations = {normalize_text(k) for k in NEGATIONS}

    def analyze_comment(self, text: str) -> Dict[str, Any]:
        """Analyse un commentaire et extrait son sentiment, sa polarité et ses mots-clés."""
        if not text or not isinstance(text, str):
            return {
                "sentiment": "NEUTRE",
                "polarity": 0.0,
                "confidence": 0.5,
                "keywords_positive": [],
                "keywords_negative": [],
                "net_sentiment_score": 0.0,
            }

        norm = normalize_text(text)
        words = re.findall(r"\b[a-z']+\b", norm)
        
        pos_score = 0.0
        neg_score = 0.0
        kw_pos = []
        kw_neg = []

        # Recherche de n-grammes (2 à 3 mots pour les expressions comme "doy na waar", "chef d'oeuvre")
        text_spaced = f" {norm} "
        for phrase, weight in self.pos_lexicon.items():
            if " " in phrase and f" {phrase} " in text_spaced:
                pos_score += weight
                kw_pos.append(phrase)

        for phrase, weight in self.neg_lexicon.items():
            if " " in phrase and f" {phrase} " in text_spaced:
                neg_score += abs(weight)
                kw_neg.append(phrase)

        # Analyse mot à mot avec prise en compte du contexte local (négation, intensificateur)
        for i, w in enumerate(words):
            multiplier = 1.0
            is_negated = False

            if i > 0:
                prev = words[i - 1]
                if prev in self.intensifiers:
                    multiplier *= self.intensifiers[prev]
                if prev in self.negations:
                    is_negated = True
            if i > 1:
                prev2 = words[i - 2]
                if prev2 in self.negations:
                    is_negated = True

            if w in self.pos_lexicon and w not in kw_pos:
                val = self.pos_lexicon[w] * multiplier
                if is_negated:
                    neg_score += val * 0.9
                    kw_neg.append(f"pas {w}")
                else:
                    pos_score += val
                    kw_pos.append(w)

            elif w in self.neg_lexicon and w not in kw_neg:
                val = abs(self.neg_lexicon[w]) * multiplier
                if is_negated:
                    pos_score += val * 0.8
                    kw_pos.append(f"pas {w}")
                else:
                    neg_score += val
                    kw_neg.append(w)

        # Calcul de la polarité normalisée entre -1.0 et +1.0
        total = pos_score + neg_score
        if total == 0:
            polarity = 0.0
            sentiment = "NEUTRE"
            confidence = 0.50
        else:
            polarity = (pos_score - neg_score) / (total + 0.5)
            polarity = max(-1.0, min(1.0, polarity))

            if polarity >= 0.18:
                sentiment = "POSITIF"
                confidence = min(0.98, 0.60 + abs(polarity) * 0.38)
            elif polarity <= -0.18:
                sentiment = "NÉGATIF"
                confidence = min(0.98, 0.60 + abs(polarity) * 0.38)
            else:
                sentiment = "NEUTRE"
                confidence = 0.65

        # Score de Sentiment Net (NSS) allant de -100 à +100
        nss = round(polarity * 100, 1)

        return {
            "sentiment": sentiment,
            "polarity": round(polarity, 3),
            "confidence": round(confidence, 2),
            "keywords_positive": list(set(kw_pos)),
            "keywords_negative": list(set(kw_neg)),
            "net_sentiment_score": nss,
        }

    def batch_analyze(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse un ensemble de commentaires et calcule les métriques agrégées."""
        if not comments:
            return {
                "total_comments": 0,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
                "positive_pct": 0.0,
                "neutral_pct": 0.0,
                "negative_pct": 0.0,
                "net_sentiment_score": 0.0,
                "results": [],
            }

        pos = 0
        neu = 0
        neg = 0
        results = []
        nss_sum = 0.0

        for item in comments:
            txt = item.get("text", "")
            res = self.analyze_comment(txt)
            merged = {**item, **res}
            results.append(merged)

            if res["sentiment"] == "POSITIF":
                pos += 1
            elif res["sentiment"] == "NÉGATIF":
                neg += 1
            else:
                neu += 1
            nss_sum += res["net_sentiment_score"]

        total = len(comments)
        pos_pct = round((pos / total) * 100, 1) if total > 0 else 0.0
        neu_pct = round((neu / total) * 100, 1) if total > 0 else 0.0
        neg_pct = round((neg / total) * 100, 1) if total > 0 else 0.0
        avg_nss = round((pos_pct - neg_pct), 1)

        return {
            "total_comments": total,
            "positive_count": pos,
            "neutral_count": neu,
            "negative_count": neg,
            "positive_pct": pos_pct,
            "neutral_pct": neu_pct,
            "negative_pct": neg_pct,
            "net_sentiment_score": avg_nss,
            "results": results,
        }
