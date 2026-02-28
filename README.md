# 🐍 Python Test Platform

Plateforme d'évaluation automatique de code Python pour les étudiants — USTHB.

## Fonctionnalités

- **Éditeur de code** avec coloration syntaxique (CodeMirror, thème Dracula)
- **8 exercices** progressifs (somme, pair, factorielle, tri, Fibonacci...)
- **Notation automatique** sur 20 avec détail des tests réussis/échoués
- **Espace professeur** (`/admin`) avec tableau récapitulatif et export CSV
- **Base de données** SQLite (local) ou PostgreSQL (Render)
- **Sécurité** : analyse statique du code + exécution en subprocess avec timeout

## Structure du projet

```
python-test-app/
├── app.py                 # Application Flask principale
├── requirements.txt       # Dépendances Python
├── Procfile              # Configuration Gunicorn
├── render.yaml           # Configuration Render.com
├── .gitignore
├── templates/
│   ├── index.html        # Interface étudiant
│   └── admin.html        # Espace professeur
└── README.md
```

## Lancer en local

```bash
# 1. Cloner le projet
git clone <url-du-repo>
cd python-test-app

# 2. Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python app.py
```

Ouvrir http://localhost:5000

**Espace professeur** : http://localhost:5000/admin (mot de passe par défaut : `prof2025`)

## Déploiement sur Render.com

### Méthode 1 : Via render.yaml (recommandée)

1. **Pousser le code sur GitHub** :
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/VOTRE-USER/python-test-app.git
   git push -u origin main
   ```

2. **Sur Render.com** :
   - Aller sur [dashboard.render.com](https://dashboard.render.com)
   - Cliquer **New** → **Blueprint**
   - Connecter le repo GitHub
   - Render détectera le `render.yaml` et créera automatiquement le service + la base de données

### Méthode 2 : Configuration manuelle

1. **Créer une base de données** :
   - **New** → **PostgreSQL** → Plan Free → Créer
   - Copier l'**Internal Database URL**

2. **Créer un Web Service** :
   - **New** → **Web Service** → Connecter le repo GitHub
   - **Runtime** : Python 3
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
   - **Variables d'environnement** :
     | Clé | Valeur |
     |-----|--------|
     | `DATABASE_URL` | *(coller l'URL PostgreSQL)* |
     | `SECRET_KEY` | *(générer une clé aléatoire)* |
     | `ADMIN_PASSWORD` | *(votre mot de passe professeur)* |

3. Cliquer **Deploy**

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | URL PostgreSQL | `sqlite:///pytestapp.db` |
| `SECRET_KEY` | Clé secrète Flask | `dev-secret-key...` |
| `ADMIN_PASSWORD` | Mot de passe admin | `prof2025` |

## Ajouter des exercices

Modifier le dictionnaire `EXERCISES` dans `app.py` :

```python
"ex_nouveau": {
    "title": "Exercice N : Mon exercice",
    "description": "Description en HTML...",
    "template": "def ma_fonction(x):\n    pass\n",
    "test_cases": [
        {"input": "print(ma_fonction(1))", "expected": "résultat_attendu"},
        # ...
    ],
},
```

## Sécurité

- Analyse statique bloquant `import os`, `eval()`, `open()`, etc.
- Exécution dans un `subprocess` isolé avec timeout de 3 secondes
- Mot de passe requis pour l'espace professeur
- **⚠️ Pour une sécurité renforcée en production**, envisagez d'utiliser l'[API Piston](https://github.com/engineer-man/piston) ou Docker pour l'exécution du code.

## Licence

Usage éducatif — USTHB
