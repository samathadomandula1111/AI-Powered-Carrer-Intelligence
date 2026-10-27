
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from io import BytesIO
import os
import re
from zipfile import BadZipFile

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_firebase_token
from lxml.etree import XMLSyntaxError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from werkzeug.exceptions import HTTPException

app = Flask(__name__, static_folder=None)
MAX_RESUME_SIZE = 5 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_RESUME_SIZE + 128 * 1024
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "carrerinfinity-28ab1")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000",
    ).split(",")
    if origin.strip()
]

CORS(app, origins=ALLOWED_ORIGINS)

SKILL_ALIASES = {
    "Python": ("python", "python 3", "python3", "python 2", "python2"),
    "Java": ("java",),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript",),
    "SQL": ("sql",),
    "HTML": ("html",),
    "CSS": ("css",),
    "React": ("react",),
    "Node.js": ("node.js", "nodejs"),
    "Flask": ("flask",),
    "Django": ("django",),
    "Git": ("git",),
    "Docker": ("docker",),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "Google Cloud": ("google cloud", "gcp"),
    "Machine Learning": ("machine learning", "ml"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "Data Analysis": ("data analysis", "data analytics"),
    "Excel": ("excel", "microsoft excel"),
    "Power BI": ("power bi",),
    "Communication": ("communication",),
    "Leadership": ("leadership",),
}

CAREER_PROFILES = (
    ("Python Developer", ("Python", "SQL", "Git", "Flask", "Django")),
    ("Data Analyst", ("SQL", "Excel", "Power BI", "Python", "Data Analysis")),
    ("Frontend Developer", ("HTML", "CSS", "JavaScript", "React")),
    ("Machine Learning Engineer", ("Python", "Machine Learning", "TensorFlow", "PyTorch", "SQL")),
    ("Cloud Support Associate", ("AWS", "Azure", "Google Cloud", "Docker", "Git")),
)


def extract_resume_text(filename, content):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if extension == "pdf":
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif extension == "docx":
            document = Document(BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            paragraphs.extend(
                cell.text
                for table in document.tables
                for row in table.rows
                for cell in row.cells
            )
            text = "\n".join(paragraphs)
        else:
            raise ValueError("Please upload a PDF or DOCX resume.")
    except (BadZipFile, PackageNotFoundError, PdfReadError, XMLSyntaxError) as error:
        raise ValueError("The file is invalid or could not be read.") from error

    text = text.strip()
    if not text:
        raise ValueError("No readable text was found in the resume.")
    return text


def analyze_resume(text):
    normalized_text = text.lower()
    skills = []
    for name, aliases in SKILL_ALIASES.items():
        count = sum(
            len(re.findall(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized_text))
            for alias in aliases
        )
        if count:
            level = "Frequently mentioned" if count >= 4 else "Repeated" if count >= 2 else "Mentioned"
            skills.append({
                "name": name,
                "level": level,
                "score": min(100, 40 + count * 15),
            })

    skill_names = {skill["name"] for skill in skills}
    career_matches = []
    for title, required_skills in CAREER_PROFILES:
        matched = [skill for skill in required_skills if skill in skill_names]
        gaps = [skill for skill in required_skills if skill not in skill_names]
        career_matches.append({
            "title": title,
            "match": round(len(matched) / len(required_skills) * 100),
            "reason": f"Matched {len(matched)} of {len(required_skills)} core skills in your resume.",
            "matched_skills": matched,
            "required_skills": list(required_skills),
            "gaps": gaps,
        })
    career_matches.sort(key=lambda career: career["match"], reverse=True)

    suggestions = []
    if len(text) < 500:
        suggestions.append("Add more detail about your experience, projects, and achievements.")
    if not re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text):
        suggestions.append("Include a professional email address in your contact information.")
    for section, pattern in (
        ("education", r"\beducation\b"),
        ("experience", r"\b(experience|employment|work history)\b"),
        ("projects", r"\bprojects?\b"),
    ):
        if not re.search(pattern, normalized_text):
            suggestions.append(f"Consider adding an {section} section.")
    if not skills:
        suggestions.append("Include a clearly labeled skills section with your relevant technologies.")
    if not suggestions:
        suggestions.append("Keep your resume tailored to each role and quantify your achievements.")

    section_score = sum(
        bool(re.search(pattern, normalized_text))
        for pattern in (
            r"\beducation\b",
            r"\b(experience|employment|work history)\b",
            r"\bprojects?\b",
            r"\bskills?\b",
        )
    )
    contact_score = bool(re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text))
    resume_score = min(
        100,
        section_score * 10 + int(contact_score) * 15
        + min(len(skills), 5) * 5 + min(20, len(text) // 100),
    )
    profile_strength = min(
        100,
        section_score * 15 + int(contact_score) * 20 + min(len(skills), 5) * 4,
    )
    best_match = career_matches[0]["match"] if career_matches else 0

    return {
        "resume_score": resume_score,
        "career_match_score": best_match,
        "profile_strength": profile_strength,
        "skills": skills,
        "career_matches": career_matches,
        "suggestions": suggestions,
        "disclaimer": "Scores and keyword matches are estimates, not a formal assessment.",
    }


@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory('.', 'index.html')


@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    return send_from_directory('.', 'dashboard.html')

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "project": "CareerInfinity"
    })


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": error.description}), error.code
    return error


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled application error")
    if request.path.startswith("/api/"):
        return jsonify({"error": "An unexpected server error occurred."}), 500
    return "An unexpected server error occurred.", 500


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Maximum resume size is 5 MB."}), 413


@app.route("/api/analyze-resume", methods=["POST"])
def analyze_resume_upload():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return jsonify({"error": "Please sign in before uploading a resume."}), 401
    token = authorization[7:].strip()
    if not token:
        return jsonify({"error": "Please sign in before uploading a resume."}), 401
    try:
        decoded_token = verify_firebase_token(
            token,
            Request(),
            audience=FIREBASE_PROJECT_ID,
        )
    except TransportError:
        return jsonify({"error": "Authentication verification is temporarily unavailable. Please try again."}), 503
    except (GoogleAuthError, ValueError):
        return jsonify({"error": "Your sign-in session is invalid or expired. Please sign in again."}), 401
    if (
        decoded_token.get("iss") != f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        or not decoded_token.get("sub")
    ):
        return jsonify({"error": "Your sign-in session is invalid or expired. Please sign in again."}), 401

    resume = request.files.get("resume")
    if resume is None or not resume.filename:
        return jsonify({"error": "Choose a resume to upload."}), 400

    content = resume.read(MAX_RESUME_SIZE + 1)
    if len(content) > MAX_RESUME_SIZE:
        return jsonify({"error": "Maximum resume size is 5 MB."}), 413

    try:
        text = extract_resume_text(resume.filename, content)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(analyze_resume(text))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)
