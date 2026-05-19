# Service de criticité maintenance prédictive (M0-B1)

API FastAPI exposant un modèle scikit-learn de classification de criticité d'incidents machine (3 classes : `basse`, `moyenne`, `haute`).

---

## Architecture

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # Application FastAPI (lifespan, routes /health et /predict)
│   └── schemas.py       # Schémas Pydantic (MachineInput, PredictionResponse, HealthResponse)
├── data/
│   ├── generate_dataset.py  # Génération du dataset synthétique
│   └── maintenance_data.csv # Dataset d'entraînement
├── model/
│   ├── model.joblib         # Modèle pré-entraîné (pipeline scikit-learn)
│   └── train_baseline.py    # Script d'entraînement du modèle baseline
├── logs/                    # Logs applicatifs générés à l'exécution
├── tests/
│   ├── __init__.py
│   ├── test_health.py       # Tests fonctionnels de /health
│   └── test_predict.py      # Tests fonctionnels de /predict
├── Dockerfile               # Build multi-stage (builder + image de production)
├── requirements.txt         # Dépendances complètes (dev + prod)
└── requirements-prod.txt    # Dépendances de production uniquement
```

### Routes exposées

| Méthode | Route      | Description                                  |
|---------|------------|----------------------------------------------|
| `GET`   | `/health`  | Santé du service et état du modèle chargé    |
| `POST`  | `/predict` | Prédiction de criticité à partir des features |
| `GET`   | `/docs`    | Documentation interactive (Swagger UI)       |

### Entrée `/predict`

| Champ                      | Type    | Description                                       |
|----------------------------|---------|---------------------------------------------------|
| `type_machine`             | string  | `pompe`, `compresseur`, `convoyeur`, `presse`, `four` |
| `age_machine_jours`        | int     | Âge de la machine en jours (0–10 000)             |
| `derniere_maintenance_jours` | int   | Jours depuis la dernière maintenance (0–365)      |
| `temperature_moyenne`      | float   | Température moyenne sur 7 jours (°C)              |
| `vibration_moyenne`        | float   | Vibration moyenne sur 7 jours (mm/s, ≥ 0)        |
| `pression_moyenne`         | float   | Pression moyenne sur 7 jours (bar, ≥ 0)          |
| `nb_incidents_3_mois`      | int     | Nombre d'incidents sur les 3 derniers mois (≥ 0) |

---

## Installation

### Prérequis

- Python 3.11+
- (optionnel) Docker ou Podman pour le déploiement conteneurisé

### Environnement local

```bash
# Cloner le projet et créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Installer les dépendances
pip install -r requirements.txt
```

---

## Lancement

### En local (développement)

```bash
uvicorn app.main:app --reload
```

L'API est accessible sur [http://localhost:8000](http://localhost:8000).  
La documentation Swagger est disponible sur [http://localhost:8000/docs](http://localhost:8000/docs).

### Avec Docker / Podman

```bash
# Build de l'image
docker build -t fastia-maintenance:dev .

# Lancement du conteneur
docker run --rm -p 8000:8000 fastia-maintenance:dev

# Vérification
curl http://localhost:8000/health
```

### Exemple de requête `/predict`

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

Réponse attendue :

```json
{
  "criticite": "moyenne",
  "probabilites": {
    "basse": 0.12,
    "moyenne": 0.71,
    "haute": 0.17
  }
}
```

---

## Tests

Les tests utilisent `pytest` avec le client de test intégré à FastAPI (`TestClient`).

```bash
# Lancer tous les tests
pytest

# Avec détail des tests
pytest -v

# Avec couverture de code
pytest --cov=app
```

### Fichiers de tests

| Fichier                  | Couverture                                                      |
|--------------------------|-----------------------------------------------------------------|
| `tests/test_health.py`   | Statut 200, schéma de réponse de `/health`                     |
| `tests/test_predict.py`  | Prédiction valide, validation 422 sur entrée invalide, schéma  |

---

## Modèle

Le modèle pré-entraîné (`model/model.joblib`) est un pipeline scikit-learn combinant un `ColumnTransformer` et un `RandomForestClassifier`.

- **Accuracy** : ~80 % en validation croisée stratifiée
- **Classes** : `basse` (majoritaire), `moyenne`, `haute` (sous-représentée ~10 %)

Pour ré-entraîner le modèle :

```bash
python model/train_baseline.py
```
