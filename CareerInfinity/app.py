
from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)

# Allow your frontend to communicate with the backend
CORS(app)

@app.route("/")
def home():
    return jsonify({
        "message": "CareerInfinity backend is running!",
        "status": "success"
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "project": "CareerInfinity"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
