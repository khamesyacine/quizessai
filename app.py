"""
Python Test Platform v2 — avec support upload .ipynb
USTHB — Faculté des Sciences Biologiques
"""

import os
import io
import csv
import subprocess
import tempfile
import json
import re
import hashlib
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, Response, flash, abort
)
from flask_sqlalchemy import SQLAlchemy

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

database_url = os.environ.get("DATABASE_URL", "sqlite:///pytestapp.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB max upload

db = SQLAlchemy(app)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "prof2025")

# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────
class Notebook(db.Model):
    __tablename__ = "notebooks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    cells_json = db.Column(db.Text, nullable=False)  # All cells as JSON
    exercises_json = db.Column(db.Text, nullable=False)  # Extracted exercises with tests
    nb_exercises = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_cells(self):
        return json.loads(self.cells_json)

    def get_exercises(self):
        return json.loads(self.exercises_json)


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    student_group = db.Column(db.String(60), default="")
    notebook_slug = db.Column(db.String(100), nullable=False)
    exercise_id = db.Column(db.String(60), nullable=False)
    code = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, default=20.0)
    details = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class FullSubmission(db.Model):
    """Stores a complete notebook submission (all exercises at once)."""
    __tablename__ = "full_submissions"
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    student_group = db.Column(db.String(60), default="")
    notebook_slug = db.Column(db.String(100), nullable=False)
    total_score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, default=20.0)
    details_json = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────
# Built-in Exercises (legacy)
# ──────────────────────────────────────────────
EXERCISES = {
    "ex1_somme": {
        "title": "Exercice 1 : Fonction somme",
        "description": "Écrivez une fonction <code>somme(a, b)</code> qui retourne la somme de deux nombres.",
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
        "description": "Écrivez une fonction <code>est_pair(n)</code> qui retourne <code>True</code> si <code>n</code> est pair.",
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
        "description": "Écrivez une fonction <code>factorielle(n)</code> qui retourne la factorielle de <code>n</code>.",
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
        "description": "Écrivez une fonction <code>inverser(s)</code> qui retourne la chaîne inversée.",
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
        "description": "Écrivez une fonction <code>maximum(lst)</code> qui retourne le plus grand élément sans utiliser <code>max()</code>.",
        "template": "def maximum(lst):\n    # Votre code ici\n    pass\n",
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
        "description": "Écrivez une fonction <code>fibonacci(n)</code> qui retourne le n-ième terme de Fibonacci.",
        "template": "def fibonacci(n):\n    # Votre code ici\n    pass\n",
        "test_cases": [
            {"input": "print(fibonacci(0))", "expected": "0"},
            {"input": "print(fibonacci(1))", "expected": "1"},
            {"input": "print(fibonacci(6))", "expected": "8"},
            {"input": "print(fibonacci(10))", "expected": "55"},
        ],
    },
}


# ──────────────────────────────────────────────
# Notebook Parser
# ──────────────────────────────────────────────
def markdown_to_html(md_text):
    """Simple markdown to HTML converter for notebook cells."""
    import re
    html = md_text

    # Headers
    html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)

    # Code blocks
    html = re.sub(r'```(\w*)\n(.*?)```', r'<pre class="bg-gray-800 text-green-400 p-3 rounded-lg text-sm font-mono overflow-x-auto my-2"><code>\2</code></pre>', html, flags=re.DOTALL)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code class="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono">\1</code>', html)

    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Tables
    lines = html.split('\n')
    in_table = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if '|' in stripped and stripped.startswith('|'):
            cols = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(re.match(r'^[-:]+$', c) for c in cols):
                continue  # separator row
            if not in_table:
                new_lines.append('<div class="overflow-x-auto my-3"><table class="min-w-full text-sm border border-gray-200 rounded">')
                new_lines.append('<thead><tr>' + ''.join(f'<th class="px-3 py-2 bg-gray-50 border-b text-left font-semibold text-gray-700">{c}</th>' for c in cols) + '</tr></thead><tbody>')
                in_table = True
            else:
                new_lines.append('<tr>' + ''.join(f'<td class="px-3 py-2 border-b border-gray-100">{c}</td>' for c in cols) + '</tr>')
        else:
            if in_table:
                new_lines.append('</tbody></table></div>')
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append('</tbody></table></div>')
    html = '\n'.join(new_lines)

    # Lists
    html = re.sub(r'^- (.+)$', r'<li class="ml-4">\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li.*</li>\n?)+', lambda m: '<ul class="list-disc ml-4 my-2">' + m.group(0) + '</ul>', html)

    # Numbered lists
    html = re.sub(r'^\d+\. (.+)$', r'<li class="ml-4">\1</li>', html, flags=re.MULTILINE)

    # Blockquotes
    html = re.sub(r'^> (.+)$', r'<blockquote class="border-l-4 border-yellow-400 bg-yellow-50 pl-4 py-2 my-2 text-sm">\1</blockquote>', html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r'^---+$', r'<hr class="my-4 border-gray-300">', html, flags=re.MULTILINE)

    # Paragraphs (lines not already tagged)
    result_lines = []
    for line in html.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('<') and not stripped.startswith('|'):
            result_lines.append(f'<p class="my-1">{stripped}</p>')
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def parse_notebook(nb_json):
    """Parse a Jupyter notebook and extract cells + exercises."""
    cells_data = []
    exercises = []
    exercise_idx = 0

    nb_cells = nb_json.get("cells", [])

    for i, cell in enumerate(nb_cells):
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            html_content = markdown_to_html(source)
            is_exercise = bool(re.search(r'exercice\s*\d+', source, re.IGNORECASE))

            cell_data = {
                "type": "markdown",
                "html": html_content,
                "is_exercise": is_exercise,
                "raw": source,
            }

            if is_exercise:
                # Extract exercise number and description
                match = re.search(r'exercice\s*(\d+)', source, re.IGNORECASE)
                ex_num = match.group(1) if match else str(exercise_idx + 1)

                # Get the next code cell as template
                template = "# Votre code ici\n"
                if i + 1 < len(nb_cells) and nb_cells[i + 1]["cell_type"] == "code":
                    template = "".join(nb_cells[i + 1]["source"])

                exercise = {
                    "id": f"nb_ex{ex_num}",
                    "number": int(ex_num),
                    "title": f"Exercice {ex_num}",
                    "description_md": source,
                    "description_html": html_content,
                    "template": template,
                    "test_cases": [],  # Will be set by professor
                }
                exercises.append(exercise)
                cell_data["exercise_id"] = exercise["id"]
                exercise_idx += 1

            cells_data.append(cell_data)

        elif cell_type == "code":
            # Skip cells that are exercise templates (already captured)
            prev_is_exercise = (i > 0 and cells_data and cells_data[-1].get("is_exercise"))
            cells_data.append({
                "type": "code",
                "source": source,
                "is_template": prev_is_exercise,
                "exercise_id": cells_data[-1].get("exercise_id", "") if prev_is_exercise else "",
            })

    return cells_data, exercises


def generate_test_cases_for_exercise(exercise):
    """Generate automatic test cases based on exercise description."""
    desc = exercise["description_md"].lower()
    ex_num = exercise["number"]
    tests = []

    if ex_num == 1:
        tests = [
            {"input": "nb_leucocytes = 8200\nprint(type(nb_leucocytes).__name__)", "expected": "int"},
            {"input": "glycemie = 0.95\nprint(type(glycemie).__name__)", "expected": "float"},
            {"input": 'diagnostic = "Diabète type 2"\nprint(type(diagnostic).__name__)', "expected": "str"},
            {"input": "hospitalise = False\nprint(type(hospitalise).__name__)", "expected": "bool"},
        ]
    elif ex_num == 2:
        tests = [
            {"input": "poids = 92\ntaille = 1.68\nIMC = poids / (taille ** 2)\nprint(f'IMC du patient : {round(IMC, 1)} kg/m²')", "expected": "IMC du patient : 32.6 kg/m²"},
        ]
    elif ex_num == 3:
        tests = [
            {"input": 'hemoglobine = "13.2"\nprint(type(float(hemoglobine)).__name__)', "expected": "float"},
            {"input": 'globules_rouges = "4800000"\nprint(type(int(globules_rouges)).__name__)', "expected": "int"},
            {"input": 'groupe_sanguin = "A+"\nprint(type(groupe_sanguin).__name__)', "expected": "str"},
        ]
    elif ex_num == 4:
        tests = [
            {"input": "N0 = 1\nn = 10\nN = N0 * (2 ** n)\nprint(N)", "expected": "1024"},
        ]
    elif ex_num == 5:
        tests = [
            {"input": "r1, r2, r3 = 650, 820, 530\ntotal = r1 + r2 + r3\nprint(total)", "expected": "2000"},
            {"input": "r1, r2, r3 = 650, 820, 530\nmoyenne = (r1 + r2 + r3) / 3\nprint(round(moyenne, 1))", "expected": "666.7"},
        ]
    elif ex_num == 6:
        tests = [
            {"input": "print(10 > 5)", "expected": "True"},
            {"input": 'print("ADN" != "ARN")', "expected": "True"},
            {"input": "print(True and False)", "expected": "False"},
            {"input": "print(False or True)", "expected": "True"},
            {"input": "print(not (5 > 3))", "expected": "False"},
        ]
    elif ex_num == 7:
        tests = [
            {"input": "IgG = 12.5\nIgM = 0.8\nIgG_normal = IgG >= 7 and IgG <= 16\nIgM_normal = IgM >= 0.4 and IgM <= 2.3\nprint(IgG_normal and IgM_normal)", "expected": "True"},
        ]
    elif ex_num == 8:
        tests = [
            {"input": "glyc = 1.35\nprint(glyc > 1.1)", "expected": "True"},
            {"input": "IMC = 31.2\nprint(IMC >= 30)", "expected": "True"},
            {"input": "glyc = 1.35\nfumeur = True\nIMC = 31.2\nprint(glyc > 1.1 and fumeur and IMC >= 30)", "expected": "True"},
        ]

    return tests


# ──────────────────────────────────────────────
# Code Execution Engine
# ──────────────────────────────────────────────
FORBIDDEN_KEYWORDS = [
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import http", "import urllib", "import requests",
    "__import__", "eval(", "exec(", "open(", "compile(",
    "import signal", "import ctypes", "import pickle",
]


def check_code_safety(code):
    code_lower = code.lower().replace(" ", "")
    for keyword in FORBIDDEN_KEYWORDS:
        normalized = keyword.lower().replace(" ", "")
        if normalized in code_lower:
            return False, f"Code interdit : utilisation de '{keyword}' non autorisée."
    return True, ""


def run_student_code(student_code, test_input, timeout=3):
    full_code = student_code + "\n" + test_input
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(full_code)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            return {"success": True, "output": result.stdout.strip(), "error": ""}
        else:
            return {"success": False, "output": result.stdout.strip(), "error": result.stderr.strip()}

    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return {"success": False, "output": "", "error": "⏱ Timeout (3s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def grade_submission_legacy(student_code, exercise_id):
    """Grade built-in exercises."""
    exercise = EXERCISES.get(exercise_id)
    if not exercise:
        return {"score": 0, "max_score": 20, "details": [], "error": "Exercice inconnu."}

    is_safe, msg = check_code_safety(student_code)
    if not is_safe:
        return {"score": 0, "max_score": 20, "details": [{"test": "Sécurité", "passed": False, "message": msg}], "error": msg}

    test_cases = exercise["test_cases"]
    total = len(test_cases)
    passed = 0
    details = []

    for i, tc in enumerate(test_cases, 1):
        result = run_student_code(student_code, tc["input"])
        if result["success"] and result["output"] == tc["expected"]:
            passed += 1
            details.append({"test": f"Test {i}", "passed": True, "input": tc["input"], "expected": tc["expected"], "got": result["output"], "message": "✅ Réussi"})
        else:
            msg = result["error"] if result["error"] else f"Attendu: {tc['expected']} | Obtenu: {result['output']}"
            details.append({"test": f"Test {i}", "passed": False, "input": tc["input"], "expected": tc["expected"], "got": result["output"] or "(erreur)", "message": f"❌ Échoué — {msg}"})

    score = round((passed / total) * 20, 2) if total > 0 else 0
    return {"score": score, "max_score": 20, "passed": passed, "total": total, "details": details, "error": ""}


def grade_notebook_exercise(student_code, test_cases):
    """Grade a notebook exercise."""
    is_safe, msg = check_code_safety(student_code)
    if not is_safe:
        return {"score": 0, "details": [{"test": "Sécurité", "passed": False, "message": msg}], "error": msg}

    if not test_cases:
        return {"score": 0, "details": [{"test": "Config", "passed": False, "message": "Aucun test configuré"}], "error": "Pas de tests"}

    total = len(test_cases)
    passed = 0
    details = []

    for i, tc in enumerate(test_cases, 1):
        result = run_student_code(student_code, tc["input"])
        if result["success"] and result["output"].strip() == tc["expected"].strip():
            passed += 1
            details.append({"test": f"Test {i}", "passed": True, "input": tc["input"], "expected": tc["expected"], "got": result["output"], "message": "✅ Réussi"})
        else:
            msg = result["error"] if result["error"] else f"Attendu: {tc['expected']} | Obtenu: {result['output']}"
            details.append({"test": f"Test {i}", "passed": False, "input": tc["input"], "expected": tc["expected"], "got": result["output"] or "(erreur)", "message": f"❌ — {msg}"})

    return {"passed": passed, "total": total, "details": details}


# ──────────────────────────────────────────────
# Routes — Student
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Home page — list of available TPs and exercises."""
    notebooks = Notebook.query.filter_by(is_active=True).order_by(Notebook.created_at.desc()).all()
    exercise_id = request.args.get("ex", "ex1_somme")
    exercise = EXERCISES.get(exercise_id, EXERCISES["ex1_somme"])
    return render_template("index.html",
        exercises=EXERCISES, current_ex=exercise_id, exercise=exercise,
        notebooks=notebooks)


@app.route("/tp/<slug>")
def view_notebook(slug):
    """View a notebook TP with embedded exercises."""
    notebook = Notebook.query.filter_by(slug=slug, is_active=True).first_or_404()
    cells = notebook.get_cells()
    exercises = notebook.get_exercises()
    return render_template("notebook.html", notebook=notebook, cells=cells, exercises=exercises)


@app.route("/submit", methods=["POST"])
def submit():
    """Submit code for built-in exercises."""
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

    result = grade_submission_legacy(code, exercise_id)

    sub = Submission(
        student_name=student_name, student_group=student_group,
        notebook_slug="builtin", exercise_id=exercise_id,
        code=code, score=result["score"], max_score=result["max_score"],
        details=json.dumps(result["details"], ensure_ascii=False),
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify(result)


@app.route("/submit_notebook", methods=["POST"])
def submit_notebook():
    """Submit all exercises for a notebook TP."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données invalides."}), 400

    student_name = data.get("student_name", "").strip()
    student_group = data.get("student_group", "").strip()
    notebook_slug = data.get("notebook_slug", "")
    answers = data.get("answers", {})  # {exercise_id: code}

    if not student_name:
        return jsonify({"error": "Veuillez entrer votre nom."}), 400

    notebook = Notebook.query.filter_by(slug=notebook_slug, is_active=True).first()
    if not notebook:
        return jsonify({"error": "TP introuvable."}), 404

    exercises = notebook.get_exercises()
    if not exercises:
        return jsonify({"error": "Aucun exercice dans ce TP."}), 400

    total_points = 0
    total_possible = 0
    all_details = []

    for ex in exercises:
        ex_id = ex["id"]
        code = answers.get(ex_id, "").strip()
        test_cases = ex.get("test_cases", [])

        if not code or code == ex.get("template", "").strip():
            # Not answered
            all_details.append({
                "exercise_id": ex_id,
                "title": ex["title"],
                "passed": 0,
                "total": len(test_cases),
                "details": [{"test": "Non répondu", "passed": False, "message": "❌ Exercice non répondu"}],
            })
            total_possible += len(test_cases) if test_cases else 1
            continue

        if test_cases:
            result = grade_notebook_exercise(code, test_cases)
            total_points += result["passed"]
            total_possible += result["total"]
            all_details.append({
                "exercise_id": ex_id,
                "title": ex["title"],
                "passed": result["passed"],
                "total": result["total"],
                "details": result["details"],
            })

            # Save individual submission
            sub = Submission(
                student_name=student_name, student_group=student_group,
                notebook_slug=notebook_slug, exercise_id=ex_id,
                code=code,
                score=round((result["passed"] / result["total"]) * 20, 2) if result["total"] > 0 else 0,
                max_score=20.0,
                details=json.dumps(result["details"], ensure_ascii=False),
            )
            db.session.add(sub)
        else:
            all_details.append({
                "exercise_id": ex_id,
                "title": ex["title"],
                "passed": 0, "total": 0,
                "details": [{"test": "Info", "passed": True, "message": "ℹ️ Pas de tests auto — correction manuelle"}],
            })

    # Compute final score /20
    final_score = round((total_points / total_possible) * 20, 2) if total_possible > 0 else 0

    # Save full submission
    full_sub = FullSubmission(
        student_name=student_name, student_group=student_group,
        notebook_slug=notebook_slug,
        total_score=final_score, max_score=20.0,
        details_json=json.dumps(all_details, ensure_ascii=False),
    )
    db.session.add(full_sub)
    db.session.commit()

    return jsonify({
        "score": final_score,
        "max_score": 20,
        "total_points": total_points,
        "total_possible": total_possible,
        "exercises": all_details,
    })


# ──────────────────────────────────────────────
# Routes — Admin
# ──────────────────────────────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()
            full_submissions = FullSubmission.query.order_by(FullSubmission.submitted_at.desc()).all()
            notebooks = Notebook.query.order_by(Notebook.created_at.desc()).all()
            return render_template("admin.html",
                submissions=submissions, full_submissions=full_submissions,
                notebooks=notebooks, authenticated=True,
                exercises=EXERCISES, password=password)
        else:
            flash("Mot de passe incorrect.", "error")
    return render_template("admin.html", authenticated=False, exercises=EXERCISES)


@app.route("/admin/upload", methods=["POST"])
def upload_notebook():
    """Upload a .ipynb file and create a TP."""
    password = request.form.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Non autorisé"}), 403

    file = request.files.get("notebook")
    if not file or not file.filename.endswith(".ipynb"):
        flash("Veuillez sélectionner un fichier .ipynb", "error")
        return redirect(url_for("admin"))

    try:
        content = file.read().decode("utf-8")
        nb_json = json.loads(content)
    except Exception as e:
        flash(f"Erreur de lecture du fichier : {e}", "error")
        return redirect(url_for("admin"))

    # Parse notebook
    cells_data, exercises = parse_notebook(nb_json)

    # Generate test cases
    for ex in exercises:
        ex["test_cases"] = generate_test_cases_for_exercise(ex)

    # Create title and slug
    title = request.form.get("title", "").strip()
    if not title:
        # Try to extract from first cell
        for cell in nb_json.get("cells", []):
            if cell["cell_type"] == "markdown":
                src = "".join(cell["source"])
                match = re.search(r'^#\s+(.+)$', src, re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                    # Clean emoji
                    title = re.sub(r'[^\w\s\-—àâäéèêëïîôùûüç]', '', title).strip()
                    break
    if not title:
        title = file.filename.replace(".ipynb", "")

    slug = re.sub(r'[^a-z0-9]+', '-', title.lower().strip())[:80].strip('-')
    # Ensure unique slug
    existing = Notebook.query.filter_by(slug=slug).first()
    if existing:
        slug = slug + "-" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]

    description = request.form.get("description", "").strip()

    notebook = Notebook(
        title=title,
        slug=slug,
        description=description,
        cells_json=json.dumps(cells_data, ensure_ascii=False),
        exercises_json=json.dumps(exercises, ensure_ascii=False),
        nb_exercises=len(exercises),
    )
    db.session.add(notebook)
    db.session.commit()

    flash(f"✅ TP «{title}» uploadé avec succès ! ({len(exercises)} exercices détectés)", "success")
    return redirect(url_for("admin"))


@app.route("/admin/notebook/<int:nb_id>/edit", methods=["POST"])
def edit_notebook_tests(nb_id):
    """Edit test cases for a notebook exercise."""
    password = request.form.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Non autorisé"}), 403

    notebook = Notebook.query.get_or_404(nb_id)
    exercises = notebook.get_exercises()

    exercise_id = request.form.get("exercise_id", "")
    tests_json = request.form.get("tests_json", "[]")

    try:
        new_tests = json.loads(tests_json)
    except json.JSONDecodeError:
        return jsonify({"error": "JSON invalide"}), 400

    for ex in exercises:
        if ex["id"] == exercise_id:
            ex["test_cases"] = new_tests
            break

    notebook.exercises_json = json.dumps(exercises, ensure_ascii=False)
    db.session.commit()

    return jsonify({"success": True, "message": "Tests mis à jour"})


@app.route("/admin/notebook/<int:nb_id>/delete", methods=["POST"])
def delete_notebook(nb_id):
    password = request.form.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Non autorisé"}), 403

    notebook = Notebook.query.get_or_404(nb_id)
    db.session.delete(notebook)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/admin/notebook/<int:nb_id>/toggle", methods=["POST"])
def toggle_notebook(nb_id):
    password = request.form.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Non autorisé"}), 403

    notebook = Notebook.query.get_or_404(nb_id)
    notebook.is_active = not notebook.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": notebook.is_active})


@app.route("/admin/export")
def export_csv():
    password = request.args.get("pwd", "")
    if password != ADMIN_PASSWORD:
        return "Non autorisé", 403

    # Export full submissions (notebook TPs)
    full_subs = FullSubmission.query.order_by(FullSubmission.submitted_at.desc()).all()
    legacy_subs = Submission.query.filter_by(notebook_slug="builtin").order_by(Submission.submitted_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Étudiant", "Groupe", "TP/Exercice", "Note", "/20", "Date"])

    for s in full_subs:
        nb = Notebook.query.filter_by(slug=s.notebook_slug).first()
        tp_name = nb.title if nb else s.notebook_slug
        writer.writerow([
            s.id, s.student_name, s.student_group, tp_name,
            s.total_score, s.max_score,
            s.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if s.submitted_at else "",
        ])

    for s in legacy_subs:
        ex_title = EXERCISES.get(s.exercise_id, {}).get("title", s.exercise_id)
        writer.writerow([
            f"L{s.id}", s.student_name, s.student_group, ex_title,
            s.score, s.max_score,
            s.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if s.submitted_at else "",
        ])

    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=resultats_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"})


# ──────────────────────────────────────────────
# Init DB
# ──────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
