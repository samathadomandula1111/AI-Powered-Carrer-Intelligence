import io
import unittest
from unittest.mock import patch

from docx import Document
from google.auth.exceptions import GoogleAuthError, TransportError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import app


class ResumeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.valid_claims = {
            "iss": f"https://securetoken.google.com/{app.FIREBASE_PROJECT_ID}",
            "sub": "test-user",
        }
        self.token_verifier = patch.object(
            app, "verify_firebase_token", return_value=self.valid_claims
        )
        self.token_verifier.start()
        self.addCleanup(self.token_verifier.stop)
        self.headers = {"Authorization": "Bearer test-token"}

    @staticmethod
    def create_docx():
        document = Document()
        for paragraph in (
            "Alex Example alex@example.com",
            "Skills: Python, SQL, Git, Flask, Excel",
            "Education: Computer Science",
            "Experience: Built data analysis projects with Python and SQL.",
            "Projects: Resume analyzer dashboard.",
        ):
            document.add_paragraph(paragraph)
        content = io.BytesIO()
        document.save(content)
        return content.getvalue()

    @staticmethod
    def create_pdf():
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 72 720 Td (Python SQL) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        content = io.BytesIO()
        writer.write(content)
        return content.getvalue()

    def upload(self, content, filename):
        return self.client.post(
            "/api/analyze-resume",
            headers=self.headers,
            data={"resume": (io.BytesIO(content), filename)},
            content_type="multipart/form-data",
        )

    def test_docx_upload_returns_dashboard_response_shape(self):
        response = self.upload(self.create_docx(), "resume.docx")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(
            set(result),
            {
                "resume_score",
                "career_match_score",
                "profile_strength",
                "skills",
                "career_matches",
                "suggestions",
                "disclaimer",
            },
        )
        self.assertTrue(any(skill["name"] == "Python" for skill in result["skills"]))
        self.assertTrue(any(
            career["title"] == "Python Developer"
            for career in result["career_matches"]
        ))
        python_role = next(
            career
            for career in result["career_matches"]
            if career["title"] == "Python Developer"
        )
        self.assertIn("Python", python_role["matched_skills"])
        self.assertIn("Django", python_role["gaps"])

    def test_python_variants_match_python_developer_role(self):
        for resume_text in (
            "Skills: Python",
            "Skills: Python 3",
            "Skills: Python3",
            "Skills: Python 2",
        ):
            with self.subTest(resume_text=resume_text):
                result = app.analyze_resume(resume_text)
                self.assertTrue(any(
                    skill["name"] == "Python" for skill in result["skills"]
                ))
                python_role = next(
                    career for career in result["career_matches"]
                    if career["title"] == "Python Developer"
                )
                self.assertIn("Python", python_role["matched_skills"])

    def test_pdf_upload_extracts_text(self):
        response = self.upload(self.create_pdf(), "resume.pdf")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(
            skill["name"] == "Python"
            for skill in response.get_json()["skills"]
        ))

    def test_missing_authentication_is_rejected(self):
        response = self.client.post(
            "/api/analyze-resume",
            data={},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.get_json())

    def test_invalid_firebase_claims_are_rejected(self):
        with patch.object(
            app,
            "verify_firebase_token",
            return_value={"iss": "https://invalid.example", "sub": "test-user"},
        ):
            response = self.client.post(
                "/api/analyze-resume",
                headers=self.headers,
                data={},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_token_is_rejected(self):
        with patch.object(
            app,
            "verify_firebase_token",
            side_effect=GoogleAuthError("invalid token"),
        ):
            response = self.client.post(
                "/api/analyze-resume",
                headers=self.headers,
                data={},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.get_json())

    def test_authentication_service_failure_returns_unavailable(self):
        with patch.object(
            app,
            "verify_firebase_token",
            side_effect=TransportError("network unavailable"),
        ):
            response = self.client.post(
                "/api/analyze-resume",
                headers=self.headers,
                data={},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.get_json()["error"])

    def test_missing_or_unreadable_files_return_validation_errors(self):
        missing = self.client.post(
            "/api/analyze-resume",
            headers=self.headers,
            data={},
            content_type="multipart/form-data",
        )
        invalid_docx = self.upload(b"not a DOCX", "resume.docx")
        invalid_pdf = self.upload(b"not a PDF", "resume.pdf")

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid_docx.status_code, 400)
        self.assertEqual(invalid_pdf.status_code, 400)
        self.assertTrue(all(
            response.is_json
            for response in (missing, invalid_docx, invalid_pdf)
        ))

    def test_unsupported_file_type_is_rejected(self):
        response = self.upload(b"plain text", "resume.txt")

        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF or DOCX", response.get_json()["error"])

    def test_oversized_file_is_rejected(self):
        response = self.upload(
            b"x" * (app.MAX_RESUME_SIZE + 1),
            "resume.pdf",
        )

        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)

    def test_unknown_api_route_returns_json_not_found(self):
        response = self.client.get("/api/unknown")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.is_json)

    def test_backend_source_is_not_served_as_a_static_asset(self):
        response = self.client.get("/app.py")

        self.assertEqual(response.status_code, 404)

    def test_unexpected_api_failure_returns_safe_json_error(self):
        with patch("app.analyze_resume", side_effect=RuntimeError("internal detail")):
            response = self.upload(self.create_docx(), "resume.docx")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json(),
            {"error": "An unexpected server error occurred."},
        )

    def test_cors_is_limited_to_local_frontend_origins(self):
        allowed = self.client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5000"},
        )
        denied = self.client.get(
            "/api/health",
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(
            allowed.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:5000",
        )
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
