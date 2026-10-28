"""Package MLOps pour la plateforme audiovisuelle sénégalaise (Sprint 5).

Composants principaux :
- features : Extraction DuckDB Gold, ingénierie de variables, clustering K-Means et préprocesseurs.
- train : Entraînement multi-modèles (Régression & Classification) avec suivi MLflow.
- evaluate : Évaluation des métriques ($R^2$, RMSE, ROC-AUC, F1-Score) et génération des graphiques.
- predict : Service d'inférence combinée pour l'estimation d'audience et de hit viral.
"""

__version__ = "1.0.0"
