Docker Compose — Flask app + R Plumber pipeline

Purpose
-------
This repository contains the Flask application. The R Plumber inference pipeline is private and must be provided by the operator on the host machine. The Docker Compose setup in this repository starts three services:

- `db` — MySQL database
- `plumber` — R Plumber API (mounted from a local host folder)
- `web` — Flask application

High-level requirements
-----------------------
- Do NOT copy or commit the private R pipeline into this repository.
- The Plumber service is supplied by mounting a local pipeline folder into the Plumber container at `/pipeline`.
- The Flask app talks to the Plumber service using the Docker service name `plumber` (http://plumber:8002).

Prerequisites
-------------
- Docker Engine and Docker Compose (v2) installed.
- A local copy of the private R pipeline (the same folder you use today when running the pipeline manually).

Prepare the pipeline folder
---------------------------
1. Locate or place your private pipeline folder on the host. Example Windows path:

   C:/Users/Windows/Desktop/Capsico_mini_v2/Capsico_mini_v2

   This folder must contain `run_api.R` at its top level and the pipeline's source files (plumber.R, functions, boot, redcap_data, etc.).

2. In this repository root create a `.env` file by copying `.env.example` and set at minimum the following variables:

   - `PIPELINE_LOCAL_PATH` — absolute host path to your pipeline folder. Example:

       PIPELINE_LOCAL_PATH=C:/Users/Windows/Desktop/Capsico_mini_v2/Capsico_mini_v2

   - `DB_NAME`, `DB_USER`, `DB_PASS` — MySQL credentials used by the Flask app. The defaults in `.env.example` will work for local testing but you can change them.

Notes:
- Do not include secrets in version control.
- Use forward slashes on Windows in the `.env` value to avoid shell parsing problems in some environments.

How the pipeline is mounted
--------------------------
- The `plumber` service in `docker-compose.yml` mounts the host folder `${PIPELINE_LOCAL_PATH}` into the container at `/pipeline`.
- The container's working directory is `/pipeline` and the container runs `Rscript run_api.R` (so `run_api.R` must exist in the mounted folder).

Start the stack
---------------
From the repository root run:

```powershell
docker compose up -d --build
```

Quick checks
------------
- See running services:

```powershell
docker compose ps
```

- Check Plumber health (example endpoint — your pipeline may provide `/health`):

http://127.0.0.1:8002/health

- Open the Flask UI:

http://127.0.0.1:8080

If a port is already in use, you will see an error during startup in the container logs.

Useful commands
---------------
- View logs (all services):

```powershell
docker compose logs -f
```

- View logs for a single service (e.g., plumber):

```powershell
docker compose logs -f plumber
```

- Rebuild and restart after changes to Dockerfiles:

```powershell
docker compose up -d --build
```

- Stop and remove containers:

```powershell
docker compose down
```

Networking & service names
--------------------------
- When running under Docker Compose the Flask app calls the Plumber API at `http://plumber:8002` (service name `plumber`), not `localhost`. This is already set in the project's `config.py` default of `http://plumber:8002` and in the `web` service environment.

Customization notes
-------------------
- If your pipeline needs additional R packages at container build time, add `install.packages(...)` calls to `Dockerfile.plumber` before mounting the pipeline. Alternatively, add an init script inside the mounted pipeline that installs packages on startup.
- The `Dockerfile.web` installs Python dependencies from `requirements.txt`. If you add new Python packages, update `requirements.txt` and rebuild the `web` image.

Security & best practices
------------------------
- Do not commit your pipeline or secrets to this repo.
- For production use, replace defaults with secure credentials and use managed database instances and secret stores.

Troubleshooting
---------------
- "Service can't connect to Plumber": ensure `PIPELINE_LOCAL_PATH` points to a folder containing `run_api.R` and that the Plumber container started successfully (`docker compose logs plumber`).
- "MySQL connection errors": verify the Flask `.env` DB variables match the `db` service credentials. You can also inspect `docker compose logs db` for MySQL-related errors.
- If building `Dockerfile.plumber` fails due to missing system dependencies for certain R packages, check the R packages' system requirements and add `apt-get` installs into `Dockerfile.plumber`.

Contact / Notes
---------------

Notes:
- The `plumber` service expects the host pipeline to include a top-level `run_api.R` file.
- If you prefer an explicit Docker healthcheck for Plumber, add a `healthcheck` entry for the `plumber` service in `docker-compose.yml` that polls `http://localhost:8002/health` inside the container.
- For Windows hosts, prefer a forward-slash path in the `.env` `PIPELINE_LOCAL_PATH` value (example provided in `.env.example`).
