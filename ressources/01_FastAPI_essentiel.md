# FastAPI — Mini-cours

> Brief associé : M0-B1
> Durée de lecture + pratique : ~45 min
> Pré-requis : Python 3.11+, environnement virtuel actif (cf. P0).

## Pourquoi cette techno ?

**FastAPI** est le framework Python moderne pour exposer un service HTTP. Il
combine trois choses qui faisaient défaut à Flask :

- **validation automatique** des entrées et sorties via Pydantic ;
- **documentation Swagger / OpenAPI gratuite** sur `/docs` ;
- **performance native** (basé sur Starlette + Uvicorn, async-ready).

**Alternatives à connaître :**

| Framework | Quand l'utiliser ?                                                                                                                                                                                                              |
|---|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Flask** | Existe depuis 2010, encore largement utilisé. Pas de validation native, pas de Swagger auto. FastAPI est généralement préférable aujourd’hui pour un nouveau service ML grâce au typage, à la validation et à OpenAPI intégrés. |
| **Django REST** | Lourd, orienté CRUD applicatif riche. Ne pas utiliser si c'est juste pour exposer un modèle.                                                                                                                                    |
| **Starlette** | Le moteur sous FastAPI. Plus bas niveau. À utiliser si on veut tout contrôler.                                                                                                                                                  |
| **Litestar** | Concurrent récent de FastAPI, très bien aussi. Communauté plus petite.                                                                                                                                                          |

Sur ce parcours, **FastAPI est le standard** pour M0 → M5 (intégration, déploiement,
MLOps). C'est aussi ce que demande explicitement le sujet certif janvier 2026.

## Concepts clés

- **`FastAPI()`** : l'application = collection de routes. Une route = un point
  d'entrée HTTP.
- **Décorateurs de route** : `@app.get(...)`, `@app.post(...)`, `@app.put(...)`,
  `@app.delete(...)`. La fonction décorée reçoit les paramètres validés.
- **Pydantic `BaseModel`** : déclare le schéma d'entrée / sortie. FastAPI valide
  automatiquement les requêtes contre ce schéma. 422 déclenché automatiquement par FastAPI lors d’une erreur de validation Pydantic..
- **`response_model=...`** : impose un schéma de sortie, documenté dans Swagger.
- **`lifespan`** : gère ce qui se passe **au démarrage** (charger un modèle ML)
  et **à l'arrêt** (libérer une ressource). Remplace les anciens `@app.on_event`
  *deprecated*.
- **`HTTPException`** : lever une erreur HTTP propre depuis le code (`raise
  HTTPException(status_code=404, detail="Note introuvable")`).
- **`uvicorn`** : le serveur ASGI qui exécute l'application. En dev : `uvicorn
  app.main:app --reload` ; en prod : sans `--reload`, derrière un reverse proxy.

### Rappel scikit-learn (pour intégrer un modèle déjà entraîné)

Quand un modèle scikit-learn est chargé via `joblib.load(...)`, tu as 3 méthodes
utiles pour le servir derrière une API :

- **`model.predict(X)`** → renvoie un tableau de **classes prédites** (la plus
  probable pour chaque ligne de `X`). Ex : `array(['haute'])`.
- **`model.predict_proba(X)`** → renvoie une **matrice de probabilités**, une
  ligne par exemple, une colonne par classe. Ex : `array([[0.1, 0.2, 0.7]])`.
- **`model.classes_`** → l'**ordre des classes** correspondant aux colonnes de
  `predict_proba`. Ex : `array(['basse', 'moyenne', 'haute'])`.

L'entrée `X` doit être un **DataFrame pandas** (ou array 2D) avec les mêmes
colonnes que celles vues à l'entraînement. Pour un seul exemple :
`pd.DataFrame([item.model_dump()])`.

## Exemple minimal qui tourne

```python
# app/main.py — versions testées : python 3.11+, fastapi 0.115+, pydantic 2.10+
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class Note(BaseModel):
    titre: str
    contenu: str


state: dict[str, Any] = {} # Ici on utilise un dict global simplifié pour le cours. En production on préférera souvent app.state ou une couche de dépendances.


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["notes"] = []          # « base de données » en mémoire
    yield
    state.clear()


app = FastAPI(title="API Notes", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/notes", response_model=Note, status_code=201)
def creer_note(note: Note) -> Note:
    state["notes"].append(note)
    return note


@app.get("/notes/{idx}", response_model=Note)
def lire_note(idx: int) -> Note:
    notes = state["notes"]
    if idx < 0 or idx >= len(notes):
        raise HTTPException(404, "Note introuvable")
    return notes[idx]
```

Lance :

```bash
uvicorn app.main:app --reload
```

Ouvre <http://localhost:8000/docs> → **interface Swagger interactive**, tu
peux tester `/health`, `POST /notes`, `GET /notes/0` directement.

## Exercice guidé

Tu es sur le squelette **M0-B1**. L'endpoint `/predict` renvoie actuellement une
erreur 501. **Implémente-le.**

**Cherche par toi-même** en t'appuyant sur la section *Concepts clés* (en
particulier le **rappel scikit-learn** ci-dessus) et l'*Exemple minimal*. La
solution est masquée plus bas — à révéler seulement après ta tentative.

**Étapes attendues dans `app/main.py`** :

1. Récupérer le modèle depuis `state` (lever `HTTPException(503)` si absent).
2. Construire un **DataFrame pandas** à partir de l'item Pydantic
   (`item.model_dump()`).
3. Appeler `.predict()` et `.predict_proba()` sur le modèle (cf. *Rappel
   scikit-learn*).
4. Construire un `dict {classe: proba}` en zippant `model.classes_` et les
   probabilités.
5. Logger l'événement (`loguru.logger.info`).
6. Retourner une réponse typée `PredictionResponse(criticite=..., probabilites=...)`.

✅ **Résultat attendu** : un POST `/predict` avec un payload JSON valide doit
retourner `200` + `{"criticite": "...", "probabilites": {...}}`. Un payload
invalide doit retourner `422`.

<details>
<summary>🔒 <strong>Solution</strong> — clique pour révéler (après avoir cherché)</summary>

```python
import pandas as pd
from fastapi import HTTPException
from loguru import logger

@app.post("/predict", response_model=PredictionResponse)
def predict(item: MachineInput) -> PredictionResponse:
    # 1. Charger le modèle depuis state
    model = state.get("model")
    if model is None:
        raise HTTPException(503, "Modèle non chargé")

    # 2. Construire un DataFrame à partir de l'item
    df = pd.DataFrame([item.model_dump()])

    # 3. Prédire la classe et les probabilités
    classe = str(model.predict(df)[0])
    probas = model.predict_proba(df)[0]
    classes = model.classes_

    # 4. Construire le dict {classe: proba}
    proba_dict = {str(c): float(p) for c, p in zip(classes, probas)}

    # 5. Logger l'événement
    logger.info(f"Prédiction : {classe} (entrée={item.model_dump()})")

    # 6. Retourner la réponse typée
    return PredictionResponse(criticite=classe, probabilites=proba_dict)
```

</details>

Test depuis ton terminal :

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "type_machine": "compresseur",
    "age_machine_jours": 1500,
    "derniere_maintenance_jours": 45,
    "temperature_moyenne": 68.5,
    "vibration_moyenne": 3.2,
    "pression_moyenne": 7.8,
    "nb_incidents_3_mois": 2
  }'
```

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Oublier `with TestClient(app) as client:` dans les tests | Le `lifespan` ne s'exécute pas → le modèle n'est pas chargé → `model_loaded:false`. |
| Oublier `response_model=...` sur une route | Pas de validation de la sortie, Swagger incomplet, peut leak des champs internes. |
| Utiliser `.dict()` (Pydantic v1) au lieu de `.model_dump()` (v2) | `AttributeError: 'BaseModel' object has no attribute 'dict'` (ou DeprecationWarning). |
| Confondre `@app.get` et `@app.post` | Erreur `405 Method Not Allowed` ou `404 Not Found`. |
| Mélanger `def` et `async def` sans comprendre pourquoi | Soit `async def` qui bloque tout l'event loop sur un appel sync, soit `def` qui sérialise les requêtes inutilement. |
| Lever 400 alors que c'est une validation Pydantic | **422** = validation auto (champ manquant, type invalide) ; **400** = erreur métier que **tu** lèves via `HTTPException(400, ...)`. Ne pas mélanger. |

**Symptôme → cause probable**

| Symptôme | Cause probable |
|---|---|
| `model_loaded:false` dans les tests | `TestClient` utilisé sans `with` → lifespan pas déclenché |
| `AttributeError: ... has no attribute 'dict'` | Migration Pydantic v2 oubliée → utiliser `.model_dump()` |
| Swagger n'affiche pas le schéma de réponse | `response_model=...` oublié sur la route |
| 405 Method Not Allowed | Mauvais décorateur (`@app.get` au lieu de `@app.post`) |
| `/predict` renvoie 422 sans raison apparente | Validation Pydantic échouée — regarde le `detail` JSON, il pointe le champ fautif |

## Pour aller plus loin

- **Doc officielle** : <https://fastapi.tiangolo.com/>
- **Tutoriel pas à pas** : <https://fastapi.tiangolo.com/tutorial/>
- **Référence legacy OPCO ATLAS** (CRUD complet GET/POST/PUT/DELETE sur une
  API de citations + intégration Streamlit) : disponible **à la demande via
  Discord** auprès de la formatrice. Utile si tu veux voir un exemple plus
  large que `/health` + `/predict`.
- **Livre** : *Building Data Science Applications with FastAPI* (Packt, 2023) —
  ressource complémentaire fournie par la formatrice. Référence pour la suite
  du parcours (M5 monitoring, M6 amélioration).

⭐ **Bonus** : explorer la dependency injection (`Depends(...)`) pour
authentification, base de données partagée. Pas obligatoire pour M0-B1.

## Vérification (checklist apprenant)

- [ ] Mon API répond 200 sur `GET /health`.
- [ ] J'ai implémenté `POST /predict` qui retourne la classe + les probabilités.
- [ ] L'interface Swagger `/docs` affiche bien mes deux endpoints avec leur schéma.
- [ ] Une entrée invalide renvoie bien 422 sans que j'écrive de code spécifique.
- [ ] Je sais expliquer en 2 minutes la différence entre **FastAPI et Flask**.
- [ ] Je sais expliquer ce que fait le `lifespan` et pourquoi il est utile pour un service ML.