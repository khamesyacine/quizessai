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


def execute_code_for_output(code):
    """Execute a code cell and return its stdout output."""
    if not code.strip():
        return ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        os.unlink(tmp_path)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return ""


def parse_notebook(nb_json):
    """Parse a Jupyter notebook. ALL code cells become evaluable exercises."""
    cells_data = []
    exercises = []
    code_cell_idx = 0

    nb_cells = nb_json.get("cells", [])

    # Get the markdown context before each code cell for descriptions
    last_markdown_html = ""
    last_markdown_raw = ""

    for i, cell in enumerate(nb_cells):
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            html_content = markdown_to_html(source)
            last_markdown_html = html_content
            last_markdown_raw = source

            cells_data.append({
                "type": "markdown",
                "html": html_content,
                "is_exercise": False,
                "raw": source,
            })

        elif cell_type == "code":
            code = source.strip()
            code_cell_idx += 1

            # Determine if this is an empty/template cell (student exercise)
            is_student_cell = (
                not code
                or code.startswith("# Votre code")
                or code.startswith("# Vérifiez")
                or (code.count("\n") == 0 and code.startswith("#"))
            )

            # Check if there are existing outputs in the notebook
            expected_output = ""
            for o in cell.get("outputs", []):
                if "text" in o:
                    expected_output = "".join(o["text"]).strip()
                elif "data" in o and "text/plain" in o["data"]:
                    expected_output = "".join(o["data"]["text/plain"]).strip()

            # If no saved output, execute to get expected output
            if not expected_output and code and not is_student_cell:
                expected_output = execute_code_for_output(code)

            # Create exercise ID
            ex_id = f"code_{code_cell_idx}"

            # Build test case: the test is simply running the code and checking stdout
            test_cases = []
            if expected_output and not is_student_cell:
                # The test: run student code, expect the same output
                test_cases.append({
                    "input": "",  # No extra input needed — the code itself is the test
                    "expected": expected_output,
                })

            # Determine a short title from context
            title = f"Cellule {code_cell_idx}"
            if is_student_cell:
                # Check if previous markdown has exercise info
                match = re.search(r'exercice\s*(\d+)', last_markdown_raw, re.IGNORECASE)
                if match:
                    title = f"Exercice {match.group(1)}"
                else:
                    title = f"Exercice (cellule {code_cell_idx})"

            exercise = {
                "id": ex_id,
                "number": code_cell_idx,
                "title": title,
                "description_html": last_markdown_html if is_student_cell else "",
                "template": code if not is_student_cell else code,
                "expected_output": expected_output,
                "test_cases": test_cases,
                "is_student_cell": is_student_cell,
                "is_example": not is_student_cell and bool(expected_output),
            }
            exercises.append(exercise)

            cells_data.append({
                "type": "code",
                "source": code,
                "exercise_id": ex_id,
                "is_student_cell": is_student_cell,
                "is_example": not is_student_cell,
                "expected_output": expected_output,
            })

    return cells_data, exercises


def generate_test_cases_for_exercise(exercise):
    """Auto-generate test cases — tests are already created during parsing."""
    return exercise.get("test_cases", [])


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


def grade_notebook_exercise(student_code, test_cases, is_example=False):
    """Grade a notebook exercise.
    For example cells: the student code is executed directly and output is compared.
    For student cells: test cases are run after the student code.
    """
    is_safe, msg = check_code_safety(student_code)
    if not is_safe:
        return {"score": 0, "passed": 0, "total": 1, "details": [{"test": "Sécurité", "passed": False, "message": msg}], "error": msg}

    if not test_cases:
        # No test cases — just check the code runs without error
        result = run_student_code(student_code, "")
        if result["success"]:
            return {"passed": 1, "total": 1, "details": [{"test": "Exécution", "passed": True, "input": "", "expected": "(code exécuté)", "got": result["output"], "message": "✅ Code exécuté sans erreur"}]}
        else:
            return {"passed": 0, "total": 1, "details": [{"test": "Exécution", "passed": False, "input": "", "expected": "(sans erreur)", "got": result["error"], "message": f"❌ Erreur — {result['error'][:200]}"}]}

    total = len(test_cases)
    passed = 0
    details = []

    for i, tc in enumerate(test_cases, 1):
        test_input = tc.get("input", "")

        if is_example and not test_input:
            # For example cells: the student code IS the program, run it directly
            result = run_student_code(student_code, "")
        else:
            result = run_student_code(student_code, test_input)

        expected = tc["expected"].strip()
        got = result["output"].strip()

        if result["success"] and got == expected:
            passed += 1
            details.append({"test": f"Test {i}", "passed": True, "input": test_input or "(exécution directe)", "expected": expected, "got": got, "message": "✅ Réussi"})
        else:
            err_msg = result["error"] if result["error"] else f"Attendu: {expected} | Obtenu: {got}"
            details.append({"test": f"Test {i}", "passed": False, "input": test_input or "(exécution directe)", "expected": expected, "got": got or "(erreur)", "message": f"❌ — {err_msg[:200]}"})

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


@app.route("/run", methods=["POST"])
def run_code():
    """Execute a single code cell and return the output (no grading)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données invalides."}), 400

    code = data.get("code", "").strip()
    if not code:
        return jsonify({"output": "", "error": "Code vide."})

    is_safe, msg = check_code_safety(code)
    if not is_safe:
        return jsonify({"output": "", "error": msg})

    result = run_student_code(code, "", timeout=3)
    return jsonify({
        "output": result["output"],
        "error": result["error"],
        "success": result["success"],
    })


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

        if test_cases or not ex.get("is_student_cell", False):
            is_example = ex.get("is_example", False)
            result = grade_notebook_exercise(code, test_cases, is_example=is_example)
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
