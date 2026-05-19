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
import os
from pathlib import Path
import pandas as pd
from typing import Any

import httpx
import joblib
from fastapi import FastAPI, HTTPException
from loguru import logger

from app.schemas import HealthResponse, MachineInput, PredictionResponse


MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "model.joblib"

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma3:1b"

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


@app.post("/predict_explain")
def predict_explain(item: MachineInput) -> dict:
    """Prédit la criticité puis génère une explication en français via Ollama.

    Args:
        item: caractéristiques de la machine (identiques à /predict).

    Returns:
        dict avec `criticite`, `probabilites` et `explication`.
    """
    # --- prédiction ---
    item_dict = item.model_dump()
    df = pd.DataFrame([item_dict])
    model = state["model"]
    predicted_class = model.predict(df)[0]
    probabilities = model.predict_proba(df)[0]
    class_probabilities = dict(zip(model.classes_, probabilities))
    logger.info(f"Prédiction interne /explain : {predicted_class}")

    # --- contexte métier dérivé des seuils observés dans le dataset ---
    age_ans = item.age_machine_jours // 365
    age_ctx = (
        "machine jeune (faible usure)"
        if item.age_machine_jours < 3_000
        else "machine vieillissante (usure modérée)"
        if item.age_machine_jours < 5_000
        else "machine très ancienne (usure avancée)"
    )
    vibration_ctx = (
        "normale (< 3 mm/s, typique criticité basse)"
        if item.vibration_moyenne < 3.0
        else "élevée (3–4 mm/s, typique criticité moyenne)"
        if item.vibration_moyenne < 4.0
        else "critique (> 4 mm/s, typique criticité haute)"
    )
    maintenance_ctx = (
        "récente (< 90 j)"
        if item.derniere_maintenance_jours < 90
        else "en limite (90–130 j)"
        if item.derniere_maintenance_jours < 130
        else "en retard (> 130 j)"
    )
    incidents_ctx = (
        "faible (0–2)"
        if item.nb_incidents_3_mois <= 2
        else "préoccupant (3–4)"
        if item.nb_incidents_3_mois <= 4
        else "alarmant (> 4)"
    )

    # --- prompt Ollama ---
    prob_fmt = ", ".join(
        f"{cls}={prob:.0%}" for cls, prob in sorted(class_probabilities.items())
    )
    criticite_def = {
        "basse":   "la machine est en bon état général, aucune urgence détectée",
        "moyenne": "la machine présente des signes de dégradation, surveillance accrue requise",
        "haute":   "la machine présente un risque d'incident grave, intervention prioritaire requise",
    }
    consigne_ton = {
        "basse": (
            "Explique pourquoi les indicateurs sont dans les normes et confirment l'absence d'urgence. "
            "Ne suggère PAS d'intervention urgente ni de risque de panne."
        ),
        "moyenne": (
            "Identifie les indicateurs qui s'écartent légèrement des normes et justifient une surveillance. "
            "Préconise une planification de maintenance à court terme, sans alarmisme."
        ),
        "haute": (
            "Identifie clairement les indicateurs critiques (avec leurs valeurs) qui justifient l'urgence. "
            "Préconise une intervention immédiate et concrète."
        ),
    }
    prompt = (
        "Tu es un expert en maintenance industrielle prédictive. "
        "Un modèle ML a calculé un score composite de sévérité pour prioriser les interventions.\n\n"
        f"RÉSULTAT DU MODÈLE : criticité = {predicted_class.upper()} ({prob_fmt})\n"
        f"Ce niveau signifie : {criticite_def[predicted_class]}\n"
        "IMPORTANT : ton explication DOIT être cohérente avec ce niveau de criticité. "
        "Ne le contredis pas.\n\n"
        "Données de la machine avec interprétation par rapport au parc :\n"
        f"- Type : {item.type_machine} — {age_ans} ans ({age_ctx})\n"
        f"- Vibration moyenne (7j) : {item.vibration_moyenne} mm/s → {vibration_ctx}\n"
        f"- Dernière maintenance : il y a {item.derniere_maintenance_jours} jours → {maintenance_ctx}\n"
        f"- Incidents sur 3 mois : {item.nb_incidents_3_mois} → {incidents_ctx}\n"
        f"- Température moyenne (7j) : {item.temperature_moyenne} °C (peu discriminante)\n"
        f"- Pression moyenne (7j) : {item.pression_moyenne} bar (peu discriminante)\n\n"
        f"Consigne de rédaction : {consigne_ton[predicted_class]}\n"
        "Rédige 2 à 3 phrases en français, en citant les valeurs numériques clés. "
        "Réponds uniquement avec l'explication, sans titre ni liste."
    )

    # --- appel Ollama ---
    logger.info(f"Appel Ollama (modèle={OLLAMA_MODEL}) pour criticité '{predicted_class}'")
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
    except httpx.ConnectError:
        logger.error("Impossible de joindre Ollama — vérifiez que le service tourne.")
        raise HTTPException(
            status_code=503,
            detail="Service Ollama inaccessible. Assurez-vous qu'Ollama est démarré.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error(f"Erreur HTTP Ollama : {exc.response.status_code}")
        raise HTTPException(
            status_code=502,
            detail=f"Erreur retournée par Ollama : {exc.response.text}",
        )

    explication = resp.json().get("response", "").strip()
    logger.info(f"Explication générée ({len(explication)} caractères)")
    return {
        "criticite": predicted_class,
        "probabilites": class_probabilities,
        "explication": explication,
    }
