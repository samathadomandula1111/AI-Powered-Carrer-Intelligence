
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from io import BytesIO

app = Flask(__name__)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}

# Sample jobs for CareerInfinity
JOBS = [
    {
        "title": "Python Developer Intern",
        "company": "Example Technology Company",
        "skills": ["Python", "Flask", "SQL"],
        "location": "Hyderabad",
        "type": "Internship",
        "apply_url": "https://www.linkedin.com/jobs/"
    },
    {
        "title": "Data Analyst Intern",
        "company": "Example Analytics Company",
        "skills": ["Python", "SQL", "Excel"],
        "location": "Remote",
        "type": "Internship",
        "apply_url": "https://www.linkedin.com/jobs/"
    },
    {
        "title": "Frontend Developer Intern",
        "company": "Example Software Company",
        "skills": ["HTML", "CSS", "JavaScript"],
        "location": "Hyderabad",
        "type": "Internship",
        "apply_url": "https://www.linkedin.com/jobs/"
    },
    {
        "title": "AI Developer Intern",
        "company": "Example AI Company",
        "skills": ["Python", "Machine Learning", "SQL"],
        "location": "Remote",
        "type": "Internship",
        "apply_url": "https://www.linkedin.com/jobs/"
    }
]

# Free learning and certification resources
CERTIFICATIONS = [
    {
        "name": "Python Programming",
        "provider": "Infosys Springboard",
        "skills": ["Python", "Programming"],
        "url": "https://infyspringboard.onwingspan.com/"
    },
    {
        "name": "AI and Machine Learning",
        "provider": "IBM SkillsBuild",
        "skills": ["AI", "Machine Learning"],
        "url": "https://skillsbuild.org/"
    },
    {
        "name": "Cloud Computing",
        "provider": "Google Cloud Skills Boost",
        "skills": ["Cloud", "Google Cloud"],
        "url": "https://www.cloudskillsboost.google/"
    },
    {
        "name": "Web Development",
        "provider": "freeCodeCamp",
        "skills": ["HTML", "CSS", "JavaScript"],
        "url": "https://www.freecodecamp.org/learn/"
    }
]


def serve_html(filename):
    return send_file(
        os.path.join(app.root_path, filename),
        mimetype="text/html"
    )


@app.route("/", methods=["GET"])
def home():
    return serve_html("index.html")


@app.route("/index.html", methods=["GET"])
def index_page():
    return serve_html("index.html")


@app.route("/dashboard", methods=["GET"])
@app.route("/dashboard.html", methods=["GET"])
def dashboard_page():
    return serve_html("dashboard.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "project": "CareerInfinity"
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    return jsonify({
        "success": True,
        "count": len(JOBS),
        "jobs": JOBS
    })


@app.route("/api/jobs/recommend", methods=["POST"])
def recommend_jobs():
    data = request.get_json(silent=True) or {}
    user_skills = data.get("skills", [])

    if not isinstance(user_skills, list):
        return jsonify({
            "success": False,
            "error": "Skills must be provided as a list."
        }), 400

    user_skills = {
        str(skill).strip().lower()
        for skill in user_skills
        if isinstance(skill, str) and skill.strip()
    }

    results = []

    for job in JOBS:
        required = {
            skill.lower() for skill in job["skills"]
        }
        matched = sorted(user_skills & required)

        score = round(
            len(matched) / len(required) * 100
        ) if required else 0

        results.append({
            **job,
            "matched_skills": matched,
            "match_percentage": score
        })

    results.sort(
        key=lambda job: job["match_percentage"],
        reverse=True
    )

    return jsonify({
        "success": True,
        "recommendations": results
    })


@app.route("/api/analyze-resume", methods=["POST"])
@app.route("/api/resume/analyze", methods=["POST"])
def analyze_resume():
    if "resume" not in request.files:
        return jsonify({
            "success": False,
            "error": "Please upload a PDF resume."
        }), 400

    file = request.files["resume"]

    if not file.filename:
        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    filename = secure_filename(file.filename)

    if not filename.lower().endswith(".pdf"):
        return jsonify({
            "success": False,
            "error": "Only PDF resumes are supported."
        }), 400

    try:
        pdf_data = file.read()

        if not pdf_data:
            return jsonify({
                "success": False,
                "error": "The uploaded file is empty."
            }), 400

        reader = PdfReader(BytesIO(pdf_data))

        if reader.is_encrypted:
            return jsonify({
                "success": False,
                "error": "Please upload an unlocked PDF."
            }), 400

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        ).strip()

        if not text:
            return jsonify({
                "success": False,
                "error": (
                    "No readable text found. "
                    "Please upload a text-based PDF."
                )
            }), 400

        text_lower = text.lower()

        skill_keywords = [
            "python", "java", "sql", "html", "css",
            "javascript", "flask", "machine learning",
            "artificial intelligence", "excel",
            "communication", "git", "cloud"
        ]

        found_skills = [
            skill for skill in skill_keywords
            if skill in text_lower
        ]

        suggestions = []

        if not any(word in text_lower for word in
                   ["education", "degree", "bachelor"]):
            suggestions.append(
                "Add a clear education section if applicable."
            )

        if not any(word in text_lower for word in
                   ["project", "projects"]):
            suggestions.append(
                "Include relevant academic or personal projects."
            )

        if not any(word in text_lower for word in
                   ["experience", "internship"]):
            suggestions.append(
                "Add relevant internship or practical experience, "
                "if available."
            )

        if not found_skills:
            suggestions.append(
                "Add a skills section with your actual technical skills."
            )

        return jsonify({
            "success": True,
            "filename": filename,
            "pages": len(reader.pages),
            "extracted_text_length": len(text),
            "detected_skills": found_skills,
            "suggestions": suggestions,
            "analysis_type": "Basic rule-based analysis",
            "notice": (
                "This is a basic automated review, not an AI "
                "assessment or validated ATS score."
            )
        })

    except Exception:
        app.logger.exception("Resume analysis failed")
        return jsonify({
            "success": False,
            "error": (
                "Could not read this PDF. Please check "
                "the file and try again."
            )
        }), 400


@app.route("/api/certifications", methods=["GET"])
def get_certifications():
    return jsonify({
        "success": True,
        "count": len(CERTIFICATIONS),
        "certifications": CERTIFICATIONS
    })


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "success": False,
        "error": "File too large. Maximum size is 5 MB."
    }), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
