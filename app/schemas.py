"""Schémas Pydantic d'entrée et sortie de l'API.

L'API attend les 7 features observables d'une machine (cf. dataset
`data/maintenance_data.csv`, hors `machine_id` qui n'entre pas dans le modèle)
et retourne la classe prédite + les probabilités associées.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TypeMachine = Literal["pompe", "compresseur", "convoyeur", "presse", "four"]
Criticite = Literal["basse", "moyenne", "haute"]


class MachineInput(BaseModel):
    """Données d'entrée d'une prédiction de criticité.

    Les bornes des champs reflètent les plages observées dans le dataset
    d'entraînement et servent de garde-fou contre les entrées aberrantes.
    """

    type_machine: TypeMachine = Field(
        description="Famille de la machine.",
    )
    age_machine_jours: int = Field(
        ge=0,
        le=10_000,
        description="Âge de la machine en jours (0 à 10 000).",
    )
    derniere_maintenance_jours: int = Field(
        ge=0,
        le=365,
        description="Jours écoulés depuis la dernière maintenance (0 à 365).",
    )
    temperature_moyenne: float = Field(
        description="Température moyenne 7 derniers jours, °C.",
    )
    vibration_moyenne: float = Field(
        ge=0,
        description="Vibration moyenne 7 derniers jours, mm/s (≥ 0).",
    )
    pression_moyenne: float = Field(
        ge=0,
        description="Pression moyenne 7 derniers jours, bar (≥ 0).",
    )
    nb_incidents_3_mois: int = Field(
        ge=0,
        description="Nombre d'incidents recensés sur les 3 derniers mois (≥ 0).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "type_machine": "compresseur",
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2,
            }
        }
    }


class PredictionResponse(BaseModel):
    """Sortie d'une prédiction : classe + probabilités."""

    criticite: Criticite = Field(description="Classe prédite par le modèle.")
    probabilites: dict[Criticite, float] = Field(
        description="Probabilité par classe (somme = 1.0).",
    )


class HealthResponse(BaseModel):
    """Sortie de la route /health."""

    status: Literal["ok", "degraded"] = Field(description="Statut global du service.")
    model_loaded: bool = Field(description="Vrai si le modèle est chargé en mémoire.")