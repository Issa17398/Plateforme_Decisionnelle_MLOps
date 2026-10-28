"""Module de données et visualisations d'Analyse des Sentiments du public sénégalais (Sprint 6).

Fournit :
1. Un référentiel de commentaires représentatifs et authentiques du public sénégalais (Français & Wolof)
2. Des fonctions d'agrégation statistique par série/franchise et par chaîne
3. Des composants graphiques Plotly spécialisés pour la restitution de la satisfaction et des controverses
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ml.sentiment import SenegalSentimentAnalyzer

# Palette Luminous Studio (Adaptée au thème clair / lisible)
COLOR_POS = "#10B981"  # Émeraude
COLOR_NEU = "#64748B"  # Ardoise neutre
COLOR_NEG = "#EF4444"  # Rouge rubis
COLOR_GOLD = "#D97706"  # Or ambré
COLOR_BLUE = "#2563EB"  # Bleu royal

PLOTLY_LIGHT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#0F172A"),
    margin=dict(l=24, r=24, t=44, b=24),
)

# Commentaires représentatifs du public sénégalais par franchise
SAMPLE_COMMENT_TEMPLATES = [
    # Positifs élogieux (Wolof / Français)
    {"text": "Machallah actrice bi dafa meun série bi nekh na torop ! Bravo aux acteurs.", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Félicitations pour cet épisode, le jeu d'acteur est incroyable et émouvant !", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Bilahi Amina dafa meun rôle bi, fierté sénégalaise, sa kaw sa kanam !", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Chef d'œuvre vraiment ! Rien à dire, EvenProd amna solo torop.", "franchise": "Bété Bété", "channel": "EvenProd"},
    {"text": "Nekhna trop suspence bi lourd na, félicitations à toute l'équipe.", "franchise": "Bété Bété", "channel": "EvenProd"},
    {"text": "Grand bravo ! Ce scénario est très touchant et plein de leçons de vie.", "franchise": "Bété Bété", "channel": "EvenProd"},
    {"text": "La meilleure série de l'année au Sénégal, jeu d'acteur exceptionnel.", "franchise": "Infidèles", "channel": "EvenProd"},
    {"text": "Pikini Production dafa am créativité, masterclass chaque semaine !", "franchise": "Virginie", "channel": "Pikini Production"},
    {"text": "Virginie dafa rafet, les jeunes acteurs sont tellement talentueux.", "franchise": "Virginie", "channel": "Pikini Production"},
    {"text": "Emprises dafa puissant, on sent que la qualité s'améliore d'année en année.", "franchise": "Emprises", "channel": "Marodi TV"},
    {"text": "Cœurs Brisés saison 2 m'a fait pleurer, tellement captivant et propre.", "franchise": "Cœurs Brisés", "channel": "EvenProd"},
    {"text": "Salma est une pépite, merci Marodi pour ces productions professionnelles.", "franchise": "Salma", "channel": "Marodi TV"},
    
    # Critiques & Déceptions (Wolof / Français)
    {"text": "Doy na waar trop de publicités et lenteur, le scénario est complètement gâché.", "franchise": "Infidèles", "channel": "EvenProd"},
    {"text": "Franchement déçu par cet épisode, beaucoup d'incohérences et c'est répétitif.", "franchise": "Infidèles", "channel": "EvenProd"},
    {"text": "Yakhou na trop, ils ont tué la série avec cette saison inutile et vide.", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Arrêtez le massacre s'il vous plaît, 40 minutes d'épisode dont 15 minutes de pub !", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Sof na trop, les acteurs surjouent et l'histoire ne bouge plus d'un centimètre.", "franchise": "Virginie", "channel": "Pikini Production"},
    {"text": "Grosse déception pour le dénouement final, fin bâclée et ridicule.", "franchise": "Bété Bété", "channel": "EvenProd"},
    {"text": "Ay thiakhane rekk, aucun respect pour les spectateurs avec ce retard de sortie.", "franchise": "Emprises", "channel": "Marodi TV"},
    {"text": "La qualité du son est mauvaise cette fois, réglez vos micros svp c'est inaudible.", "franchise": "Cœurs Brisés", "channel": "EvenProd"},
    {"text": "Sénario bi dafa lent torop, j'ai failli m'endormir devant cet épisode.", "franchise": "Salma", "channel": "Marodi TV"},

    # Neutres & Questionnements
    {"text": "À quelle heure sort l'épisode 45 ? On attend depuis midi.", "franchise": "Karma", "channel": "Marodi TV"},
    {"text": "Est-ce qu'il y aura une saison 3 pour cette série ou c'est terminé ?", "franchise": "Bété Bété", "channel": "EvenProd"},
    {"text": "Qui connaît le nom de la musique du générique de début ?", "franchise": "Virginie", "channel": "Pikini Production"},
    {"text": "Rendez-vous vendredi prochain inchallah pour la suite.", "franchise": "Infidèles", "channel": "EvenProd"},
    {"text": "Quelqu'un peut m'expliquer ce que le père a dit à la minute 12 ?", "franchise": "Emprises", "channel": "Marodi TV"},
    {"text": "Episode disponible en replay dès maintenant.", "franchise": "Salma", "channel": "Marodi TV"},
]


def generate_extended_sentiment_dataset(n_samples: int = 1200) -> pd.DataFrame:
    """Génère un dataset riche et équilibré de commentaires annotés."""
    analyzer = SenegalSentimentAnalyzer()
    random.seed(42)
    np.random.seed(42)

    franchises = [
        ("Karma", "Marodi TV", 0.65, 0.15, 0.20),
        ("Bété Bété", "EvenProd", 0.72, 0.16, 0.12),
        ("Infidèles", "EvenProd", 0.52, 0.18, 0.30),
        ("Virginie", "Pikini Production", 0.68, 0.17, 0.15),
        ("Emprises", "Marodi TV", 0.60, 0.20, 0.20),
        ("Cœurs Brisés", "EvenProd", 0.66, 0.18, 0.16),
        ("Salma", "Marodi TV", 0.63, 0.22, 0.15),
        ("Maitresse d'un Homme Marié", "Marodi TV", 0.54, 0.16, 0.30),
        ("Idoles", "EvenProd", 0.70, 0.18, 0.12),
        ("Golden", "Marodi TV", 0.69, 0.19, 0.12),
    ]

    records = []
    authors = [
        "Fatou Ndiaye", "Moussa Diop", "Aïssatou Sow", "Babacar Fall",
        "Khadija Seck", "Ousmane Diallo", "Mariama Ba", "Ibrahima Gueye",
        "Aminata Cissé", "Cheikh Sarr", "Ndeye Astou", "Modou Lo",
        "Sokhna Diagne", "Abdoulaye Faye", "Rama Traoré", "Alioune Badara",
    ]

    for i in range(n_samples):
        # Tirage d'une franchise
        fr_choice = random.choice(franchises)
        fr_name, ch_name, p_pos, p_neu, p_neg = fr_choice

        # Tirage de la tonalité selon la propension de la franchise
        sentiment_type = np.random.choice(["POS", "NEU", "NEG"], p=[p_pos, p_neu, p_neg])

        if sentiment_type == "POS":
            candidates = [t for t in SAMPLE_COMMENT_TEMPLATES if "Bravo" in t["text"] or "Machallah" in t["text"] or "Félicitations" in t["text"] or "nekh" in t["text"] or "fierté" in t["text"] or "magnifique" in t["text"]]
        elif sentiment_type == "NEG":
            candidates = [t for t in SAMPLE_COMMENT_TEMPLATES if "déçu" in t["text"] or "Doy na waar" in t["text"] or "publicité" in t["text"] or "Yakhou" in t["text"] or "massacre" in t["text"] or "incohérences" in t["text"]]
        else:
            candidates = [t for t in SAMPLE_COMMENT_TEMPLATES if "À quelle heure" in t["text"] or "Est-ce qu'il" in t["text"] or "musique" in t["text"] or "inchallah" in t["text"]]

        base = random.choice(candidates)["text"] if candidates else "Épisode très intéressant."
        
        # Variations stylistiques réalistes
        if random.random() > 0.6:
            base += " " + random.choice(["🔥🔥", "👏🏾👏🏾", "🇸🇳❤️", "❤️", "🙌🏾", "💯"])

        res = analyzer.analyze_comment(base)
        likes = int(np.random.exponential(14))

        records.append({
            "comment_id": f"COM_{i+1:05d}",
            "author": random.choice(authors),
            "franchise": fr_name,
            "channel_title": ch_name,
            "text": base,
            "sentiment": res["sentiment"],
            "polarity": res["polarity"],
            "confidence": res["confidence"],
            "net_sentiment_score": res["net_sentiment_score"],
            "keywords_detected": ", ".join(res["keywords_positive"] + res["keywords_negative"]),
            "like_count": likes,
        })

    return pd.DataFrame(records)


def compute_sentiment_kpis(df_sentiments: pd.DataFrame) -> Dict[str, Any]:
    """Calcule les indicateurs clés de performance des sentiments."""
    total = len(df_sentiments)
    pos = (df_sentiments["sentiment"] == "POSITIF").sum()
    neu = (df_sentiments["sentiment"] == "NEUTRE").sum()
    neg = (df_sentiments["sentiment"] == "NÉGATIF").sum()

    pos_pct = (pos / total * 100) if total > 0 else 0.0
    neu_pct = (neu / total * 100) if total > 0 else 0.0
    neg_pct = (neg / total * 100) if total > 0 else 0.0
    nss = round(pos_pct - neg_pct, 1)

    return {
        "total_comments": total,
        "positive_count": pos,
        "neutral_count": neu,
        "negative_count": neg,
        "positive_pct": round(pos_pct, 1),
        "neutral_pct": round(neu_pct, 1),
        "negative_pct": round(neg_pct, 1),
        "net_sentiment_score": nss,
        "average_polarity": round(df_sentiments["polarity"].mean(), 3),
    }


def compute_franchise_sentiment_benchmarks(df_sentiments: pd.DataFrame) -> pd.DataFrame:
    """Calcule les ratios de satisfaction et NSS pour chaque saga."""
    grouped = df_sentiments.groupby("franchise").agg(
        total_comments=("comment_id", "count"),
        positive_count=("sentiment", lambda s: (s == "POSITIF").sum()),
        neutral_count=("sentiment", lambda s: (s == "NEUTRE").sum()),
        negative_count=("sentiment", lambda s: (s == "NÉGATIF").sum()),
        avg_polarity=("polarity", "mean"),
    ).reset_index()

    grouped["Taux Satisfaction (%)"] = (grouped["positive_count"] / grouped["total_comments"] * 100).round(1)
    grouped["Taux Neutre (%)"] = (grouped["neutral_count"] / grouped["total_comments"] * 100).round(1)
    grouped["Taux Critique (%)"] = (grouped["negative_count"] / grouped["total_comments"] * 100).round(1)
    grouped["Score NSS (Net)"] = (grouped["Taux Satisfaction (%)"] - grouped["Taux Critique (%)"]).round(1)

    return grouped.sort_values("Score NSS (Net)", ascending=False)


# =========================================================================
# GRAPHIQUES PLOTLY SPÉCIALISÉS (THÈME CLAIR & LISIBLE)
# =========================================================================

def plot_sentiment_donut(kpis: Dict[str, Any]) -> go.Figure:
    """Donut de distribution globale des sentiments."""
    labels = ["Positif (Éloges)", "Neutre (Questions)", "Négatif (Critiques)"]
    values = [kpis["positive_count"], kpis["neutral_count"], kpis["negative_count"]]
    colors = [COLOR_POS, COLOR_NEU, COLOR_NEG]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.60,
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2.5)),
                textinfo="label+percent",
                textfont=dict(size=13, family="Outfit", color="#0F172A"),
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        title="<b>Répartition Globale des Sentiments du Public</b>",
        title_font=dict(size=16, color="#0F172A", family="Outfit"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
        height=360,
        **PLOTLY_LIGHT_DEFAULTS,
    )
    return fig


def plot_sentiment_by_franchise(df_franchises_sentiment: pd.DataFrame) -> go.Figure:
    """Barres empilées 100% comparant la satisfaction entre franchises."""
    df_plot = df_franchises_sentiment.sort_values("Score NSS (Net)", ascending=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df_plot["franchise"],
            x=df_plot["Taux Satisfaction (%)"],
            name="Positif (%)",
            orientation="h",
            marker=dict(color=COLOR_POS),
            hovertemplate="<b>%{y}</b><br>Positif : %{x:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=df_plot["franchise"],
            x=df_plot["Taux Neutre (%)"],
            name="Neutre (%)",
            orientation="h",
            marker=dict(color=COLOR_NEU),
            hovertemplate="<b>%{y}</b><br>Neutre : %{x:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=df_plot["franchise"],
            x=df_plot["Taux Critique (%)"],
            name="Critique (%)",
            orientation="h",
            marker=dict(color=COLOR_NEG),
            hovertemplate="<b>%{y}</b><br>Critique : %{x:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        title="<b>Profil d'Opinion du Public par Saga (Positif / Neutre / Critique)</b>",
        title_font=dict(size=16, color="#0F172A", family="Outfit"),
        xaxis=dict(title="Pourcentage (%)", maxallowed=100, showgrid=True, gridcolor="#E2E8F0"),
        yaxis=dict(title="", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        height=400,
        **PLOTLY_LIGHT_DEFAULTS,
    )
    return fig


def plot_sentiment_nss_benchmark(df_franchises_sentiment: pd.DataFrame) -> go.Figure:
    """Barres du Score de Sentiment Net (NSS) par franchise."""
    df_sorted = df_franchises_sentiment.sort_values("Score NSS (Net)", ascending=False)
    colors = [COLOR_POS if v >= 40 else (COLOR_GOLD if v >= 20 else COLOR_NEG) for v in df_sorted["Score NSS (Net)"]]

    fig = go.Figure(
        go.Bar(
            x=df_sorted["franchise"],
            y=df_sorted["Score NSS (Net)"],
            text=[f"{v:+.1f}" for v in df_sorted["Score NSS (Net)"]],
            textposition="auto",
            marker=dict(color=colors, line=dict(color="#CBD5E1", width=1)),
            hovertemplate="<b>%{x}</b><br>Score NSS : %{y:+.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="<b>Indice de Satisfaction Nette (Net Sentiment Score - NSS) de -100 à +100</b>",
        title_font=dict(size=16, color="#0F172A", family="Outfit"),
        xaxis=dict(title="Saga / Franchise", showgrid=False, tickangle=-30),
        yaxis=dict(title="Score NSS", showgrid=True, gridcolor="#E2E8F0"),
        height=380,
        **PLOTLY_LIGHT_DEFAULTS,
    )
    return fig
