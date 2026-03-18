from flask import Flask, render_template, request, flash, redirect, url_for
import sys
import os
import pandas as pd
from werkzeug.utils import secure_filename

# root path ekliyoruz ki services import edilebilsin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.inference_service import perform_inference
from services.base_payload import BASE_PATIENT_PAYLOAD
from validators.patient_form_parser import parse_patient_form

app = Flask(__name__)
app.secret_key = 'capsico_inference_secret_key_2026'

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'inputs')
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        # Parse and validate the submitted form values.
        # overrides  – clean, type-correct values ready to apply to the payload
        # raw_values – original strings for re-populating the form on errors
        # errors     – field-keyed error messages; empty means the form is valid
        overrides, raw_values, errors = parse_patient_form(request.form)

        if errors:
            # Re-render the form with preserved input and clear error messages.
            # raw_values acts as prefill_data so the user does not lose their input.
            return render_template(
                "index.html",
                prefill_data=raw_values,
                form_errors=errors,
            ), 422

        # Validation passed — build the full payload from the baseline and apply
        # only the fields the user actually provided.
        payload = BASE_PATIENT_PAYLOAD.copy()
        payload.update(overrides)

        result = perform_inference(input_data=payload)

        if not result["success"]:
            return (
                f"<h2>Inference Error</h2><pre>{result['error']}</pre>"
                f"<p><a href='/'>Back to Home</a></p>",
                502,
            )

        return render_template("results.html", data=result["data"])

    # GET request - legacy backward-compatibility path (subprocess flow)
    result = perform_inference()

    if not result["success"]:
        flash(f"Error: {result['error']}", 'danger')
        return redirect(url_for('home'))

    return render_template("results.html", data=result["data"])


@app.route("/test-plumber")
def test_plumber():
    """
    Temporary test route to verify the Flask → inference_service → plumber_client
    → Plumber API → results.html pipeline end-to-end.
    Uses BASE_PATIENT_PAYLOAD from services/base_payload.py as the known-good request.
    Remove or disable this route once the main /predict flow is migrated.
    """
    payload = BASE_PATIENT_PAYLOAD.copy()

    result = perform_inference(input_data=payload)

    if not result["success"]:
        return (
            f"<h2>Plumber API Error</h2><pre>{result['error']}</pre>"
            f"<p><a href='/'>Back to Home</a></p>",
            502,
        )

    return render_template("results.html", data=result["data"])


# ---------------------------------------------------------------------------
# Editable fields the form exposes.  Shared by /predict and /upload-patient-csv
# so the two routes stay in sync automatically.
# ---------------------------------------------------------------------------
_PREFILL_FIELDS = [
    "patientid",
    "age", "sex",
    "baseline_bmi", "baseline_sbp", "baseline_hr", "baseline_k",
    "lvef", "baseline_nyha",
    "mh_af", "mh_ckd", "mh_dm",
    "bb_dose", "arni_dose", "sglt_dose", "mra_dose", "loopd_dose",
]


@app.route("/upload-patient-csv", methods=["POST"])
def upload_patient_csv():
    """
    Accept a CSV upload, extract the first data row, and re-render the patient
    input form with those values pre-filled.  Does NOT trigger inference — the
    user reviews / edits the values and submits the form themselves.
    """
    if "csv_file" not in request.files:
        return (
            "<h2>Upload Error</h2><pre>No file part in the request.</pre>"
            "<p><a href='/'>Back to Home</a></p>",
            400,
        )

    file = request.files["csv_file"]

    if file.filename == "":
        return (
            "<h2>Upload Error</h2><pre>No file selected.</pre>"
            "<p><a href='/'>Back to Home</a></p>",
            400,
        )

    if not allowed_file(file.filename):
        return (
            "<h2>Upload Error</h2><pre>Invalid file type. Please upload a .csv file.</pre>"
            "<p><a href='/'>Back to Home</a></p>",
            400,
        )

    try:
        df = pd.read_csv(file, nrows=1)
    except Exception as exc:
        return (
            f"<h2>Upload Error</h2><pre>Could not parse CSV: {exc}</pre>"
            f"<p><a href='/'>Back to Home</a></p>",
            400,
        )

    if df.empty:
        return (
            "<h2>Upload Error</h2><pre>CSV file contains no data rows.</pre>"
            "<p><a href='/'>Back to Home</a></p>",
            400,
        )

    row = df.iloc[0]

    # Build prefill dict: only include fields the form actually supports and
    # that have a non-null value in the CSV row.
    prefill_data = {}
    for field in _PREFILL_FIELDS:
        if field in row.index and pd.notna(row[field]):
            prefill_data[field] = row[field]

    return render_template("index.html", prefill_data=prefill_data, upload_filename=file.filename)


if __name__ == "__main__":
    app.run(debug=True, port=8080)