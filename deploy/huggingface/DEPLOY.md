# Deploying Synapse to a Hugging Face Space

The Space runs the whole application (FastAPI backend plus the built React
frontend) in one Docker container on port 7860, with demo mode enabled.

## 1. Create the Space

On https://huggingface.co/new-space:

| Field | Value |
|---|---|
| Owner | your account |
| Space name | `synapse` |
| License | MIT |
| SDK | **Docker**, blank template |
| Hardware | CPU basic is enough |
| Visibility | Public |

Do not add any files during creation.

## 2. Add the secrets

Space **Settings → Variables and secrets → New secret**:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | your Google AI Studio key |
| `SECRET_KEY` | a long random string, e.g. `python -c "import secrets; print(secrets.token_hex(32))"` |

Secrets are injected as environment variables at runtime. They are never
written into the image or the repository.

## 3. Assemble the Space repository

The Space repo needs the application source plus the two files in this folder,
laid out like this:

```
<space repo>/
├── README.md          <- deploy/huggingface/README.md (has the Space YAML header)
├── Dockerfile         <- deploy/huggingface/Dockerfile
├── .dockerignore
├── backend/
└── frontend/
```

Clone the Space next to the project:

```bash
git clone https://huggingface.co/spaces/<user>/synapse hf-space
```

Copy the application in. On Windows, from the project root:

```bat
robocopy backend hf-space\backend /MIR /XD data __pycache__ .pytest_cache .ruff_cache static .venv venv
robocopy frontend hf-space\frontend /MIR /XD node_modules dist
copy /Y deploy\huggingface\Dockerfile hf-space\Dockerfile
copy /Y deploy\huggingface\README.md hf-space\README.md
```

On macOS or Linux:

```bash
rsync -a --delete --exclude data --exclude __pycache__ --exclude .pytest_cache \
  --exclude .ruff_cache --exclude static backend/ hf-space/backend/
rsync -a --delete --exclude node_modules --exclude dist frontend/ hf-space/frontend/
cp deploy/huggingface/Dockerfile hf-space/Dockerfile
cp deploy/huggingface/README.md hf-space/README.md
```

Then publish:

```bash
cd hf-space
git add -A
git commit -m "Deploy Synapse demo"
git push
```

Re-run the same copy commands and push again whenever you want to ship an
update to the Space.

The first build takes several minutes (frontend build plus Python
dependencies). Watch progress in the Space **Logs** tab.

## 4. Verify

- `https://<user>-synapse.hf.space/api/health` returns `{"status":"ok"}`
- The app loads and **Launch demo** signs you in without a form
- The seeded sample document is listed under **Documents** as `ready`
- Asking about the sample report returns an answer with citations

## Runtime configuration

Everything below is set in the Dockerfile and can be overridden with Space
variables.

| Variable | Purpose | Space default |
|---|---|---|
| `DEMO_MODE` | Enables guest sessions and demo limits | `true` |
| `DEMO_SESSIONS_PER_HOUR` | Guest sign-ins per IP | 5 |
| `DEMO_MESSAGES_PER_HOUR` | Chat messages per IP | 12 |
| `DEMO_DAILY_MESSAGE_CAP` | Messages per day across all visitors | 200 |
| `DEMO_MAX_UPLOAD_MB` | Upload ceiling in demo mode | 3 |
| `DATABASE_URL` | SQLite path inside the container | `/home/user/app/data/synapse.db` |
| `CHROMA_DIR` | Vector store path | `/home/user/app/data/chroma` |

## Notes

- Space disk is ephemeral. The database resets when the container restarts and
  the sample document is re-seeded automatically on boot.
- Guest accounts older than 12 hours are purged at startup.
- Seeding embeds the sample document once per cold start. Guest sign-ins clone
  those stored embeddings at the database layer, so they cost nothing.
