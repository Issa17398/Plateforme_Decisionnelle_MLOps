"""Module complet de visualisations graphiques analytiques et comportementales avec Plotly.

Palette et typographie adaptées au mode clair haute lisibilité :
- Textes et titres : Ardoise profonde (#0F172A, #334155)
- Grilles : Lignes fines douces (#E2E8F0)
- Accents : Or Sénégal (#D97706), Émeraude (#10B981), Bleu Royal (#2563EB), Pourpre (#8B5CF6)
"""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

COLOR_GOLD = "#D97706"
COLOR_AMBER_LIGHT = "#F59E0B"
COLOR_EMERALD = "#10B981"
COLOR_BLUE = "#2563EB"
COLOR_PURPLE = "#7C3AED"
COLOR_CRIMSON = "#DC2626"
COLOR_SLATE = "#475569"
COLOR_DARK_TEXT = "#0F172A"

PLOTLY_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#0F172A"),
    margin=dict(l=24, r=24, t=44, b=24),
)


def plot_market_share(df_channels: pd.DataFrame) -> go.Figure:
    """Diagramme Donut des parts d'audience cumulées."""
    colors = [COLOR_GOLD, COLOR_BLUE, COLOR_PURPLE, COLOR_EMERALD]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=df_channels["channel_title"],
                values=df_channels["total_cumulative_views"],
                hole=0.58,
                textinfo="label+percent",
                textfont=dict(size=13, family="Outfit", color="#0F172A"),
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2.5)),
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        title="<b>Parts d'Audience Cumulée par Chaîne</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5, font=dict(color=COLOR_DARK_TEXT)),
        height=380,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_views_by_content_type(df_videos: pd.DataFrame) -> go.Figure:
    """Diagramme à barres comparant l'audience médiane par format éditorial."""
    agg = df_videos.groupby("content_type")["view_count"].agg(["median", "count"]).reset_index()
    agg.columns = ["content_type", "median", "count"]
    agg = agg.sort_values("median", ascending=False)

    colors = [COLOR_GOLD if c == "EPISODE" else (COLOR_BLUE if c == "TEASER" else COLOR_PURPLE) for c in agg["content_type"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=agg["content_type"],
                y=agg["median"],
                text=[f"{v:,.0f} vues".replace(",", " ") for v in agg["median"]],
                textposition="auto",
                marker=dict(color=colors, line=dict(color="#CBD5E1", width=1)),
                hovertemplate="<b>Format %{x}</b><br>Médiane : %{y:,.0f} vues<br>Effectif : %{customdata} vidéos<extra></extra>",
                customdata=agg["count"],
            )
        ]
    )
    fig.update_layout(
        title="<b>Audience Médiane par Format Éditorial</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Format", showgrid=False, title_font=dict(color=COLOR_DARK_TEXT), tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="Vues Médianes", showgrid=True, gridcolor="#E2E8F0", title_font=dict(color=COLOR_DARK_TEXT), tickfont=dict(color=COLOR_DARK_TEXT)),
        height=380,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_hourly_audience(df_videos: pd.DataFrame) -> go.Figure:
    """Courbe d'audience selon l'heure de publication avec mise en valeur du Prime-Time."""
    agg_hour = df_videos.groupby("published_hour")["view_count"].median().reset_index()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=agg_hour["published_hour"],
            y=agg_hour["view_count"],
            mode="lines+markers",
            name="Vues Médianes",
            line=dict(color=COLOR_GOLD, width=3.5, shape="spline"),
            marker=dict(size=8, color=COLOR_GOLD, line=dict(color="#FFFFFF", width=1.5)),
            fill="tozeroy",
            fillcolor="rgba(217, 119, 6, 0.10)",
        )
    )

    # Zone Prime-Time (19h - 22h)
    fig.add_vrect(
        x0=19,
        x1=22,
        fillcolor="rgba(217, 119, 6, 0.18)",
        layer="below",
        line_width=1.5,
        line_color=COLOR_GOLD,
        annotation_text="⭐ Prime-Time National (19h30 - 21h30)",
        annotation_position="top left",
        annotation_font=dict(color=COLOR_GOLD, size=11, family="Outfit"),
    )

    fig.update_layout(
        title="<b>Courbe d'Audience Horaire & Prime-Time Sénégalais</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Heure de mise en ligne (0h - 23h GMT)", tickmode="linear", dtick=2, showgrid=False, tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="Vues Médianes", showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT)),
        height=380,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_behavioral_heatmap_2d(pivot_matrix: pd.DataFrame) -> go.Figure:
    """Matrice 2D interactive Jour x Heure pour l'analyse comportementale du public."""
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_matrix.values,
            x=[f"{h}h" for h in pivot_matrix.columns],
            y=pivot_matrix.index,
            colorscale=[
                [0.0, "#F8FAFC"],
                [0.2, "#E2E8F0"],
                [0.5, "#93C5FD"],
                [0.75, "#FCD34D"],
                [1.0, "#D97706"],
            ],
            colorbar=dict(
                title=dict(text="Vues Méd.", font=dict(color=COLOR_DARK_TEXT, size=11)),
                tickfont=dict(color=COLOR_DARK_TEXT),
            ),
            hovertemplate="<b>%{y} à %{x}</b><br>Audience Médiane : %{z:,.0f} vues<extra></extra>",
        )
    )

    fig.update_layout(
        title="<b>Matrice Comportementale d'Audience (Jour de la semaine x Heure de diffusion)</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Heure de publication", showgrid=False, tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="Jour de diffusion", showgrid=False, tickfont=dict(color=COLOR_DARK_TEXT)),
        height=360,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_engagement_vs_views_scatter(df_videos: pd.DataFrame) -> go.Figure:
    """Nuage de points : Notoriété (Vues) vs Fidélité Communautaire (Taux d'Engagement)."""
    clean = df_videos.dropna(subset=["view_count", "engagement_rate_pct"]).copy()
    clean = clean[clean["view_count"] > 0]
    clean["comment_count_clean"] = clean["comment_count"].fillna(0).clip(lower=0)
    clean["bubble_size"] = np.log1p(clean["comment_count_clean"]) + 3

    sample_size = min(len(clean), 2500)
    sample = clean.sample(sample_size, random_state=42) if len(clean) > sample_size else clean

    fig = px.scatter(
        sample,
        x="view_count",
        y="engagement_rate_pct",
        color="channel_title",
        size="bubble_size",
        hover_name="title",
        log_x=True,
        color_discrete_map={
            "EvenProd": COLOR_GOLD,
            "Marodi TV": COLOR_BLUE,
            "Pikini Production": COLOR_PURPLE,
        },
        labels={
            "view_count": "Nombre de Vues (Échelle Log)",
            "engagement_rate_pct": "Taux d'Engagement (%)",
            "channel_title": "Chaîne",
            "bubble_size": "Commentaires (Log)",
        },
        opacity=0.72,
    )

    fig.update_layout(
        title="<b>Psychologie de l'Engagement : Volume de Vues vs Taux d'Engagement (%)</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5, font=dict(color=COLOR_DARK_TEXT)),
        height=420,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT))
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT))
    return fig


def plot_debate_vs_consensus_scatter(df_videos: pd.DataFrame) -> go.Figure:
    """Analyse de controverse / débat : Likes vs Commentaires."""
    clean = df_videos.dropna(subset=["like_count", "comment_count"]).copy()
    clean = clean[(clean["like_count"] > 0) & (clean["comment_count"] > 0)]

    sample_size = min(len(clean), 2500)
    sample = clean.sample(sample_size, random_state=42) if len(clean) > sample_size else clean

    fig = px.scatter(
        sample,
        x="like_count",
        y="comment_count",
        color="content_type",
        hover_name="title",
        log_x=True,
        log_y=True,
        color_discrete_map={
            "EPISODE": COLOR_GOLD,
            "TEASER": COLOR_BLUE,
            "SHORT": COLOR_EMERALD,
            "OTHER": COLOR_PURPLE,
        },
        labels={
            "like_count": "Nombre de Likes (Log)",
            "comment_count": "Nombre de Commentaires (Log)",
            "content_type": "Format",
        },
        opacity=0.70,
    )

    fig.update_layout(
        title="<b>Indice de Débat & Controverse : Likes (Approbation) vs Commentaires (Débats)</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5, font=dict(color=COLOR_DARK_TEXT)),
        height=420,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT))
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT))
    return fig


def plot_format_distribution_box(df_videos: pd.DataFrame) -> go.Figure:
    """Boîtes à moustaches (Box Plot) montrant la dispersion des vues par format."""
    fig = px.box(
        df_videos,
        x="content_type",
        y="view_count",
        color="content_type",
        log_y=True,
        color_discrete_sequence=[COLOR_GOLD, COLOR_BLUE, COLOR_EMERALD, COLOR_PURPLE],
        labels={"content_type": "Format Éditorial", "view_count": "Vues (Échelle Log)"},
    )
    fig.update_layout(
        title="<b>Dispersion & Asymétrie des Audiences par Format Éditorial</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        showlegend=False,
        height=380,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(tickfont=dict(color=COLOR_DARK_TEXT))
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT))
    return fig


def plot_monthly_evolution(monthly_df: pd.DataFrame) -> go.Figure:
    """Évolution chronologique : Volume de vidéos produites vs Vues totales cumulées."""
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=monthly_df["year_month"],
            y=monthly_df["videos_count"],
            name="Vidéos Publiées",
            marker=dict(color="rgba(37, 99, 235, 0.45)", line=dict(color=COLOR_BLUE, width=1)),
            yaxis="y",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=monthly_df["year_month"],
            y=monthly_df["total_views"],
            name="Vues Cumulées",
            mode="lines",
            line=dict(color=COLOR_GOLD, width=3),
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="<b>Dynamique Temporelle : Cadence de Publication et Volume d'Audience par Mois</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Mois de Publication", showgrid=False, tickangle=-45, tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="Nombre de Vidéos", showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis2=dict(
            title="Vues Totales",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=",.0s",
            tickfont=dict(color=COLOR_DARK_TEXT),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, font=dict(color=COLOR_DARK_TEXT)),
        height=400,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_franchises_benchmark(franchises_df: pd.DataFrame) -> go.Figure:
    """Benchmark des sagas et séries télévisées cultes sénégalaises."""
    top10 = franchises_df.head(10).sort_values("Vues Médianes", ascending=True)

    fig = go.Figure(
        go.Bar(
            x=top10["Vues Médianes"],
            y=top10["Franchise"],
            orientation="h",
            text=[f"{v:,.0f} vues".replace(",", " ") for v in top10["Vues Médianes"]],
            textposition="auto",
            marker=dict(
                color=COLOR_GOLD,
                line=dict(color="#CBD5E1", width=1),
            ),
            hovertemplate="<b>%{y}</b><br>Médiane : %{x:,.0f} vues<br>Hits (≥ 1M) : %{customdata[0]}<br>Chaîne : %{customdata[1]}<extra></extra>",
            customdata=top10[["Hits (≥ 1M)", "Chaîne Principale"]].values,
        )
    )

    fig.update_layout(
        title="<b>Top 10 des Franchises & Séries Cultes (par Audience Médiane)</b>",
        title_font=dict(size=16, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Vues Médianes", showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="", showgrid=False, tickfont=dict(color=COLOR_DARK_TEXT, size=12)),
        height=400,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_hit_gauge(hit_prob_pct: float) -> go.Figure:
    """Jauge moderne affichant la probabilité que la vidéo atteigne ≥ 1M de vues."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=hit_prob_pct,
            number={"suffix": "%", "font": {"size": 42, "color": COLOR_DARK_TEXT, "family": "Outfit"}},
            title={"text": "<b>PROBABILITÉ DE HIT VIRAL (≥ 1M VUES)</b>", "font": {"size": 13, "color": COLOR_SLATE}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": COLOR_SLATE},
                "bar": {"color": COLOR_GOLD, "thickness": 0.3},
                "bgcolor": "#F1F5F9",
                "borderwidth": 1,
                "bordercolor": "#CBD5E1",
                "steps": [
                    {"range": [0, 25], "color": "#F1F5F9"},
                    {"range": [25, 50], "color": "#DBEAFE"},
                    {"range": [50, 80], "color": "#FEF3C7"},
                    {"range": [80, 100], "color": "#D1FAE5"},
                ],
                "threshold": {
                    "line": {"color": COLOR_EMERALD, "width": 4},
                    "thickness": 0.8,
                    "value": 50,
                },
            },
        )
    )
    fig.update_layout(height=260, **PLOTLY_LAYOUT_DEFAULTS)
    return fig


def plot_confidence_interval(pred_views: int, lower_bound: int, upper_bound: int) -> go.Figure:
    """Visualisation de l'intervalle de confiance à 80% des vues prédites."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=[lower_bound, upper_bound],
            y=["Vues Estimées", "Vues Estimées"],
            mode="lines",
            line=dict(color=COLOR_BLUE, width=10),
            name="Intervalle 80%",
            hoverinfo="none",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[pred_views],
            y=["Vues Estimées"],
            mode="markers+text",
            marker=dict(color=COLOR_GOLD, size=20, symbol="diamond", line=dict(color="#0F172A", width=2)),
            text=[f"  <b>{pred_views:,.0f} vues</b>".replace(",", " ")],
            textposition="top center",
            textfont=dict(color=COLOR_DARK_TEXT, size=13),
            name="Prédiction Centrale",
        )
    )

    fig.update_layout(
        title="<b>Fourchette d'Audience Estimée (Intervalle de Confiance 80%)</b>",
        title_font=dict(size=14, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(
            title="Nombre de Vues",
            showgrid=True,
            gridcolor="#E2E8F0",
            tickformat=",.0f",
            tickfont=dict(color=COLOR_DARK_TEXT),
        ),
        yaxis=dict(showticklabels=False),
        height=180,
        showlegend=False,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_ab_comparison(pred_a: int, pred_b: int, label_a: str, label_b: str) -> go.Figure:
    """Graphique comparatif A/B de deux scénarios de diffusion."""
    diff = pred_b - pred_a
    pct = (diff / pred_a * 100) if pred_a > 0 else 0

    fig = go.Figure(
        data=[
            go.Bar(
                x=[label_a, label_b],
                y=[pred_a, pred_b],
                text=[f"{pred_a:,.0f} vues".replace(",", " "), f"{pred_b:,.0f} vues".replace(",", " ")],
                textposition="auto",
                marker=dict(color=[COLOR_BLUE, COLOR_EMERALD if diff >= 0 else COLOR_CRIMSON]),
            )
        ]
    )

    fig.update_layout(
        title=f"<b>Comparatif A/B : Impact Estimé = {pct:+.1f}% ({diff:+,.0f} vues)</b>",
        title_font=dict(size=15, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(title="Scénario", showgrid=False, tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(title="Vues Prédites", showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color=COLOR_DARK_TEXT)),
        height=320,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig


def plot_confusion_matrix_interactive(cm_dict: Dict[str, int]) -> go.Figure:
    """Matrice de confusion interactive pour l'onglet MLOps."""
    z = [
        [cm_dict["true_negatives"], cm_dict["false_positives"]],
        [cm_dict["false_negatives"], cm_dict["true_positives"]],
    ]
    x = ["Prédit Normal (< 1M)", "Prédit Hit (≥ 1M)"]
    y = ["Réel Normal (< 1M)", "Réel Hit (≥ 1M)"]

    total = sum([cm_dict["true_negatives"], cm_dict["false_positives"], cm_dict["false_negatives"], cm_dict["true_positives"]])

    text_matrix = [
        [
            f"<b>{z[0][0]:,}</b><br>({z[0][0]/total*100:.1f}%)",
            f"<b>{z[0][1]:,}</b><br>({z[0][1]/total*100:.1f}%)",
        ],
        [
            f"<b>{z[1][0]:,}</b><br>({z[1][0]/total*100:.1f}%)",
            f"<b>{z[1][1]:,}</b><br>({z[1][1]/total*100:.1f}%)",
        ],
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale=[[0, "#EFF6FF"], [0.4, "#93C5FD"], [0.8, "#2563EB"], [1, "#D97706"]],
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 15, "color": "#0F172A", "family": "Outfit"},
            showscale=False,
        )
    )
    fig.update_layout(
        title="<b>Matrice de Confusion sur Test Holdout Strict (N = 3 167)</b>",
        title_font=dict(size=15, color=COLOR_DARK_TEXT, family="Outfit"),
        xaxis=dict(tickfont=dict(color=COLOR_DARK_TEXT)),
        yaxis=dict(tickfont=dict(color=COLOR_DARK_TEXT)),
        height=340,
        **PLOTLY_LAYOUT_DEFAULTS,
    )
    return fig
