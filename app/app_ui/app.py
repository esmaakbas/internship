from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, g
import sys
import os
import pandas as pd
from werkzeug.utils import secure_filename
from flask_session import Session

# root path ekliyoruz ki services import edilebilsin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.inference_service import perform_inference
from services.base_payload import BASE_PATIENT_PAYLOAD
from services.decision_engine import classify_treatments
from validators.patient_form_parser import parse_patient_form

from config import (
    FLASK_SECRET_KEY,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    ALLOWED_DEBUG_IPS,
    SESSION_TYPE,
    SESSION_PERMANENT,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE,
    AUTH0_ENABLED,
)

from database import check_connection, count_users, validate_database

# Import authentication module only if Auth0 is configured
if AUTH0_ENABLED:
    import auth


app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Configure Flask-Session for server-side sessions
app.config['SESSION_TYPE'] = 'filesystem'  # Use filesystem for development
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True  # Sign session cookies
app.config['SESSION_KEY_PREFIX'] = 'capsico:'  # Unique prefix
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE  # From config (False in debug, True in production)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'capsico_session'  # Custom cookie name

# Ensure session directory exists
import os
os.makedirs(os.path.join(os.path.dirname(__file__), 'flask_session'), exist_ok=True)

Session(app)

# Conditionally register authentication routes
if AUTH0_ENABLED:
    auth.register_auth_routes(app)
    app.logger.info("Authentication enabled (Auth0 configured)")
else:
    app.logger.warning("Authentication DISABLED - Auth0 not configured in .env")
    app.logger.warning("To enable authentication, configure AUTH0_DOMAIN, AUTH0_CLIENT_ID, and AUTH0_CLIENT_SECRET")

    # Add before_request handler to set g.user to None when auth is disabled
    @app.before_request
    def load_user_without_auth():
        g.user = None

# Validate database connection on startup
try:
    validate_database()
    app.logger.info("Database validation successful")
except Exception as exc:
    app.logger.error(f"Database validation failed: {exc}")
    app.logger.warning("App will start but database operations may fail")


# Make auth state available in all templates
@app.context_processor
def inject_auth_state():
    """Inject authentication state into all templates.

    Provides:
        auth_enabled: Whether Auth0 is configured
        user: Current user dict from g.user (None if not logged in)
    """
    return {
        'auth_enabled': AUTH0_ENABLED,
        'user': getattr(g, 'user', None)
    }


# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'inputs')
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    # g.user is set by auth.load_user_into_g() if auth is enabled
    # or by load_user_without_auth() if auth is disabled
    return render_template("index.html")


# Protected routes - only register if authentication is enabled
if AUTH0_ENABLED:
    @app.route("/profile")
    @auth.login_required
    def profile():
        """Protected route example - requires authentication.

        Demonstrates:
        - @login_required decorator
        - Accessing g.user for current user info
        - User data from database (synced from Auth0)
        """
        return render_template("profile.html", user=g.user)


    @app.route("/admin")
    @auth.admin_required
    def admin_panel():
        """Admin-only route example - requires admin role.

        Demonstrates:
        - @admin_required decorator
        - Role-based access control
        """
        return "<h1>Admin Panel</h1><p>Only admins can see this page.</p><p><a href='/'>Home</a></p>"
else:
    # When auth is disabled, protected routes return a message
    @app.route("/profile")
    def profile():
        return (
            "<h1>Authentication Required</h1>"
            "<p>This feature requires authentication to be enabled.</p>"
            "<p>Configure Auth0 credentials in your .env file to enable authentication.</p>"
            "<p><a href='/'>Back to Home</a></p>",
            200
        )

    @app.route("/admin")
    def admin_panel():
        return (
            "<h1>Authentication Required</h1>"
            "<p>This feature requires authentication to be enabled.</p>"
            "<p>Configure Auth0 credentials in your .env file to enable authentication.</p>"
            "<p><a href='/'>Back to Home</a></p>",
            200
        )


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

        # TODO: NEXT PHASE - Save prediction to database with user_id
        # When authenticated users make predictions, save to predictions table:
        # user_id = g.user['id'] if g.user else None
        # save_prediction(user_id=user_id, input_payload=payload,
        #                 output_payload=result['data'], status='success')
        # This will enable prediction history feature in the next phase.

        if not result["success"]:
            return (
                f"<h2>Inference Error</h2><pre>{result['error']}</pre>"
                f"<p><a href='/'>Back to Home</a></p>",
                502,
            )

        return render_template(
            "results.html",
            data=result["data"],
            decision_summary=result.get("decision_summary"),
            alex_guidance=result.get("alex_guidance"),
            patient_data=payload
        )

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

    return render_template(
        "results.html",
        data=result["data"],
        alex_guidance=result.get("alex_guidance"),
        patient_data=payload
    )


# ---------------------------------------------------------------------------
# Editable fields the form exposes.  Shared by /predict and /upload-patient-csv
# so the two routes stay in sync automatically.
# ---------------------------------------------------------------------------
_PREFILL_FIELDS = [
    # Patient info
    "patientid", "age", "sex",

    # Vital signs
    "baseline_sbp", "baseline_dpb", "baseline_hr", "baseline_bw", "baseline_bmi",

    # Cardiac function
    "lvef", "baseline_nyha", "baseline_ischaemic", "baseline_qrs",
    "PM_Rhythm_ECG", "EP_HF_encoded",

    # Physical examination
    "baseline_orthopnea", "baseline_rales", "baseline_jdv", "baseline_edema",

    # Medical history
    "mh_af", "mh_ckd", "mh_dm", "mh_hypertension", "mh_mi", "mh_agina",
    "mh_cabg", "mh_vavhd", "mh_stroke", "mh_bbb", "mh_impl_dev",
    "mh_copd", "mh_hept", "mh_smoke", "aspirin",

    # Lab values
    "baseline_k", "baseline_na", "baseline_creat", "baseline_urea",
    "baseline_hb", "baseline_hct", "baseline_ntbnp", "baseline_cys",
    "baseline_crp", "baseline_gdf15", "baseline_hscnt", "baseline_il6",
    "baseline_chol", "baseline_hb_a1c", "baseline_tf", "baseline_ft",

    # Current medications
    "bb_dose", "arni_dose", "sglt_dose", "mra_dose", "loopd_dose",
    "ace_dose", "arb_dose",

    # Previous medications
    "DoseBB_prev", "RASDose_prev", "DoseSpiro_prev",
    "Loop_dose_prev", "SGLT2Dose_prev", "ARNIDose_prev",

    # Visit info
    "visit_time_days", "time_from_last_medication",
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


@app.route("/test-alex-ui")
def test_alex_ui():
    """
    Test route to verify Alex UI integration without requiring Plumber API.
    Returns mock inference results to test the results.html template and Alex guidance display.
    """
    # Mock inference results
    mock_data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
        {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    # Generate decision summary from mock data
    mock_decision_summary = classify_treatments(mock_data)

    # Mock Alex guidance (successful)
    mock_alex_guidance = {
        "ok": True,
        "request_id": "test_mock_request",
        "status": "ok",
        "answer": "Based on the treatment effect estimates, BB shows the strongest beneficial effect (tau=-0.123, 95% CI: -0.234 to -0.012), followed by RAS (tau=-0.098), SP (tau=-0.056), and LD (tau=-0.023). All treatments show negative point estimates indicating potential benefit, though the confidence intervals vary in their precision. BB has the most favorable profile with both the point estimate and confidence interval indicating benefit.",
        "model": "test-mock-model",
        "warnings": [],
        "metadata": {},
        "error": None,
        "raw": {}
    }

    # Mock patient data for testing
    mock_patient_data = BASE_PATIENT_PAYLOAD.copy()

    return render_template(
        "results.html",
        data=mock_data,
        decision_summary=mock_decision_summary,
        alex_guidance=mock_alex_guidance,
        patient_data=mock_patient_data
    )


@app.route("/test-alex-ui-error")
def test_alex_ui_error():
    """
    Test route showing Alex guidance failure scenario.
    Displays how the UI handles Alex API being down or erroring.
    """
    # Mock inference results (same as success test)
    mock_data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
        {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    # Generate decision summary from mock data
    mock_decision_summary = classify_treatments(mock_data)

    # Mock Alex guidance (failed)
    mock_alex_guidance = {
        "ok": False,
        "request_id": "test_mock_error",
        "status": "error",
        "answer": None,
        "model": None,
        "warnings": [],
        "metadata": {},
        "error": {
            "code": "CONNECTION_ERROR",
            "message": "Failed to connect to guidance API"
        },
        "raw": {}
    }

    # Mock patient data for testing
    mock_patient_data = BASE_PATIENT_PAYLOAD.copy()

    return render_template(
        "results.html",
        data=mock_data,
        decision_summary=mock_decision_summary,
        alex_guidance=mock_alex_guidance,
        patient_data=mock_patient_data
    )


@app.route('/debug/db-check')
def debug_db_check():
    """Lightweight debug endpoint returning DB connectivity and a users count.

    SECURITY: This route is restricted to specific IP addresses (localhost only
    by default) and should be removed or moved to a proper health check endpoint
    in production.

    Access control:
    - Only allowed IPs from ALLOWED_DEBUG_IPS config can access this route
    - Returns 403 Forbidden for unauthorized IPs
    - Only available when FLASK_DEBUG is True (returns 404 in production)

    Returns:
        JSON response with database status or error
    """
    # Only available in debug mode
    if not FLASK_DEBUG:
        return jsonify({'error': 'Not found'}), 404

    # IP whitelist check
    client_ip = request.remote_addr
    if client_ip not in ALLOWED_DEBUG_IPS:
        return jsonify({
            'ok': False,
            'error': 'Access forbidden',
            'client_ip': client_ip
        }), 403

    # Perform database checks
    from sqlalchemy.exc import SQLAlchemyError
    try:
        select1 = check_connection()
        users = count_users()
        return jsonify({
            'ok': True,
            'db': {
                'select_1': select1,
                'users_count': users,
            }
        })
    except SQLAlchemyError as exc:
        # Log the full error but don't expose details to client
        app.logger.error(f"Database check failed: {exc}", exc_info=True)
        return jsonify({
            'ok': False,
            'error': 'Database connection failed'
        }), 500




if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)
