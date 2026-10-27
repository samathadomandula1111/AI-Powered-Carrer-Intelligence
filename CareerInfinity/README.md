# CareerInfinity

CareerInfinity is a small Flask application with static HTML pages and Firebase
Authentication. Its resume analyzer extracts text from PDF and DOCX uploads and
returns keyword-based career suggestions.

## Run locally (Windows PowerShell)

```powershell
cd CareerInfinity
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000/`. The dashboard is at
`http://127.0.0.1:5000/dashboard`. The server binds to loopback and runs with
debug mode disabled by default.

The static pages use the Firebase web-app configuration in `index.html` and
`dashboard.html`. Firebase web API keys identify a web app; they are not server
credentials. Restrict the key to the intended APIs and authorized domains in
the Firebase/Google Cloud console. The backend verifies Firebase ID tokens
against `FIREBASE_PROJECT_ID` and does not require service-account credentials.

Copy `.env.example` to `.env` as a reference, then set the variables in your
shell or hosting environment. `FIREBASE_PROJECT_ID` must match the `projectId`
in both HTML pages. Flask does not automatically load `.env`.
`CORS_ORIGINS` is a comma-separated allowlist for a separately hosted frontend;
the default allows the two local Flask origins. Keep any added origins specific
to the frontend hosts you control.

## Data and API

- `GET /api/health` reports whether Flask is responding.
- `POST /api/analyze-resume` accepts a signed-in user's `resume` PDF or DOCX,
  up to 5 MB, and returns resume, profile, and skill estimates plus ranked
  career matches with detected skills and skills to improve for each role.
- Uploaded files are processed in memory and are not stored by the backend.
- Learning progress, placement opportunities, and certificate names are saved
  in browser local storage, scoped to the signed-in Firebase user on that
  browser. This project has no database configured; this data does not sync
  between devices.

The resume scores and skill matches are heuristics, not formal assessments.
Scanned/image-only PDFs need OCR, which is not included.

## Tests

```powershell
python -m unittest discover -s . -p "*test.py" -v
```
