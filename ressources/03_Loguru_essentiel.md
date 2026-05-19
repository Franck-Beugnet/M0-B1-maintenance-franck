# Loguru — Mini-cours

> Brief associé : M0-B1
> Durée de lecture + pratique : ~30 min
> Pré-requis : Python 3.11+, env virtuel actif avec `loguru` installé.

## Pourquoi cette techno ?

Tout service en production **doit** journaliser ce qu'il fait. Sinon :

- impossible de débugger une erreur signalée hier ;
- impossible de mesurer les performances ;
- impossible de prouver à un audit qui a fait quoi.

Le module `logging` de la stdlib Python existe pour ça, mais il a un défaut :
**il faut beaucoup de configuration boilerplate** pour des fonctions de base
(rotation, format, couleurs).

**Loguru** est l'alternative moderne, simple par défaut. Une seule ligne pour
logger, configuration prête à l'emploi pour les usages pro (rotation, retention,
compression).

**Alternatives à connaître :**

| Outil | Position |
|---|---|
| **`logging` (stdlib)** | Très flexible, mais verbeux. Standard quand on impose stdlib only. |
| **structlog** | Logs structurés (JSON), excellent pour pipeline ELK / Grafana Loki. Plus complexe. |
| **picologging** | Drop-in replacement performant de stdlib. Niche. |

Sur ce parcours, **Loguru est imposé** (cf. CLAUDE.md §8). C'est notre standard.

## Concepts clés

- **Le `logger` global** : importé depuis `loguru`, partagé dans toute
  l'application. Pas besoin de l'instancier comme avec `logging.getLogger()`.
- **Niveaux standards** : `DEBUG` (verbeux), `INFO` (déroulé normal),
  `WARNING` (recoverable), `ERROR` (échec localisé), `CRITICAL` (service mort).
- **Sinks** : un sink = un endroit où vont les logs (console, fichier, fonction
  callback). On les ajoute via `logger.add(...)`.
- **Rotation** : redécoupe le fichier quand il atteint une taille (`"10 MB"`)
  ou un délai (`"1 day"`).
- **Retention** : durée de conservation des fichiers archivés (`"30 days"`).
- **Compression** : compresse automatiquement les fichiers archivés
  (`compression="zip"` ou `"gz"`).
- **`@logger.catch`** : décorateur qui logge automatiquement n'importe quelle
  exception remontée par la fonction décorée. Très pratique sur un endpoint API.

## Exemple minimal qui tourne

```python
# Versions testées : python 3.11+, loguru 0.7+
from loguru import logger

# 1. Sortie console : déjà active par défaut, formatée et colorée
logger.info("Démarrage du service")
logger.warning("Attention, cache vide")
logger.error("Échec de l'appel externe")

# 2. Ajouter un fichier de logs avec rotation, retention, compression
logger.add(
    "logs/api.log",
    rotation="10 MB",        # nouveau fichier dès que 10 Mo atteints
    retention="30 days",     # garde 30 jours d'historique
    compression="zip",       # compresse les fichiers archivés
    level="INFO",            # ne logge pas les DEBUG dans ce fichier
)

# 3. Logger une exception proprement
try:
    1 / 0
except ZeroDivisionError:
    logger.exception("Calcul impossible")  # logge avec stacktrace complet

# 4. Décorateur @logger.catch : capture toute exception non gérée
@logger.catch
def predire(data: dict) -> str:
    if not data:
        raise ValueError("data vide")
    return "ok"

predire({})   # ValueError logguée automatiquement, pas besoin de try/except
```

Lance le script. Tu vois :

- la console affiche les messages colorés ;
- un dossier `logs/` apparaît avec `api.log` ;
- au bout de 10 Mo (ou en testant manuellement), un fichier daté apparaît.

## Exercice guidé

Sur le squelette **M0-B1**, ajoute le logging Loguru à l'endpoint `/predict` que
tu as implémenté dans le mini-cours FastAPI.

**Cherche par toi-même** en t'appuyant sur les *Concepts clés* et l'*Exemple
minimal* (étapes 1-2 du script ci-dessus). La solution est masquée plus bas — à
révéler seulement après ta tentative.

**Tâches :**

1. Dans `app/main.py`, en début de fichier, configurer un **sink fichier**
   pointant vers `logs/api.log` avec rotation `"5 MB"`, retention `"7 days"`,
   compression `"zip"`, niveau `INFO`, et `enqueue=True` (safe pour contextes
   async / multi-thread). Penser à créer le dossier `logs/` via `pathlib`.
2. Logger en `INFO` **avant** la prédiction (avec le payload reçu via
   `item.model_dump()`).
3. Logger en `INFO` **après** la prédiction, avec **la durée mesurée**
   (`time.perf_counter()` avant/après l'appel modèle, conversion en ms).
4. Ajouter `logs/` à `.gitignore` (si pas déjà fait).
5. Lancer 5 requêtes à `/predict` (Swagger ou curl) et vérifier que
   `logs/api.log` se remplit.

✅ **Résultat attendu** :
- console colorée pendant le run d'uvicorn ;
- fichier `logs/api.log` avec une ligne INFO par requête ;
- pas de log de niveau DEBUG (sauf si tu as changé le niveau) ;
- les durées de prédiction visibles.

<details>
<summary>🔒 <strong>Solution</strong> — clique pour révéler (après avoir cherché)</summary>

```python
# en début de app/main.py
from pathlib import Path
from loguru import logger

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "api.log",
    rotation="5 MB",
    retention="7 days",
    compression="zip",
    level="INFO",
    enqueue=True,            # safe pour les contextes async / multi-thread
)
```

```python
# dans la route /predict
import time

logger.info(f"Requête /predict reçue : {item.model_dump()}")

t0 = time.perf_counter()
# ... appel modèle ...
duree_ms = (time.perf_counter() - t0) * 1000
logger.info(f"Prédiction = {classe} (durée {duree_ms:.1f} ms)")
```

</details>

⭐ **Bonus** : utiliser un format JSON pour les logs fichier (utile en M5 si tu
ingères les logs dans Grafana Loki). Indice : Loguru accepte une fonction
de formatage personnalisée passée au paramètre `format=`. La fonction
reçoit un `record` (dict) et doit retourner une string.

<details><summary>▶ Voir une solution possible</summary>

```python
def json_formatter(record):
    import json
    return json.dumps({
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "msg": record["message"],
        "module": record["name"],
    }) + "\n"

logger.add("logs/api.jsonl", format=json_formatter, rotation="5 MB")
```

</details>

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Oublier `enqueue=True` en contexte async / multi-thread | Corruption / interleaving des logs sous charge. |
| Oublier `logs/` dans `.gitignore` | Fichiers de logs commités (potentiellement plusieurs Mo, parfois secrets). |
| Logger des **secrets / PII** dans les messages (tokens, mots de passe, données perso) | Fuite de données dans les logs archivés. |
| Utiliser un seul niveau global (pas de niveau par sink) | DEBUG flood le fichier de prod, ou INFO masque les `WARNING` critiques. |
| Appeler `logger.exception(...)` **hors** d'un `except` actif | Pas de stack trace capturé → devient un `logger.error` standard sans le contexte. |
| Rotation trop fréquente (`"1 KB"`) | Centaines de fichiers archivés, outils d'analyse cassés. |

**Symptôme → cause probable**

| Symptôme | Cause probable |
|---|---|
| Logs entrelacés / corrompus sous charge | `enqueue=True` oublié dans `logger.add(...)` |
| `logger.exception` n'affiche pas la stack trace | Appelé hors d'un bloc `except` actif |
| Fichier `api.log` commité par erreur | `logs/` pas dans `.gitignore` |
| Le fichier de prod ne contient que des DEBUG inutiles | Pas de `level="INFO"` sur le sink fichier |
| 200 fichiers `api.log.YYYY-MM-DD.zip` en 1 journée | Rotation trop agressive (passer à `"10 MB"` ou `"1 day"`) |

## Pour aller plus loin

- **Doc officielle Loguru** : <https://loguru.readthedocs.io/>
- **Référence legacy OPCO ATLAS** (partie « Loguru » : rotation, retention,
  compression, exemple complet d'API sur 1 page) : disponible **à la demande
  via Discord** auprès de la formatrice. Bon complément pour le détail de
  chaque option.
- **Comparaison Loguru vs logging stdlib** :
  <https://github.com/Delgan/loguru#features>

⭐ **Pour M5** (déploiement/monitoring), on enverra ces logs dans un
collector (Loki, Elasticsearch). Le format JSON cité plus haut sera précieux à
ce moment-là.

## Vérification (checklist apprenant)

- [ ] Mon endpoint `/predict` logge une ligne INFO avant chaque appel modèle.
- [ ] Mon endpoint logge une ligne INFO après, avec le résultat et la durée en ms.
- [ ] Le dossier `logs/` est créé automatiquement.
- [ ] `logs/` est dans mon `.gitignore`.
- [ ] La rotation est configurée (j'ai testé en regénérant 5+ Mo de logs).
- [ ] Je sais expliquer en 1 minute la différence **DEBUG / INFO / WARNING / ERROR**.
- [ ] Je sais ce que fait `enqueue=True` (thread-safe, indispensable en API).