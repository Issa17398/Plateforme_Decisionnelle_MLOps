# Note de Conformité Juridique et Technique — YouTube Data API v3

**Projet :** Sénégal Audiovisual Intelligence Platform  
**Date d'évaluation :** Octobre 2026  
**Statut :** Mode Audit en lecture seule (Aucune persistance de données sans conformité validée)

---

## 1. Introduction et Périmètre

Ce document analyse les exigences légales et contractuelles imposées par Google et YouTube pour l'utilisation de **YouTube Data API v3**.  
Dans le cadre de l'ingénierie des données pour l'analyse audiovisuelle sénégalaise (chaînes cibles initiales : *Marodi TV*, *EvenProd*, *Pikini Production*), le respect strict de ces règles conditionne directement l'architecture logicielle.

**Règle d'or :** L'accès public via une API ne confère aucun droit automatique de copie massive, de stockage illimité ou de commercialisation des données brutes.

---

## 2. Sources Officielles de Référence

1. **YouTube Developer Policies :**  
   [https://developers.google.com/youtube/terms/developer-policies](https://developers.google.com/youtube/terms/developer-policies)
2. **YouTube Terms of Service :**  
   [https://www.youtube.com/t/terms](https://www.youtube.com/t/terms)
3. **Google APIs Terms of Service :**  
   [https://developers.google.com/terms](https://developers.google.com/terms)
4. **Documentation API v3 :**  
   - `channels.list` : [https://developers.google.com/youtube/v3/docs/channels/list](https://developers.google.com/youtube/v3/docs/channels/list)
   - `playlistItems.list` : [https://developers.google.com/youtube/v3/docs/playlistItems/list](https://developers.google.com/youtube/v3/docs/playlistItems/list)
   - `videos.list` : [https://developers.google.com/youtube/v3/docs/videos/list](https://developers.google.com/youtube/v3/docs/videos/list)
   - `commentThreads.list` : [https://developers.google.com/youtube/v3/docs/commentThreads/list](https://developers.google.com/youtube/v3/docs/commentThreads/list)

---

## 3. Analyse des Règles Clés et Impacts Architecturaux

### A. Quotas et Gestion des Ressources
* **Règle :** Chaque projet Google Cloud dispose par défaut d'une allocation gratuite de **10 000 unités de quota par jour** (remise à zéro à minuit heure du Pacifique).
* **Coût unitaire des endpoints :**
  - `channels.list` : 1 unité
  - `playlistItems.list` : 1 unité
  - `videos.list` : 1 unité
  - `commentThreads.list` : 1 unité
  - `search.list` : **100 unités** (à proscrire pour notre usage régulier).
* **Conséquence d'architecture :**  
  Pour lister les vidéos d'une chaîne, **ne jamais utiliser `search.list`**. L'architecture doit interroger `channels.list` avec la partie `contentDetails` pour extraire l'identifiant de la playlist automatique des vidéos mises en ligne (`relatedPlaylists.uploads`), puis paginer sur `playlistItems.list`. Cette méthode consomme **100 fois moins de quota**.

### B. Durée de Conservation, Rafraîchissement et Suppression (Section III.E)
* **Règle :**  
  - Le stockage ou la mise en cache de données API n'est autorisé que de manière temporaire pour des besoins opérationnels directs.
  - La politique YouTube impose que les données mises en cache ne soient **pas conservées plus de 30 jours** sans être rafraîchies ou supprimées.
  - Si un créateur supprime, modifie ou rend privée une vidéo sur YouTube, l'application tierce doit obligatoirement refléter cette suppression ou modification.
* **Conséquence d'architecture :**  
  - **Phase 1 (Actuelle) :** Mode audit 100% volatile en mémoire (aucune écriture disque permanente).
  - **Phase ultérieure :** Tout système de stockage futur devra comporter une politique de rétention (TTL <= 30 jours) et un mécanisme d'invalidation/mise à jour périodique.

### C. Agrégation Inter-Chaînes (Cross-Channel Data)
* **Règle :**  
  Les règles YouTube interdisent d'utiliser les données de l'API pour tenter de reconstituer des informations privées ou sensibles de créateurs tiers sans leur accord. La comparaison publique de statistiques publiques (vues publiques, nombre d'abonnés arrondi fourni par l'API) est admise tant qu'elle ne dénigre pas, ne contourne pas les droits d'auteur et ne monétise pas les données brutes.
* **Conséquence d'architecture :**  
  Seules les métriques publiques officielles fournies par l'API sont inspectées. Aucune tentative d'inférence de métriques privées (revenus YouTube Analytics, données démographiques privées) n'est autorisée.

### D. Commentaires et Données Personnelles (PII)
* **Règle :**  
  Les commentaires d'utilisateurs contiennent des données à caractère personnel (noms affichés, photos de profil, identifiants de comptes Google/YouTube). Le Règlement Général sur la Protection des Données (RGPD / législation sénégalaise CDP) et les Developer Policies encadrent strictement le profilage d'individus.
* **Conséquence d'architecture :**  
  **Les commentaires (`commentThreads.list`) sont expressément EXCLUS du périmètre de cette première version.** Aucun traitement de données nominatives n'est réalisé.

### E. Interdictions Absolues
1. **Téléchargement de médias :** Interdiction totale de télécharger, sauvegarder ou ré-héberger les flux audio ou vidéo de YouTube (Section II.A des ToS).
2. **Scraping web :** Interdiction d'utiliser des scrapers HTML (BeautifulSoup, Selenium, Playwright, requêtes HTTP directes sur `youtube.com`) pour contourner l'API. Seule l'API officielle v3 avec clé d'authentification valide est autorisée.
3. **Divulgation de clés :** Les clés d'API ne doivent jamais être exposées dans des dépôts publics, dans les logs ou dans des commits Git.

---

## 4. Synthèse des Décisions pour l'Étape Initiale

| Sujet | Statut | Règle Opérationnelle |
|---|---|---|
| **Collecte Vidéo/Audio** | ❌ Interdit | Aucune extraction de flux multimédia. Uniquement les métadonnées de l'API. |
| **Scraping HTML** | ❌ Interdit | Utilisation exclusive de `requests` ciblant `https://www.googleapis.com/youtube/v3/`. |
| **Commentaires** | ⏸️ Ajourné | Endpoint exclu en phase 1 pour protéger la conformité PII. |
| **Stockage Permanent** | ⏸️ Suspendu | Mode audit volatile en mémoire. Dossier `data/raw/` vide pour le moment. |
| **Gestion du Quota** | ✅ Optimisé | Utilisation de la playlist `uploads` (coût 1 unité) au lieu de `search.list` (100 unités). |
| **Sécurité des Clés** | ✅ Sécurisé | Fichier `.env` masqué dans `.gitignore` et clés masquées dans les journaux d'exécution. |

---

*Document approuvé pour l'exécution de l'audit technique de configuration.*
