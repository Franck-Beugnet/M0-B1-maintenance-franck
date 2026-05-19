# Pytest pour API — Mini-cours

> Brief associé : M0-B1
> Durée de lecture + pratique : ~45 min
> Pré-requis : Python 3.11+, env virtuel actif avec `pytest` et `httpx` installés.

## Pourquoi cette techno ?

Tester une API n'est **pas optionnel** quand on déploie un service en prod :

- chaque modification de code peut casser un endpoint ;
- chaque mise à jour de dépendance (FastAPI, scikit-learn, NumPy) peut casser
  la sérialisation ;
- chaque changement de modèle peut produire des prédictions incohérentes.

**pytest** est l'outil standard de test en Python. Combiné au **`TestClient`**
de FastAPI (basé sur httpx), il permet de tester une API **sans démarrer le
serveur** : on simule des requêtes en mémoire.

**Alternatives à connaître :**

| Outil | Position |
|---|---|
| **`unittest`** (stdlib) | OO, verbeux. Encore présent dans le legacy. |
| **`hypothesis`** | Property-based testing. Excellent en complément de pytest. |
| **`tavern`** | YAML-based tests d'API. Pour QA non-dev. |

Sur ce parcours, **pytest est imposé** (cf. CLAUDE.md §8). On l'utilisera de
M0 à M9.

## Concepts clés

- **Convention de nommage** : fichiers `test_*.py`, fonctions `test_*`. pytest
  les découvre automatiquement.
- **`assert`** : tu écris des assertions Python normales. Pas de `assertEqual`
  comme `unittest`. Si l'assert échoue, pytest affiche un diff lisible.
- **Fixture** : fonction qui prépare des données / objets avant un test, marquée
  `@pytest.fixture`. Très utile pour partager une `TestClient` entre tests.
- **`@pytest.mark.parametrize`** : exécute un même test avec plusieurs jeux de
  données. Évite la copie-colle.
- **`TestClient` (FastAPI)** : encapsule l'app, simule des requêtes HTTP via
  httpx. **Le `with TestClient(app) as client:` déclenche le lifespan**
  (chargement du modèle, etc.).
- **Codes HTTP attendus** : 200 (OK), 201 (créé), 400 (mauvaise requête métier),
  422 (validation Pydantic échouée), 500 (erreur serveur). À tester
  systématiquement.

## Exemple minimal qui tourne

```python
# tests/test_addition.py — exemple sans API pour comprendre pytest
def addition(a: int, b: int) -> int:
    return a + b


def test_addition_simple():
    assert addition(2, 3) == 5


def test_addition_negatifs():
    assert addition(-1, -2) == -3


import pytest

@pytest.mark.parametrize("a,b,attendu", [
    (0, 0, 0),
    (10, -3, 7),
    (1, 1, 2),
])
def test_addition_param(a, b, attendu):
    assert addition(a, b) == attendu
```

Lance :

```bash
pytest -v
```

Tu vois `5 passed` (1 + 1 + 3 paramétrés). Si un cas échoue, pytest te montre
**la valeur attendue vs la valeur reçue** — gros gain de productivité par
rapport à `assertEqual`.

### Avec FastAPI TestClient

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:    # ← le `with` déclenche le lifespan
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "model_loaded": True}
```

Le `with` est **important** : sans lui, le `lifespan` qui charge le modèle ne
s'exécute pas, et `model_loaded` serait `False`.

## Exercice guidé

Tu as déjà 2 tests pour `/health` dans `tests/test_health.py` (livrés au clone).
**Ajoute 3 tests pour `/predict`** dans un nouveau fichier `tests/test_predict.py`.

**Cherche par toi-même** en t'appuyant sur la section *Concepts clés* et l'exemple
*Avec FastAPI TestClient* ci-dessus. La solution est masquée plus bas — à révéler
seulement après ta tentative.

**À écrire :**

1. Une **fixture `client`** de scope `module` qui ouvre un `TestClient(app)` avec
   `with` (pour déclencher le `lifespan`).
2. **Test cas valide** : POST `/predict` avec un payload `compresseur` complet,
   attendu `200` + `body["criticite"] in {"basse","moyenne","haute"}` +
   somme des `probabilites.values()` ≈ 1.
3. **Test cas invalide** : POST avec `type_machine: "INCONNU"`, attendu `422`
   (validation Pydantic).
4. **Test paramétré** : `@pytest.mark.parametrize` sur 4 types
   (`pompe`, `convoyeur`, `presse`, `four`), chaque cas doit renvoyer `200`.

**Payload de référence** (à adapter selon les tests) :
```json
{
  "type_machine": "compresseur",
  "age_machine_jours": 1500,
  "derniere_maintenance_jours": 45,
  "temperature_moyenne": 68.5,
  "vibration_moyenne": 3.2,
  "pression_moyenne": 7.8,
  "nb_incidents_3_mois": 2
}
```

✅ **Résultat attendu** :
- `pytest -v` affiche **6 tests** (2 sur `/health` + 4 sur `/predict`),
  tous PASSED.
- Le test paramétré exécute 4 cas (un par type de machine).

<details>
<summary>🔒 <strong>Solution</strong> — clique pour révéler (après avoir cherché)</summary>

```python
# tests/test_predict.py
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """Fixture partagée : un seul TestClient pour tout le module."""
    with TestClient(app) as c:
        yield c


# 1. Cas valide → 200 + structure attendue
def test_predict_cas_valide(client):
    payload = {
        "type_machine": "compresseur",
        "age_machine_jours": 1500,
        "derniere_maintenance_jours": 45,
        "temperature_moyenne": 68.5,
        "vibration_moyenne": 3.2,
        "pression_moyenne": 7.8,
        "nb_incidents_3_mois": 2,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["criticite"] in {"basse", "moyenne", "haute"}
    assert set(body["probabilites"].keys()) == {"basse", "moyenne", "haute"}
    # somme des probas ≈ 1
    assert abs(sum(body["probabilites"].values()) - 1.0) < 1e-6


# 2. Type machine invalide → 422 (validation Pydantic)
def test_predict_type_machine_invalide(client):
    payload = {
        "type_machine": "INCONNU",
        "age_machine_jours": 1000,
        "derniere_maintenance_jours": 30,
        "temperature_moyenne": 65.0,
        "vibration_moyenne": 3.0,
        "pression_moyenne": 8.0,
        "nb_incidents_3_mois": 1,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 422


# 3. Plusieurs scénarios paramétrés
@pytest.mark.parametrize("type_m", ["pompe", "convoyeur", "presse", "four"])
def test_predict_tous_types_machine(client, type_m):
    payload = {
        "type_machine": type_m,
        "age_machine_jours": 2000,
        "derniere_maintenance_jours": 60,
        "temperature_moyenne": 70.0,
        "vibration_moyenne": 3.5,
        "pression_moyenne": 8.5,
        "nb_incidents_3_mois": 2,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 200
    assert r.json()["criticite"] in {"basse", "moyenne", "haute"}
```

</details>

⭐ **Bonus 1** : ajoute un test qui vérifie que la **somme des probabilités est
exactement 1.0** à `1e-9` près (montre que tu comprends `predict_proba`).

⭐ **Bonus 2** : ajoute un test « champ obligatoire manquant » → 422.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Oublier `with TestClient(app) as client:` | Le `lifespan` ne tourne pas → le modèle n'est pas chargé, `model_loaded:false`. |
| Définir une "fixture" sans `@pytest.fixture` | Ce n'est pas une fixture, c'est un appel direct → comportement imprévisible. |
| Mal comprendre `scope="module"` / `scope="session"` | State partagé entre tests, comportement dépendant de l'ordre. |
| Tests qui dépendent de l'**ordre** d'exécution | Faux verts en local, rouges en CI (anti-pattern majeur). |
| Tests qui font de **vrais appels réseau / fichier** | Lenteur + flakiness. Préférer `TestClient` ou mocker. |
| Assertions trop vagues : `assert r.status_code == 200` uniquement | Le test passe même si la réponse est incomplète/incorrecte. Vérifier aussi **structure**, **contenu** et **contrat métier**. |

**Symptôme → cause probable**

| Symptôme | Cause probable |
|---|---|
| `model_loaded:false` dans le test `/health` | `TestClient` utilisé sans `with` → lifespan pas exécuté |
| Tests qui passent seuls mais échouent en suite | State partagé entre tests (fixture mal scopée) ou ordre implicite |
| Un test devient lent / flaky en CI | Vrais appels réseau ou I/O — à mocker ou utiliser `TestClient` |
| `pytest` ne trouve aucun test | Fichier ou fonction sans préfixe `test_`, ou pas dans un répertoire reconnu |
| Assertion `assert r.json() == {...}` trop fragile | Inclure trop de détails dans le dict attendu — préférer assertions ciblées sur les clés contractuelles |

## Pour aller plus loin

- **Doc officielle pytest** : <https://docs.pytest.org/>
- **Doc TestClient FastAPI** : <https://fastapi.tiangolo.com/tutorial/testing/>
- **Référence legacy OPCO ATLAS** (partie « Pytest » : fixtures avec base
  SQLite, parametrize) : disponible **à la demande via Discord** auprès de la
  formatrice. Bon complément si tu veux des exemples plus poussés.
- **Coverage** : `pytest --cov=app` (nécessite `pytest-cov`). Vérifie que tu
  testes bien tout ton code.

⭐ **Pour M5** (CI/CD), tes tests pytest tourneront automatiquement sur chaque
push GitHub. Donc : **chaque test que tu écris aujourd'hui te protège pour
toujours.**

## Vérification (checklist apprenant)

- [ ] J'ai un fichier `tests/test_predict.py` avec **3 tests minimum**.
- [ ] `pytest -v` affiche tous les tests PASSED.
- [ ] J'ai utilisé une **fixture** pour partager le `TestClient`.
- [ ] J'ai utilisé `@pytest.mark.parametrize` au moins une fois.
- [ ] Je sais expliquer pourquoi le `with TestClient(app) as ...:` est nécessaire.
- [ ] Je sais ce que veut dire **HTTP 422** et qui le déclenche (Pydantic).
- [ ] Je sais comment lancer un seul test ciblé : `pytest tests/test_predict.py::test_predict_cas_valide -v`.
