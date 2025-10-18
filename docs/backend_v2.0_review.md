# Backend v2.0 – “Core Loop” Fonctionnel
📅 18 octobre 2025 | 🟢 **Statut : Approuvé – Lancement Phase 2**

---

## 1. Synthèse Exécutive

Cette version marque un tournant : le backend passe d’un squelette d’API à un **MVP complet de la Phase 1 (“Core Loop”)**, en alignement total avec la vision produit.  
Deux fondations structurantes sont désormais en place :  

- un **moteur astro interne (pyswisseph)**, garantissant notre souveraineté algorithmique ;  
- une **heuristique “Aujourd’hui”** intégrant notre gestion unique de l’incertitude.  

Le socle métier est stable, la dette technique maîtrisée, et le backend est prêt à aborder la **Phase 2 : monétisation et services premium.**

---

## 2. Synthèse Technique

**Robustesse :** Élevée.  
Le moteur interne est déterministe et testé, et la `FakeDeterministicAstroService` assure des tests stables et reproductibles.  
L’injection de dépendances est propre et modulaire.

**Dette Technique :** Faible et circonscrite.  
Les repositories in-memory constituent le seul point critique ; leur migration vers Redis est planifiée (Phase 2).  
→ Aucune dette bloquante.

**Performance :** À instrumenter.  
L’impact CPU de pyswisseph est marginal mais non nul.  
→ Action : instrumenter `/horoscope/today` via Prometheus pour un P95 cible < 1,5 s.

**Qualité :** Maîtrisée.  
CI 100 % verte ; couverture de tests > 82 % sur le domaine métier.  
Codebase : lint et intégration continue sans anomalies.

---

## 3. Évolutions Clés

✅ **Moteur Astro Internalisé** – Suppression de l’API externe ; calculs locaux et logique d’incertitude maîtrisée.  
✅ **Logique Produit Implémentée** – Score 1–5, arbre de décision “Aujourd’hui” et orchestration complète du flux.  
✅ **Contenu Découplé** – `JsonContentRepository` adapté au MVP, indépendant des mises à jour éditoriales.

---

## 4. Risques & Points de Vigilance

| Domaine | Risque | Impact si non traité | Remédiation |
|----------|---------|----------------------|--------------|
| Persistance | Repositories in-memory volatils | Perte de données / sessions multi-instance | Migration Redis (Phase 2) |
| Sécurité | Absence d’authentification et d’entitlements | Exposition publique / blocage de la monétisation | Implémenter JWT + Paywall (Phase 2) |
| Performance | Génération PDF CPU-intensive | Latences / timeouts | Caching + benchmarks avant release (Phase 2) |
| Opérations | Pas de monitoring métrique | Aucune visibilité sur perf ou usage | Intégrer Prometheus / StatsD (Phase 2) |

---

## 5. Matrice de Priorisation – Phase 2

| Domaine | Action | Priorité | Impact | Effort |
|----------|---------|-----------|---------|---------|
| Produit | Auth & Entitlements | 🔴 Haute | 🟢 Très fort | 🧱 Moyen |
| Produit | Génération PDF | 🔴 Haute | 🟢 Très fort | 🧱 Moyen / Élevé |
| Infra | Repositories Redis | 🟡 Moyenne | 🔸 Moyen | ⚙️ Faible |

> Auth & PDF : piliers de la Phase 2.  
> Redis : prérequis de scalabilité.

---

## 6. Plan de Release v0.3.0 (Cible Phase 2)

🎯 **Objectif :** Livrer les fondations de la monétisation et la première fonctionnalité premium.

| Module | Objectif | Indicateur de réussite |
|---------|-----------|------------------------|
| **Auth Service** | Sécuriser l’accès via JWT | > 99,5 % succès login / 0 vulnérabilité critique |
| **Entitlement Service** | Gérer les droits Free / Plus | < 0,1 % erreurs de droits |
| **PDF Service** | Générer le rapport natal | P95 < 20 s / < 1 % erreurs |
| **Redis Repositories** | Assurer la persistance | 0 perte de données post-redémarrage |
| **Monitoring** | Suivre performance & usage | Dashboard Prometheus live (P95, erreurs) |

---

## 7. Décision Finale

Cette version clôt la Phase 1 et confirme la solidité de l’architecture.  
Le socle technique est consolidé, la logique métier maîtrisée et la qualité logicielle sous contrôle.  

**Décision :** Phase 2 validée — objectif v0.3.0 : mise en production des services premium avant fin 2025.  

---

✅ **Document validé pour archivage et diffusion interne.**
