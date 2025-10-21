# Cutover — Mode d'emploi rapide (staging)

## 1) Préparer le truth-set
- Copier l'échantillon:
```
cp docs/examples/truthset.sample.json artifacts/truthset.json
```

## 2) Lancer une évaluation ponctuelle
```
python scripts/cutover_metrics.py \
  --truth-set artifacts/truthset.json \
  --k 10 \
  --out artifacts/cutover_$(date +%F-%H).json

echo $?
```
- Exit 0 si agreement@5 ≥ 0.95 ET nDCG@10 ≥ 0.90 (override possible via `--min-*`).
- Append automatique dans `artifacts/cutover_log.ndjson`.

## 3) Horaire (48h)
Ajouter une GitHub Action cron (staging) toutes les heures:
- Exécuter `scripts/cutover_metrics.py` avec le truth-set figé.
- Conserver `artifacts/cutover_log.ndjson` en artefact.
- Si seuils non atteints → échec du job (visibilité immédiate).

## 4) Interpréter les scores
- agreement@5 proche de 1 → overlap fort entre baseline et cible sur le top-5.
- nDCG@10 proche de 1 → ordres alignés (pondération logarithmique des positions).
- Action: attendre 48h de stabilité > seuils avant un cutover.

## 5) (Optionnel) Générer un sample baseline
```
python scripts/make_truthset_sample.py
```
- Remplacer `faiss_topk()` par un appel réel en staging si besoin.

> NB: `artifacts/truthset.json` doit être présent sur la branche staging (copie du sample ou un truth-set “réel” figé). Ne mets pas de PII dans le truth-set. Pour la vraie bascule, fige un baseline obtenu “live” en staging et versionne-le (ex: `truthset.baseline.YYYY-MM-DD.json`).
