# ==============================================================================
# Dockerfile personnalisé pour l'orchestration Airflow (Sprint 4)
# Projet : Sénégal Audiovisual Intelligence Platform
# ==============================================================================

FROM apache/airflow:2.10.4-python3.11

LABEL maintainer="Senegal Data Engineering Team"
LABEL description="Image Airflow personnalisée avec DuckDB, dbt-duckdb, PyArrow et ReportLab"

USER root

# Installation des outils de compilation et utilitaires de base
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copie des dépendances du projet et installation dans l'environnement virtuel Airflow
COPY --chown=airflow:root requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /requirements.txt

# Définition du répertoire de travail
WORKDIR /opt/airflow
