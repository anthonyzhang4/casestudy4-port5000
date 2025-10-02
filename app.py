from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    # ADD: convert to dict so we can modify values before creating StoredSurveyRecord
    record_data = submission.dict()

    # ADD: hash PII fields
    record_data["email"] = sha256_hash(record_data["email"])
    record_data["age"] = sha256_hash(str(record_data["age"]))

    # ADD: user_agent from request headers
    record_data["user_agent"] = request.headers.get("User-Agent", "")

    # ADD: generate submission_id if missing
    if not record_data.get("submission_id"):
        original_email = payload.get("email", "")   # use raw email, not hashed
        now_str = datetime.utcnow().strftime("%Y%m%d%H")
        record_data["submission_id"] = sha256_hash(original_email + now_str)

    # ADD: add received_at and ip address
    record_data["received_at"] = datetime.now(timezone.utc)
    record_data["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr or "")

    # ADD: now create StoredSurveyRecord with the modified data
    record = StoredSurveyRecord(**record_data)

    append_json_line(record.dict())
    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=5000, debug=True)

