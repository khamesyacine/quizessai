"""
Python Test Platform - Application Flask pour tester les étudiants en Python
Auteur: Plateforme d'évaluation automatique
"""

import os
import io
import csv
import subprocess
import tempfile
import json
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, Response, flash
)
from flask_sqlalchemy import SQLAlchemy

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Database: PostgreSQL on Render or SQLite locally
database_url = os.environ.get("DATABASE_URL", "sqlite:///pytestapp.db")
# Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────
class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    student_group = db.Column(db.String(60), default="")
    exercise_id = db.Column(db.String(60), nullable=False)
    code = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, default=20.0)
    details = db.Column(db.Text, default="")  # JSON string of test results
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Submission {self.student_name} - {self.exercise_id}: {self.score}/{self.max_score}>"


# ──────────────────────────────────────────────
# Exercices (configurable)
# ──────────────────────────────────────────────
EXERCISES = {
    "ex1_somme": {
        "title": "Exercice 1 : Fonction somme",
        "description": (
            "Écrivez une fonction <code>somme(a, b)</code> qui retourne la somme "
            "de deux nombres <code>a</code> et <code>b</code>."
        ),
        "template": "def somme(a, b):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(somme(2, 3))", "expected": "5"},
            {"input": "print(somme(-1, 1))", "expected": "0"},
            {"input": "print(somme(0, 0))", "expected": "0"},
            {"input": "print(somme(100, 200))", "expected": "300"},
            {"input": "print(somme(-5, -3))", "expected": "-8"},
        ],
    },
    "ex2_pair": {
        "title": "Exercice 2 : Nombre pair",
        "description": (
            "Écrivez une fonction <code>est_pair(n)</code> qui retourne <code>True</code> "
            "si <code>n</code> est pair, <code>False</code> sinon."
        ),
        "template": "def est_pair(n):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(est_pair(4))", "expected": "True"},
            {"input": "print(est_pair(7))", "expected": "False"},
            {"input": "print(est_pair(0))", "expected": "True"},
            {"input": "print(est_pair(-2))", "expected": "True"},
            {"input": "print(est_pair(1))", "expected": "False"},
        ],
    },
    "ex3_factorielle": {
        "title": "Exercice 3 : Factorielle",
        "description": (
            "Écrivez une fonction <code>factorielle(n)</code> qui retourne la factorielle "
            "de <code>n</code> (un entier positif ou nul). <br>"
            "Rappel : <code>0! = 1</code>, <code>5! = 120</code>."
        ),
        "template": "def factorielle(n):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(factorielle(0))", "expected": "1"},
            {"input": "print(factorielle(1))", "expected": "1"},
            {"input": "print(factorielle(5))", "expected": "120"},
            {"input": "print(factorielle(3))", "expected": "6"},
            {"input": "print(factorielle(10))", "expected": "3628800"},
        ],
    },
    "ex4_inverser": {
        "title": "Exercice 4 : Inverser une chaîne",
        "description": (
            "Écrivez une fonction <code>inverser(s)</code> qui retourne la chaîne "
            "<code>s</code> inversée.<br>"
            "Exemple : <code>inverser('hello')</code> → <code>'olleh'</code>"
        ),
        "template": 'def inverser(s):\n    # Votre code ici\n    pass\n',
        "test_cases": [
            {"input": "print(inverser('hello'))", "expected": "olleh"},
            {"input": "print(inverser('Python'))", "expected": "nohtyP"},
            {"input": "print(inverser(''))", "expected": ""},
            {"input": "print(inverser('a'))", "expected": "a"},
            {"input": "print(inverser('12345'))", "expected": "54321"},
        ],
    },
    "ex5_maximum": {
        "title": "Exercice 5 : Maximum d'une liste",
        "description": (
            "Écrivez une fonction <code>maximum(lst)</code> qui retourne le plus grand "
            "élément d'une liste de nombres <strong>sans utiliser</strong> la fonction "
            "<code>max()</code> intégrée."
        ),
        "template": "def maximum(lst):\n    # Votre code ici\n    # Ne pas utiliser max()\n    pass\n",
        "test_cases": [
            {"input": "print(maximum([1, 5, 3, 9, 2]))", "expected": "9"},
            {"input": "print(maximum([-1, -5, -3]))", "expected": "-1"},
            {"input": "print(maximum([42]))", "expected": "42"},
            {"input": "print(maximum([0, 0, 0]))", "expected": "0"},
            {"input": "print(maximum([10, 20, 30, 5]))", "expected": "30"},
        ],
    },
    "ex6_fibonacci": {
        "title": "Exercice 6 : Suite de Fibonacci",
        "description": (
            "Écrivez une fonction <code>fibonacci(n)</code> qui retourne le n-ième "
            "terme de la suite de Fibonacci.<br>"
            "Convention : <code>fibonacci(0) = 0</code>, <code>fibonacci(1) = 1</code>, "
            "<code>fibonacci(2) = 1</code>, etc."
        ),
        "template": "def fibonacci(n):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(fibonacci(0))", "expected": "0"},
            {"input": "print(fibonacci(1))", "expected": "1"},
            {"input": "print(fibonacci(2))", "expected": "1"},
            {"input": "print(fibonacci(6))", "expected": "8"},
            {"input": "print(fibonacci(10))", "expected": "55"},
        ],
    },
    "ex7_compteur_mots": {
        "title": "Exercice 7 : Compteur de mots",
        "description": (
            "Écrivez une fonction <code>compter_mots(phrase)</code> qui retourne "
            "le nombre de mots dans une phrase. Les mots sont séparés par des espaces."
        ),
        "template": "def compter_mots(phrase):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(compter_mots('Bonjour le monde'))", "expected": "3"},
            {"input": "print(compter_mots('Python'))", "expected": "1"},
            {"input": "print(compter_mots(''))", "expected": "0"},
            {"input": "print(compter_mots('un deux trois quatre cinq'))", "expected": "5"},
            {"input": "print(compter_mots('  espaces  multiples  '))", "expected": "2"},
        ],
    },
    "ex8_tri_selection": {
        "title": "Exercice 8 : Tri par sélection",
        "description": (
            "Écrivez une fonction <code>tri_selection(lst)</code> qui trie une liste "
            "de nombres en ordre croissant en utilisant l'algorithme de tri par sélection. "
            "Retournez la liste triée.<br>"
            "<strong>N'utilisez pas</strong> <code>sort()</code> ou <code>sorted()</code>."
        ),
        "template": "def tri_selection(lst):\n    # Votre code ici\n    # Ne pas utiliser sort() ou sorted()\n    pass\n",
        "test_cases": [
            {"input": "print(tri_selection([3, 1, 4, 1, 5]))", "expected": "[1, 1, 3, 4, 5]"},
            {"input": "print(tri_selection([5, 4, 3, 2, 1]))", "expected": "[1, 2, 3, 4, 5]"},
            {"input": "print(tri_selection([1]))", "expected": "[1]"},
            {"input": "print(tri_selection([]))", "expected": "[]"},
            {"input": "print(tri_selection([10, -3, 7, 0]))", "expected": "[-3, 0, 7, 10]"},
        ],
    },
}

# Password for admin access (set via env var in production)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "prof2025")


# ──────────────────────────────────────────────
# Code Execution Engine (sandboxed subprocess)
# ──────────────────────────────────────────────
FORBIDDEN_KEYWORDS = [
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import http", "import urllib", "import requests",
    "__import__", "eval(", "exec(", "open(", "compile(",
    "import signal", "import ctypes", "import pickle",
]


def check_code_safety(code: str) -> tuple[bool, str]:
    """Basic static analysis to block dangerous code."""
    code_lower = code.lower().replace(" ", "")
    for keyword in FORBIDDEN_KEYWORDS:
        normalized = keyword.lower().replace(" ", "")
        if normalized in code_lower:
            return False, f"Code interdit : utilisation de '{keyword}' non autorisée."
    return True, ""


def run_student_code(student_code: str, test_input: str, timeout: int = 3) -> dict:
    """
    Execute student code + test input in a sandboxed subprocess.
    Returns dict with 'success', 'output', 'error'.
    """
    full_code = student_code + "\n" + test_input

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(full_code)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        os.unlink(tmp_path)

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip(),
                "error": "",
            }
        else:
            return {
                "success": False,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
            }

    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return {
            "success": False,
            "output": "",
            "error": "⏱ Timeout : votre code a dépassé le temps limite (3s).",
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Erreur système : {str(e)}",
        }


def grade_submission(student_code: str, exercise_id: str) -> dict:
    """Run all test cases and compute score out of 20."""
    exercise = EXERCISES.get(exercise_id)
    if not exercise:
        return {"score": 0, "max_score": 20, "details": [], "error": "Exercice inconnu."}

    # Safety check
    is_safe, safety_msg = check_code_safety(student_code)
    if not is_safe:
        return {
            "score": 0,
            "max_score": 20,
            "details": [{"test": "Sécurité", "passed": False, "message": safety_msg}],
            "error": safety_msg,
        }

    test_cases = exercise["test_cases"]
    total = len(test_cases)
    passed = 0
    details = []

    for i, tc in enumerate(test_cases, 1):
        result = run_student_code(student_code, tc["input"])

        if result["success"] and result["output"] == tc["expected"]:
            passed += 1
            details.append({
                "test": f"Test {i}",
                "passed": True,
                "input": tc["input"],
                "expected": tc["expected"],
                "got": result["output"],
                "message": "✅ Réussi",
            })
        else:
            msg = result["error"] if result["error"] else (
                f"Attendu: {tc['expected']} | Obtenu: {result['output']}"
            )
            details.append({
                "test": f"Test {i}",
                "passed": False,
                "input": tc["input"],
                "expected": tc["expected"],
                "got": result["output"] or "(erreur)",
                "message": f"❌ Échoué — {msg}",
            })

    score = round((passed / total) * 20, 2) if total > 0 else 0

    return {
        "score": score,
        "max_score": 20,
        "passed": passed,
        "total": total,
        "details": details,
        "error": "",
    }


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Page d'accueil - choix de l'exercice."""
    exercise_id = request.args.get("ex", "ex1_somme")
    exercise = EXERCISES.get(exercise_id, EXERCISES["ex1_somme"])
    return render_template(
        "index.html",
        exercises=EXERCISES,
        current_ex=exercise_id,
        exercise=exercise,
    )


@app.route("/submit", methods=["POST"])
def submit():
    """Endpoint API pour soumettre du code."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données invalides."}), 400

    student_name = data.get("student_name", "").strip()
    student_group = data.get("student_group", "").strip()
    exercise_id = data.get("exercise_id", "")
    code = data.get("code", "")

    if not student_name:
        return jsonify({"error": "Veuillez entrer votre nom."}), 400
    if not code.strip():
        return jsonify({"error": "Veuillez écrire du code."}), 400
    if exercise_id not in EXERCISES:
        return jsonify({"error": "Exercice invalide."}), 400

    # Grade the code
    result = grade_submission(code, exercise_id)

    # Save to DB
    submission = Submission(
        student_name=student_name,
        student_group=student_group,
        exercise_id=exercise_id,
        code=code,
        score=result["score"],
        max_score=result["max_score"],
        details=json.dumps(result["details"], ensure_ascii=False),
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify(result)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    """Espace professeur - tableau récapitulatif."""
    # Simple password protection
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            # Show results
            submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()
            return render_template(
                "admin.html",
                submissions=submissions,
                authenticated=True,
                exercises=EXERCISES,
            )
        else:
            flash("Mot de passe incorrect.", "error")
            return render_template("admin.html", authenticated=False)

    return render_template("admin.html", authenticated=False, exercises=EXERCISES)


@app.route("/admin/export")
def export_csv():
    """Export CSV de toutes les soumissions."""
    # In production, add proper auth check
    password = request.args.get("pwd", "")
    if password != ADMIN_PASSWORD:
        return "Non autorisé", 403

    submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "Étudiant", "Groupe", "Exercice", "Note", "/20",
        "Date de soumission", "Code soumis"
    ])

    for s in submissions:
        ex_title = EXERCISES.get(s.exercise_id, {}).get("title", s.exercise_id)
        writer.writerow([
            s.id,
            s.student_name,
            s.student_group,
            ex_title,
            s.score,
            s.max_score,
            s.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if s.submitted_at else "",
            s.code.replace("\n", "\\n"),
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=resultats_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        },
    )


@app.route("/admin/delete/<int:submission_id>", methods=["POST"])
def delete_submission(submission_id):
    """Supprimer une soumission."""
    password = request.form.get("pwd", "")
    if password != ADMIN_PASSWORD:
        return "Non autorisé", 403

    sub = Submission.query.get_or_404(submission_id)
    db.session.delete(sub)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/admin/stats")
def admin_stats():
    """API endpoint for quick stats."""
    password = request.args.get("pwd", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Non autorisé"}), 403

    total = Submission.query.count()
    avg_score = db.session.query(db.func.avg(Submission.score)).scalar() or 0
    unique_students = db.session.query(
        db.func.count(db.func.distinct(Submission.student_name))
    ).scalar() or 0

    return jsonify({
        "total_submissions": total,
        "average_score": round(avg_score, 2),
        "unique_students": unique_students,
    })


# ──────────────────────────────────────────────
# Init DB
# ──────────────────────────────────────────────
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
