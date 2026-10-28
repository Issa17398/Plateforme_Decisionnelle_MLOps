"""Feuille de styles CSS personnalisée et Design System Luminous Studio pour l'application Streamlit.

Design System Haute Lisibilité :
- Palette : Fond Clair Nacré (#F8FAFC), Cartes Blanc Pur (#FFFFFF), Ardoise Profonde (#0F172A, #1E293B, #334155)
- Accents Nationaux : Or Sénégal Ambré (#D97706, #F59E0B), Émeraude (#059669, #10B981), Bleu Royal (#2563EB), Rubis (#DC2626)
- Typographie : Outfit (Titres, Métriques, Badges) & Inter (Corps de texte) & JetBrains Mono (Code/Valeurs)
- Objectif : Contraste maximal, clarté visuelle et lisibilité reposante pour les yeux
"""

from __future__ import annotations
import streamlit as st

__all__ = [
    "apply_custom_styles",
    "render_hero_banner",
    "render_section_header",
    "render_kpi_card",
    "render_strategic_card",
    "render_footer",
]


def apply_custom_styles() -> None:
    """Injecte l'ensemble des règles CSS modernes en mode clair et lumineux dans Streamlit."""
    custom_css = """
    <style>
        /* =========================================================================
           1. TYPOGRAPHIES PREMIUM GOOGLE FONTS
           ========================================================================= */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        /* Réinitialisation globale & Lisibilité accrue */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #1E293B !important;
            -webkit-font-smoothing: antialiased;
        }

        h1, h2, h3, h4, h5, h6, .display-font {
            font-family: 'Outfit', sans-serif !important;
            letter-spacing: -0.025em;
            font-weight: 700;
            color: #0F172A !important;
        }

        p, span, label, div {
            color: #1E293B;
        }

        code, pre, .mono-font {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* =========================================================================
           2. FOND DE PAGE LUMINEUX & AÉRÉ (LUMINOUS STUDIO)
           ========================================================================= */
        .stApp {
            background-color: #F8FAFC !important;
            background-image: 
                radial-gradient(circle at 10% 8%, rgba(245, 158, 11, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 92%, rgba(37, 99, 235, 0.06) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
        }

        header[data-testid="stHeader"] {
            background: rgba(248, 250, 252, 0.85) !important;
            backdrop-filter: blur(12px) !important;
        }
        footer {
            visibility: hidden;
        }

        /* Barre de défilement discrète et claire */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #F1F5F9;
        }
        ::-webkit-scrollbar-thumb {
            background: #CBD5E1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #D97706;
        }

        /* =========================================================================
           3. HERO BANNER DE HAUTE PRÉCISION (CLAIRE & CONTRASTÉE)
           ========================================================================= */
        .hero-banner-luminous {
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 55%, #F1F5F9 100%);
            border: 1px solid #E2E8F0;
            border-top: 2px solid #D97706;
            border-radius: 20px;
            padding: 30px 36px;
            margin-bottom: 26px;
            box-shadow: 0 10px 30px -6px rgba(15, 23, 42, 0.08), 0 2px 6px -1px rgba(15, 23, 42, 0.04);
            position: relative;
            overflow: hidden;
        }
        .hero-banner-luminous::after {
            content: "";
            position: absolute;
            top: 0; right: 0; width: 280px; height: 100%;
            background: radial-gradient(circle at right center, rgba(217, 119, 6, 0.08), transparent 70%);
            pointer-events: none;
        }
        .hero-top-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(217, 119, 6, 0.10);
            border: 1px solid rgba(217, 119, 6, 0.28);
            padding: 4px 14px;
            border-radius: 30px;
            color: #B45309;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            margin-bottom: 12px;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            background: #059669;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 rgba(5, 150, 105, 0.7);
            animation: pulse-ring 2s infinite;
        }
        @keyframes pulse-ring {
            0% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.7); }
            70% { box-shadow: 0 0 0 8px rgba(5, 150, 105, 0); }
            100% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0); }
        }
        .hero-title-main {
            color: #0F172A;
            font-size: 2.35rem;
            font-weight: 900;
            margin: 0 0 10px 0;
            letter-spacing: -0.035em;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .hero-title-main span.gradient-gold {
            background: linear-gradient(135deg, #0F172A 30%, #D97706 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-desc {
            color: #334155;
            font-size: 1.05rem;
            line-height: 1.6;
            margin: 0 0 20px 0;
            max-width: 950px;
            font-weight: 400;
        }
        .hero-chips-container {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .hero-chip {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 0.82rem;
            color: #1E293B;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .hero-chip b {
            color: #D97706;
            font-family: 'JetBrains Mono', monospace;
        }

        /* =========================================================================
           4. STRUCTURE DE MODULE ANALYTIQUE (ORGANISATION STRICTE)
           ========================================================================= */
        .section-header-box {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 32px 0 18px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid #E2E8F0;
        }
        .section-title-wrap {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .section-number-pill {
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
            color: #FFFFFF;
            font-family: 'Outfit', sans-serif;
            font-weight: 900;
            font-size: 0.85rem;
            padding: 3px 9px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(217, 119, 6, 0.3);
        }
        .section-title-text {
            color: #0F172A;
            font-size: 1.35rem;
            font-weight: 800;
            margin: 0;
            font-family: 'Outfit', sans-serif;
            letter-spacing: -0.02em;
        }
        .section-subtitle-text {
            color: #475569;
            font-size: 0.9rem;
            margin-top: 3px;
            font-weight: 500;
        }

        /* =========================================================================
           5. CARTES MÉTRIQUES & KPIS LUMINEUSES (HAUT CONTRASTE)
           ========================================================================= */
        .kpi-card-luxury {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 22px 20px;
            box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.05), 0 2px 4px -2px rgba(15, 23, 42, 0.03);
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 140px;
        }
        .kpi-card-luxury:hover {
            transform: translateY(-3px);
            border-color: #D97706;
            box-shadow: 0 12px 26px -4px rgba(217, 119, 6, 0.15);
        }
        .kpi-card-luxury::before {
            content: "";
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: #D97706;
            border-radius: 16px 0 0 16px;
        }
        .kpi-card-emerald::before { background: #059669; }
        .kpi-card-blue::before { background: #2563EB; }
        .kpi-card-purple::before { background: #7C3AED; }

        .kpi-top-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .kpi-label-text {
            color: #475569;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.07em;
        }
        .kpi-icon-badge {
            font-size: 1.15rem;
            background: #F1F5F9;
            border-radius: 8px;
            padding: 4px 8px;
            border: 1px solid #E2E8F0;
        }
        .kpi-val-number {
            color: #0F172A;
            font-size: 2.05rem;
            font-weight: 900;
            font-family: 'Outfit', sans-serif;
            letter-spacing: -0.03em;
            line-height: 1.15;
            margin: 4px 0 8px 0;
        }
        .kpi-sub-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.80rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
        }
        .kpi-sub-gold {
            color: #B45309;
            background: #FEF3C7;
            border: 1px solid #FDE68A;
        }
        .kpi-sub-green {
            color: #065F46;
            background: #D1FAE5;
            border: 1px solid #A7F3D0;
        }
        .kpi-sub-blue {
            color: #1E40AF;
            background: #DBEAFE;
            border: 1px solid #BFDBFE;
        }
        .kpi-sub-purple {
            color: #5B21B6;
            background: #EDE9FE;
            border: 1px solid #DDD6FE;
        }

        /* =========================================================================
           6. ONGLETS STREAMLIT (SEGMENT CONTROL CLAIR & CONTRASTÉ)
           ========================================================================= */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: #FFFFFF;
            padding: 8px;
            border-radius: 16px;
            border: 1px solid #CBD5E1;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .stTabs [data-baseweb="tab"] {
            height: 48px;
            border-radius: 11px;
            color: #475569;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.94rem;
            padding: 0 18px;
            border: 1px solid transparent;
            transition: all 0.20s ease-in-out;
            background: transparent;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #0F172A;
            background: #F1F5F9;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%) !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            border-color: #D97706 !important;
            box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35) !important;
        }

        /* =========================================================================
           7. CARTES DE RECOMMANDATIONS & CONSEILS STRATÉGIQUES
           ========================================================================= */
        .reco-card-luxury {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 5px solid #D97706;
            border-radius: 0 16px 16px 0;
            padding: 20px 24px;
            margin-bottom: 16px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
            transition: all 0.25s ease;
        }
        .reco-card-luxury:hover {
            transform: translateX(4px);
            border-left-color: #059669;
            border-color: #CBD5E1;
        }
        .reco-card-title {
            color: #0F172A;
            font-size: 1.08rem;
            font-weight: 800;
            font-family: 'Outfit', sans-serif;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .reco-card-body {
            color: #334155;
            font-size: 0.95rem;
            line-height: 1.65;
            margin: 0;
        }

        /* =========================================================================
           8. VERDICT BOX & RÉSULTATS DU SIMULATEUR
           ========================================================================= */
        .verdict-box-luxury {
            border-radius: 16px;
            padding: 24px 28px;
            margin: 18px 0;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .verdict-hit-glow {
            background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
            border: 2px solid #059669;
        }
        .verdict-standard-glow {
            background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
            border: 2px solid #2563EB;
        }
        .verdict-status-title {
            font-size: 0.80rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #065F46;
        }
        .verdict-main-headline {
            font-size: 1.50rem;
            font-weight: 900;
            font-family: 'Outfit', sans-serif;
            color: #0F172A;
            margin: 4px 0 6px 0;
        }
        .verdict-sub-archetype {
            font-size: 0.92rem;
            color: #334155;
            font-weight: 600;
        }

        /* =========================================================================
           9. DUEL A/B TESTING CARDS
           ========================================================================= */
        .ab-summary-card {
            background: #FFFFFF;
            border: 2px solid #D97706;
            border-radius: 18px;
            padding: 24px;
            box-shadow: 0 8px 24px rgba(217, 119, 6, 0.12);
            text-align: center;
            margin-top: 18px;
        }
        .ab-winner-pill {
            display: inline-block;
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            color: #FFFFFF;
            font-weight: 800;
            font-size: 0.88rem;
            padding: 6px 20px;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 12px;
            box-shadow: 0 4px 12px rgba(5, 150, 105, 0.25);
        }

        /* =========================================================================
           10. SIDEBAR STYLISÉE & FORMULAIRES
           ========================================================================= */
        section[data-testid="stSidebar"] {
            background: #FFFFFF !important;
            border-right: 1px solid #E2E8F0;
        }
        section[data-testid="stSidebar"] .stSelectbox label, 
        section[data-testid="stSidebar"] .stSlider label {
            color: #0F172A !important;
            font-size: 0.88rem !important;
            font-weight: 700 !important;
        }

        div[data-testid="stForm"] {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 18px;
            padding: 26px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.05);
        }

        .stButton>button {
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
            color: #FFFFFF !important;
            font-weight: 800;
            font-family: 'Outfit', sans-serif;
            font-size: 1.02rem;
            border: none;
            border-radius: 12px;
            padding: 12px 26px;
            transition: all 0.25s ease;
            box-shadow: 0 4px 14px rgba(217, 119, 6, 0.30);
            letter-spacing: -0.01em;
            width: 100%;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.01);
            box-shadow: 0 8px 22px rgba(217, 119, 6, 0.45);
        }

        /* =========================================================================
           11. FOOTER INSTITUTIONNEL HAUTE PRÉCISION
           ========================================================================= */
        .footer-luxury {
            margin-top: 55px;
            padding-top: 24px;
            border-top: 2px solid #E2E8F0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
            color: #64748B;
            font-size: 0.85rem;
        }
        .footer-left-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #0F172A;
            font-weight: 700;
        }
        .footer-badges {
            display: flex;
            gap: 10px;
        }
        .footer-pill {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            padding: 4px 12px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: #334155;
            font-weight: 600;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def render_hero_banner() -> None:
    """Affiche la bannière Hero haut de gamme en mode clair lumineux."""
    st.markdown(
        """
        <div class="hero-banner-luminous">
            <div class="hero-top-pill">
                <span class="pulse-dot"></span>
                <span>OBSERVATOIRE NATIONAL • RÉPUBLIQUE DU SÉNÉGAL • SPRINT 6</span>
            </div>
            <div class="hero-title-main">
                <span style="font-size: 2.3rem;">🇸🇳</span>
                <span class="gradient-gold">Plateforme d'Intelligence Audiovisuelle</span>
            </div>
            <div class="hero-desc">
                Analyse avancée de 15 832 productions audiovisuelles certifiées (EvenProd, Marodi TV, Pikini Production). 
                Cartographie comportementale du public sénégalais, analyse des sentiments des spectateurs, simulateur d'audience pré-publication et moteur MLOps hybride.
            </div>
            <div class="hero-chips-container">
                <div class="hero-chip">📦 Moteur : <b>RandomForest & HistGBoost</b></div>
                <div class="hero-chip">🎯 R² Régression : <b>0.8006</b></div>
                <div class="hero-chip">🔥 AUC Hit Predictor : <b>0.9871</b></div>
                <div class="hero-chip">💬 Analyse Sentiments : <b>NLP Hybride (FR/Wolof)</b></div>
                <div class="hero-chip">🏛️ Entrepôt : <b>DuckDB Gold Lakehouse</b></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(number: str, title: str, subtitle: str) -> None:
    """Affiche un en-tête de section structuré et contrasté."""
    st.markdown(
        f"""
        <div class="section-header-box">
            <div class="section-title-wrap">
                <span class="section-number-pill">{number}</span>
                <div>
                    <h3 class="section-title-text">{title}</h3>
                    <div class="section-subtitle-text">{subtitle}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    label: str,
    value: str,
    sub_text: str,
    icon: str = "📊",
    theme: str = "gold",
) -> None:
    """Génère une carte métrique KPI lumineuse avec bordure colorée et typographie contrastée."""
    theme_card_class = f"kpi-card-{theme}" if theme != "gold" else ""
    theme_sub_class = f"kpi-sub-{theme}"
    st.markdown(
        f"""
        <div class="kpi-card-luxury {theme_card_class}">
            <div class="kpi-top-row">
                <span class="kpi-label-text">{label}</span>
                <span class="kpi-icon-badge">{icon}</span>
            </div>
            <div class="kpi-val-number">{value}</div>
            <div>
                <span class="kpi-sub-badge {theme_sub_class}">{sub_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_strategic_card(title: str, text: str, icon: str = "💡") -> None:
    """Affiche une carte de recommandation stratégique éditoriale."""
    st.markdown(
        f"""
        <div class="reco-card-luxury">
            <div class="reco-card-title">
                <span>{icon}</span>
                <span>{title}</span>
            </div>
            <div class="reco-card-body">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Affiche le pied de page moderne certifié."""
    st.markdown(
        """
        <div class="footer-luxury">
            <div class="footer-left-brand">
                <span>🇸🇳</span>
                <span>Plateforme d'Intelligence Audiovisuelle Sénégalaise • Direction des Études & MLOps</span>
            </div>
            <div class="footer-badges">
                <span class="footer-pill">Sprint 6</span>
                <span class="footer-pill">DuckDB v2.0</span>
                <span class="footer-pill">Scikit-Learn 1.9</span>
                <span class="footer-pill">Streamlit 1.66</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
