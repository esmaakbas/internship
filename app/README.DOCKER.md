Docker Compose setup for Capsico Flask + Plumber pipeline

Overview
--------
This repository contains the Flask application. The R Plumber pipeline is private and must be supplied locally by the operator.

What this compose file starts
- MySQL database (service name: `db`)
- R Plumber API (service name: `plumber`) — mounts your local pipeline folder into the container at `/pipeline`
- Flask web app (service name: `web`)

Important: the R pipeline source is NOT included in this repo and must remain private. Do NOT copy the pipeline into this repository.

How to provide the pipeline folder
----------------------------------
1. Place your pipeline folder somewhere on the host, for example:

   C:/Users/Windows/Desktop/Capsico_mini_v2/Capsico_mini_v2

2. In the repository root create a `.env` file (copy from `.env.example`) and set:

   PIPELINE_LOCAL_PATH=C:/Users/Windows/Desktop/Capsico_mini_v2/Capsico_mini_v2

You can also set other env values such as DB credentials if you wish.

How it is mounted
------------------
The pipeline folder on the host is mounted into the Plumber container at `/pipeline`.
The Plumber container's working directory is `/pipeline` and it runs:

    Rscript run_api.R

which must exist within your mounted pipeline folder.

Run the stack
-------------
From the repository root run:

```powershell
docker compose up -d --build
```

Verify
------
- Plumber health (example): http://127.0.0.1:8002/health
- Flask UI: http://127.0.0.1:8080
- See running services: `docker compose ps`

Notes & constraints
-------------------
- Do NOT add the private pipeline files to this repo or commit them.
- The Flask app will call the Plumber service at `http://plumber:8002` when running inside Docker Compose.
- If your platform requires different mount syntax or path escaping, adjust `PIPELINE_LOCAL_PATH` accordingly.
