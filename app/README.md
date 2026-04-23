# Capsico Inference Application

A Python-based application for running inference predictions using the Capsico R pipeline. This application provides both a Flask web interface and integration with an R-based prediction model for processing patient data.

## Documentation

- Auth0 setup: [docs/AUTH0_SETUP_GUIDE.md](docs/AUTH0_SETUP_GUIDE.md)
- Auth0 action setup: [docs/AUTH0_ACTION_SETUP_GUIDE.md](docs/AUTH0_ACTION_SETUP_GUIDE.md)
- Flask-Alex trust contract: [docs/ALEX_TRUST_CONTRACT.md](docs/ALEX_TRUST_CONTRACT.md)

## Features

- **Web Interface**: Flask-based UI for uploading patient data and viewing predictions
- **R Pipeline Integration**: Automated execution of R scripts for inference
- **Plumber API Client**: Integration with R Plumber API for predictions
- **CSV Processing**: Upload and process patient data in CSV format
- **Form Validation**: Built-in patient form parser and validators
- **Automatic Configuration**: Auto-detects R installation and script paths

## Prerequisites

- **Python**: 3.8 or higher
- **R**: 4.0 or higher (with Rscript available in PATH)
- **R Packages**: Required packages for the Capsico pipeline
- **Operating System**: Windows (configured for Windows paths)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd internship/app
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Optional - Install python-dotenv** for environment variable management:
   ```bash
   pip install python-dotenv
   ```

5. **Copy env variables to .env file**:
   ```bash
   cp .env.example .env
   ```

6. **Verify setup**:
   ```bash
   python verify_setup.py
   ```

## Configuration

The application uses `config.py` for centralized configuration. Settings can be customized via environment variables or a `.env` file.

### Environment Variables

Create a `.env` file in the project root with the following variables (optional):

```env
# R Configuration
R_EXECUTABLE=C:\Program Files\R\R-4.x.x\bin\Rscript.exe
R_SCRIPT_PATH=path\to\Capsico_mini_v2\step_inference_mini_both.R

# Plumber API
PLUMBER_API_URL=http://localhost:8000

# Alex Guidance API
ALEX_GUIDANCE_URL=http://localhost:8000/guidance/generate
ALEX_TIMEOUT_SECONDS=30

# Delegated JWT (Flask signs, Alex verifies)
ALEX_DELEGATION_ISSUER=capsico-flask-backend
ALEX_DELEGATION_AUDIENCE=alex-llm-service
ALEX_DELEGATION_KEY_ID=alex-key-2026-01
ALEX_DELEGATION_TTL_SECONDS=120
# PEM private key (single-line env with escaped newlines)
ALEX_DELEGATION_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here
FLASK_DEBUG=True
FLASK_PORT=8080
FLASK_HOST=127.0.0.1
```

**Note**: The application will auto-detect R installation if not specified.

### Secure Flask -> Alex Flow (Production)

1. Auth0 authenticates the user; Flask trusts this verified session.
2. Flask creates a short-lived delegated JWT per Alex request.
3. Alex verifies JWT signature/claims (`iss`, `sub`, `aud`, `exp`, `iat`, `jti`) and rejects invalid tokens.
4. Alex stores `jti` for replay protection and rejects duplicate token IDs.

To generate an RSA key pair for `ALEX_DELEGATION_PRIVATE_KEY` / Alex JWKS:

```bash
openssl genrsa -out alex_delegation_private.pem 2048
openssl rsa -in alex_delegation_private.pem -pubout -out alex_delegation_public.pem
```

Never commit private keys or `.env` secrets.

## Directory Structure

```
app/
├── app_ui/              # Flask web application
│   ├── app.py          # Main Flask application
│   └── validators/     # Form validation and parsing
├── clients/            # External service clients
│   └── plumber_client.py  # R Plumber API client
├── services/           # Business logic
│   ├── base_payload.py       # Payload construction
│   └── inference_service.py  # Inference orchestration
├── r_pipeline_link/    # R pipeline integration
│   └── r_runner.py     # R script execution
├── inputs/             # CSV input files (gitignored)
├── outputs/            # Pipeline results (gitignored)
├── logs/               # Application logs (gitignored)
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Usage

### Running the Flask Web Application

```bash
python app_ui/app.py
```

Access the application at `http://localhost:8080`

### Running Tests

```bash
python run_test.py
```

### Configuration Verification

```bash
python config.py
```

This will display the current configuration including detected R paths.

## Tech Stack

- **Backend**: Python 3.x, Flask 3.1.3
- **Data Processing**: Pandas 3.0.1, NumPy 2.4.3
- **R Integration**: Subprocess execution, R Plumber API
- **HTTP Client**: Requests 2.32.5
- **Template Engine**: Jinja2 3.1.6

## API Endpoints

### Flask Web Interface

- `GET /` - Main upload form
- `POST /predict` - Upload CSV and get predictions
- `GET /results` - View prediction results

### Plumber API Integration

- `POST /predict` - Send payload to R Plumber API

## Input Format

The application accepts CSV files with patient data. See the validators module for expected column formats.

## Output Format

Results are generated in CSV format and saved to the `outputs/` directory:
- `inference_results_summary.csv` - Main prediction results

## Troubleshooting

1. **R not found**: Ensure R is installed and `Rscript.exe` is in PATH, or set `R_EXECUTABLE` in `.env`
2. **Script not found**: Set `R_SCRIPT_PATH` to point to your `step_inference_mini_both.R` file
3. **Import errors**: Activate virtual environment and reinstall dependencies
4. **Port conflicts**: Change `FLASK_PORT` in `.env` or environment variables

## Development

### Adding New Features

1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Test thoroughly
4. Submit a pull request

### Code Organization

- **app_ui/**: Frontend and web interface code
- **services/**: Business logic and orchestration
- **clients/**: External API integrations
- **r_pipeline_link/**: R script execution layer

## Security Notes

- Never commit `.env` files or sensitive credentials
- Keep `FLASK_SECRET_KEY` secure in production
- Validate all file uploads
- Limit file sizes (default: 16MB)

## License

[Specify your license here]

## Contact

[Your contact information or team information]
