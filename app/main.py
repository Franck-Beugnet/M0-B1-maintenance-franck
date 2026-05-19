"""API FastAPI — service de classification de criticité (M0-B1).

Expose un modèle scikit-learn pré-entraîné (cf. `model/train_baseline.py`) via
deux routes :

- `GET /health`  : santé du service (déjà fonctionnel)
- `POST /predict` : prédiction de criticité (🎯 à compléter par l'apprenant)

Le modèle est chargé une seule fois au démarrage via le `lifespan` FastAPI puis
réutilisé pour chaque requête.

Lancement local :
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import pandas as pd
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException
from loguru import logger

from app.schemas import HealthResponse, MachineInput, PredictionResponse


MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "model.joblib"

# Mémoire d'application — peuplée par le lifespan
state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle au démarrage, libère à l'arrêt.

    Args:
        app: instance FastAPI.
    """
    #logger setup
    logger.add(
        "logs/api.log",
        rotation="5 MB",       
        retention="7 days",  
        compression="zip",      
        level="INFO",            
    )

    if not MODEL_PATH.is_file():
        logger.error(
            f"Modèle introuvable : {MODEL_PATH}. "
            f"Lance d'abord : python model/train_baseline.py"
        )
        raise RuntimeError(f"Modèle introuvable : {MODEL_PATH}")

    logger.info(f"Chargement du modèle depuis {MODEL_PATH}")
    state["model"] = joblib.load(MODEL_PATH)
    logger.info("Modèle chargé.")

    yield

    state.clear()
    logger.info("Service arrêté, état libéré.")


app = FastAPI(
    title="FastIA — Service de criticité maintenance prédictive",
    description=(
        "API d'exposition d'un modèle scikit-learn de classification de criticité "
        "d'incidents machine (3 classes : basse, moyenne, haute)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Retourne le statut du service et du modèle.

    Returns:
        HealthResponse — `status="ok"` si le modèle est chargé, `degraded` sinon.
    """
    is_loaded = "model" in state
    return HealthResponse(
        status="ok" if is_loaded else "degraded",
        model_loaded=is_loaded,
    )

@app.post("/predict", response_model=PredictionResponse)
@logger.catch
def predict(item: MachineInput) -> PredictionResponse:
    """Prédit la criticité d'une machine à partir de ses caractéristiques.

    🎯 **À COMPLÉTER PAR L'APPRENANT.**

    Indices d'implémentation :

    1. Construire un DataFrame pandas à 1 ligne à partir de `item.model_dump()`.
       Le pipeline scikit-learn attend les colonnes dans le même ordre qu'à
       l'entraînement (cf. `model/train_baseline.py`, `NUM_FEATURES` + `CAT_FEATURES`).
    2. Récupérer le modèle via `state["model"]`.
    3. Appeler `model.predict(df)[0]` pour obtenir la classe prédite (str).
    4. Appeler `model.predict_proba(df)[0]` pour obtenir les probabilités.
       Les classes correspondantes sont dans `model.classes_`.
    5. Construire et retourner un `PredictionResponse`.
    6. Logger l'entrée + la classe prédite + le temps de réponse via Loguru.

    Args:
        item: caractéristiques de la machine (cf. `schemas.MachineInput`).

    Returns:
        PredictionResponse avec la classe prédite et les probabilités.
    """

    #building a dataframe from the input item
    item_dict = item.model_dump()
    df = pd.DataFrame([item_dict])
    
    #getting the model from the state
    model = state["model"]

    #predicting the class and probabilities
    predicted = model.predict(df)
    predicted_class = predicted[0]
    probabilities = model.predict_proba(df)[0]
    class_probabilities = dict(zip(model.classes_, probabilities))  
    logger.info(f"Input: {item_dict}, Predicted class: {predicted_class}, Probabilities: {class_probabilities}, Response time: {predicted.shape[0]} ms")

    #constructing the response
    response = PredictionResponse(
        criticite=predicted_class,
        probabilites=class_probabilities
    )
    return response
