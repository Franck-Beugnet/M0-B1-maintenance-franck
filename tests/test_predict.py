from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


#valid 
def test_valid():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json= {
                "type_machine": "compresseur",
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["criticite"] in ["basse", "moyenne", "haute"]
        assert isinstance(body["probabilites"], dict)

def test_machine_invalid():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json= {
                "type_machine": "blabla",
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2
            },
        )
        assert response.status_code == 422  # Unprocessable Entity for validation error


def test_response_schema_keys():
    """La réponse doit contenir exactement les clés 'criticite' et 'probabilites'."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "pompe",
                "age_machine_jours": 500,
                "derniere_maintenance_jours": 10,
                "temperature_moyenne": 55.0,
                "vibration_moyenne": 1.5,
                "pression_moyenne": 5.0,
                "nb_incidents_3_mois": 0,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"criticite", "probabilites"}


def test_probabilites_somme_a_un():
    """Les probabilités retournées doivent sommer à 1.0 (± tolérance flottant)."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "four",
                "age_machine_jours": 3000,
                "derniere_maintenance_jours": 200,
                "temperature_moyenne": 95.0,
                "vibration_moyenne": 4.0,
                "pression_moyenne": 9.0,
                "nb_incidents_3_mois": 5,
            },
        )
        assert response.status_code == 200
        probabilites = response.json()["probabilites"]
        assert abs(sum(probabilites.values()) - 1.0) < 1e-6


def test_probabilites_contient_toutes_les_classes():
    """Le dict 'probabilites' doit contenir exactement les 3 classes."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "convoyeur",
                "age_machine_jours": 1000,
                "derniere_maintenance_jours": 30,
                "temperature_moyenne": 60.0,
                "vibration_moyenne": 2.0,
                "pression_moyenne": 6.0,
                "nb_incidents_3_mois": 1,
            },
        )
        assert response.status_code == 200
        probabilites = response.json()["probabilites"]
        assert set(probabilites.keys()) == {"basse", "moyenne", "haute"}


def test_probabilites_entre_0_et_1():
    """Chaque probabilité doit être comprise entre 0 et 1."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "presse",
                "age_machine_jours": 2000,
                "derniere_maintenance_jours": 90,
                "temperature_moyenne": 75.0,
                "vibration_moyenne": 3.0,
                "pression_moyenne": 8.0,
                "nb_incidents_3_mois": 3,
            },
        )
        assert response.status_code == 200
        for proba in response.json()["probabilites"].values():
            assert 0.0 <= proba <= 1.0


# --- Validation des champs ---

def test_champ_manquant_retourne_422():
    """Un champ obligatoire absent doit retourner 422."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                # "type_machine" absent intentionnellement
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2,
            },
        )
        assert response.status_code == 422


def test_age_machine_negatif_retourne_422():
    """Un âge machine négatif doit être rejeté (ge=0)."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "pompe",
                "age_machine_jours": -1,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2,
            },
        )
        assert response.status_code == 422


def test_derniere_maintenance_depasse_365_retourne_422():
    """Une valeur > 365 pour derniere_maintenance_jours doit être rejetée (le=365)."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "pompe",
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 400,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": 3.2,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2,
            },
        )
        assert response.status_code == 422


def test_vibration_negative_retourne_422():
    """Une vibration négative doit être rejetée (ge=0)."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "pompe",
                "age_machine_jours": 1500,
                "derniere_maintenance_jours": 45,
                "temperature_moyenne": 68.5,
                "vibration_moyenne": -0.1,
                "pression_moyenne": 7.8,
                "nb_incidents_3_mois": 2,
            },
        )
        assert response.status_code == 422


def test_machine_neuve_zero_incidents():
    """Une machine neuve sans incident doit retourner une criticité valide."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "pompe",
                "age_machine_jours": 0,
                "derniere_maintenance_jours": 0,
                "temperature_moyenne": 50.0,
                "vibration_moyenne": 0.0,
                "pression_moyenne": 5.0,
                "nb_incidents_3_mois": 0,
            },
        )
        assert response.status_code == 200
        assert response.json()["criticite"] in ["basse", "moyenne", "haute"]


def test_machine_tres_ancienne_nombreux_incidents():
    """Une machine très ancienne avec beaucoup d'incidents doit retourner une criticité valide."""
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "type_machine": "four",
                "age_machine_jours": 9999,
                "derniere_maintenance_jours": 365,
                "temperature_moyenne": 120.0,
                "vibration_moyenne": 10.0,
                "pression_moyenne": 15.0,
                "nb_incidents_3_mois": 20,
            },
        )
        assert response.status_code == 200
        assert response.json()["criticite"] in ["basse", "moyenne", "haute"]


def test_tous_les_types_machine_acceptes():
    """Chaque type de machine valide doit être accepté par l'API."""
    types_valides = ["pompe", "compresseur", "convoyeur", "presse", "four"]
    with TestClient(app) as client:
        for type_machine in types_valides:
            response = client.post(
                "/predict",
                json={
                    "type_machine": type_machine,
                    "age_machine_jours": 1000,
                    "derniere_maintenance_jours": 30,
                    "temperature_moyenne": 65.0,
                    "vibration_moyenne": 2.5,
                    "pression_moyenne": 7.0,
                    "nb_incidents_3_mois": 1,
                },
            )
            assert response.status_code == 200, f"Échec pour type_machine={type_machine}"

