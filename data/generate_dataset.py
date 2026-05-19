"""Génère un dataset synthétique de maintenance prédictive industrielle.

Cas FastIA — M0-B1 : un industriel, client de FastIA, fait remonter pour chaque
machine un ensemble de mesures (capteurs + historique) et son équipe data a entraîné
un modèle qui score la criticité d'incident attendue en `basse`, `moyenne` ou
`haute`. C'est ce dataset qui sert à l'entraînement du modèle livré aux apprenants
(cf. `model/train_baseline.py`).

Caractéristiques injectées (volontairement non triviales pour permettre un
apprentissage non parfait, ~75-85 % d'accuracy attendue) :

- Volume : ~6 500 lignes (configurable via --rows)
- Classes : 60 % basse / 30 % moyenne / 10 % haute (déséquilibre pédagogique)
- 9 variables : machine_id, type_machine, age_machine_jours,
  derniere_maintenance_jours, temperature_moyenne, vibration_moyenne,
  pression_moyenne, nb_incidents_3_mois, criticite (cible)
- Corrélations injectées :
    * machines plus anciennes → tendance vers criticité haute (non systématique)
    * vibration / température anormales → augmente la criticité
    * maintenance récente (< 30 j) → effet protecteur modéré
    * pression seule → faible signal (variable volontairement peu informative)
    * type_machine → effet modéré (presse / four / compresseur > pompe / convoyeur)
- Pas de variable sensible RGPD, pas de NaN, pas de doublons d'identifiant
- random_state=42 → reproductibilité totale

Usage :
    python generate_dataset.py
    python generate_dataset.py --rows 8000 --output data/maintenance_data.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

RANDOM_STATE = 42
DEFAULT_ROWS = 6500
DEFAULT_OUTPUT = Path(__file__).parent / "maintenance_data.csv"

TYPES_MACHINE = ("pompe", "compresseur", "convoyeur", "presse", "four")

# Effets relatifs par type sur la criticité (signal modéré)
TYPE_EFFECT: dict[str, float] = {
    "pompe": 0.0,        # baseline
    "convoyeur": -0.2,   # plus stable
    "compresseur": 0.3,  # un peu plus risqué
    "four": 0.4,         # haute température, plus risqué
    "presse": 0.5,       # mécanique lourde, plus risquée
}


def generate(n_rows: int, random_state: int = RANDOM_STATE) -> pd.DataFrame:
    """Génère un DataFrame de maintenance prédictive.

    Args:
        n_rows: nombre de machines à générer.
        random_state: graine pour reproductibilité.

    Returns:
        DataFrame de `n_rows` lignes et 9 colonnes, sans NaN, sans doublons d'ID.
    """
    rng = np.random.default_rng(random_state)
    Faker.seed(random_state)
    fake = Faker("fr_FR")

    machine_ids = [f"MCH-{fake.country_code()}-{i:05d}" for i in range(n_rows)]
    type_machine = rng.choice(TYPES_MACHINE, size=n_rows)

    age_machine_jours = rng.uniform(0, 6000, size=n_rows).astype(int)
    derniere_maintenance_jours = (
        rng.gamma(shape=2.0, scale=45.0, size=n_rows).clip(0, 365).astype(int)
    )
    temperature_moyenne = rng.normal(loc=65, scale=12, size=n_rows).round(1)
    vibration_moyenne = rng.normal(loc=3.0, scale=1.5, size=n_rows).clip(0).round(2)
    pression_moyenne = rng.normal(loc=8.0, scale=2.5, size=n_rows).clip(0).round(2)
    nb_incidents_3_mois = rng.poisson(lam=2.0, size=n_rows)

    # Composantes pondérées du score de criticité
    score_age = (age_machine_jours / 6000) ** 1.5
    score_temp = np.maximum(0, np.abs(temperature_moyenne - 65) - 10) / 30
    score_vib = np.maximum(0, vibration_moyenne - 3.5) / 3
    score_maint = np.where(
        derniere_maintenance_jours < 30,
        -0.4,
        np.minimum(1.0, derniere_maintenance_jours / 200) * 0.3,
    )
    score_inc = np.minimum(1.0, nb_incidents_3_mois / 5) * 0.6
    score_type = np.array([TYPE_EFFECT[t] for t in type_machine])
    bruit = rng.normal(0, 0.25, size=n_rows)

    score = (
        1.2 * score_age
        + 1.5 * score_temp
        + 1.5 * score_vib
        + score_maint
        + score_inc
        + 0.5 * score_type
        + bruit
    )

    # Quantiles 60 / 90 → cible 60 % basse / 30 % moyenne / 10 % haute
    q60, q90 = np.quantile(score, [0.60, 0.90])
    criticite = np.where(
        score >= q90, "haute", np.where(score >= q60, "moyenne", "basse")
    )

    df = pd.DataFrame(
        {
            "machine_id": machine_ids,
            "type_machine": type_machine,
            "age_machine_jours": age_machine_jours,
            "derniere_maintenance_jours": derniere_maintenance_jours,
            "temperature_moyenne": temperature_moyenne,
            "vibration_moyenne": vibration_moyenne,
            "pression_moyenne": pression_moyenne,
            "nb_incidents_3_mois": nb_incidents_3_mois,
            "criticite": criticite,
        }
    )

    assert df.isna().sum().sum() == 0, "NaN détectés (ne devrait pas arriver)"
    assert df["machine_id"].is_unique, "machine_id non uniques"

    return df


def main() -> int:
    """Point d'entrée CLI.

    Returns:
        0 si succès.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE)
    args = parser.parse_args()

    df = generate(args.rows, args.random_state)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8")

    print(f"✅ Dataset généré : {args.output} ({len(df)} lignes, {df.shape[1]} colonnes)")
    print("\nDistribution criticité :")
    print(df["criticite"].value_counts(normalize=True).round(3).to_string())
    print("\nAperçu (3 premières lignes) :")
    print(df.head(3).to_string(index=False))
    print("\nStatistiques numériques :")
    print(df.select_dtypes(include="number").describe().round(2).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
