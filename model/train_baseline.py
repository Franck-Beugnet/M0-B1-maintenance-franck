"""Entraîne le modèle baseline de classification de criticité (M0-B1).

Charge le dataset généré par `data/generate_dataset.py`, construit un pipeline
scikit-learn (`ColumnTransformer` + `RandomForestClassifier`), évalue par
validation croisée stratifiée, sauvegarde le pipeline complet via joblib.

Le modèle livré est volontairement honnête : ~80 % d'accuracy en multi-classes,
classe `haute` sous-représentée (10 %) → pédagogiquement intéressant pour la suite
(M2 sur le préprocessing, M5 sur le monitoring, M6 sur la dérive).

Le `.joblib` produit ici est livré aux apprenants en M0-B1 — eux n'ont pas à le
réentraîner ; leur mission est de l'**exposer via une API**.

Usage :
    python train_baseline.py
    python train_baseline.py --input ../data/maintenance_data.csv --output model.joblib
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data" / "maintenance_data.csv"
DEFAULT_OUTPUT = Path(__file__).parent / "model.joblib"

TARGET_COL = "criticite"
ID_COL = "machine_id"
CAT_FEATURES = ["type_machine"]
NUM_FEATURES = [
    "age_machine_jours",
    "derniere_maintenance_jours",
    "temperature_moyenne",
    "vibration_moyenne",
    "pression_moyenne",
    "nb_incidents_3_mois",
]


def build_pipeline() -> Pipeline:
    """Construit le pipeline preprocessing + RandomForest.

    Returns:
        Pipeline scikit-learn prêt à l'entraînement.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUM_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ]
    )
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return Pipeline([("preprocessor", preprocessor), ("classifier", model)])


def main() -> int:
    """Entraîne et sauvegarde le modèle.

    Returns:
        0 si succès.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"Dataset chargé : {df.shape[0]} lignes × {df.shape[1]} colonnes")

    X = df.drop(columns=[TARGET_COL, ID_COL])
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    pipeline = build_pipeline()

    cv_scores = cross_val_score(
        pipeline, X_train, y_train, cv=5, scoring="f1_macro", n_jobs=-1
    )
    print(f"\nValidation croisée (train, 5 folds) — F1 macro : "
          f"{cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    print("\nÉvaluation sur le test set :")
    print(classification_report(y_test, y_pred, digits=3))

    print("Matrice de confusion (lignes = vraies classes, colonnes = prédites) :")
    classes_sorted = sorted(y.unique())
    cm = confusion_matrix(y_test, y_pred, labels=classes_sorted)
    cm_df = pd.DataFrame(cm, index=classes_sorted, columns=classes_sorted)
    print(cm_df.to_string())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # compress=3 → bon compromis vitesse / taille (RF 200 estimators ~ 31 Mo → ~3 Mo)
    joblib.dump(pipeline, args.output, compress=3)

    size_kb = args.output.stat().st_size // 1024
    print(f"\n✅ Modèle sauvegardé : {args.output} ({size_kb} ko, compressé)")

    return 0


if __name__ == "__main__":
    sys.exit(main())