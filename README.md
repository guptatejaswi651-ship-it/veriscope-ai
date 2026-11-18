# VeriScope AI

VeriScope AI is an evidence-first research and fact-checking application. It retrieves current web sources, asks a local or remotely hosted Ollama-compatible model to compare claims against those sources, and saves structured reports for follow-up.

## Problem and solution

Research answers are difficult to trust when conclusions are detached from their sources. VeriScope keeps retrieved sources, citations, analysis status, and limitations alongside each report so people can inspect the evidence rather than rely on an unsupported answer.

## Features

- Search a question with Tavily and retain the returned source links and excerpts.
- Review claims and source disagreements with an Ollama-compatible model.
- Clearly mark analysis as unavailable rather than inventing results when inference cannot run.
- Save research reports in SQLite and browse report history.
- Ask follow-up questions about a saved report, with answers linked to its source IDs.
- View agent status, evidence assessments, and report limitations.

## Technology stack

- Frontend: React, Vite, and JavaScript.
- Backend: FastAPI, Pydantic, and Uvicorn.
- Research: Tavily Search API.
- Analysis: Ollama-compatible `/api/chat` API; the local default model is `qwen3.5:4b`.
- Persistence: SQLite.

## Architecture

1. The browser sends research, history, report, and report-chat requests to the FastAPI backend under `/api`.
2. FastAPI retrieves current sources from Tavily.
3. The backend submits the retrieved evidence to Ollama-compatible verification and conflict-analysis requests. Source retrieval is kept distinct from model analysis.
4. The backend saves completed reports in SQLite and returns their citations, findings, claims, limitations, and agent statuses.
5. Ask VeriScope uses the selected saved report as its context and returns references to that report's sources.

During local development Vite proxies `/api` to `http://127.0.0.1:8000`. In a deployed frontend, `VITE_API_BASE_URL` points to the separately deployed backend.

## Local setup

Requirements: Node.js supported by the installed Vite release, Python 3.11 or newer, and Ollama with `qwen3.5:4b` pulled for local AI analysis.

1. Install frontend dependencies from the project root:

   ```sh
   npm ci
   ```

2. Create and activate a Python environment, then install backend dependencies:

   ```sh
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Create `backend/.env` (do not commit it) and set `TAVILY_API_KEY` to a key you obtained from Tavily. For local inference, the default Ollama URL and model can be used; optionally set:

   ```dotenv
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=qwen3.5:4b
   ```

   Start Ollama and make sure the configured model is available. The application does not fabricate Tavily results when the key is missing, and analysis is reported unavailable if the model endpoint cannot be reached.

4. Start the backend from the `backend` directory:

   ```sh
   cd backend
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

5. In another terminal at the project root, start the frontend:

   ```sh
   npm run dev
   ```

   Open the local URL printed by Vite. The backend health endpoint is `http://127.0.0.1:8000/health`.

Run the backend tests from `backend/` with the active Python environment:

```sh
python -m unittest discover -s tests -v
```

## Environment variables

| Variable | Used by | Required | Default / purpose |
| --- | --- | --- | --- |
| `TAVILY_API_KEY` | Backend | Yes, for research | Your Tavily API key. Keep it only in the backend environment; never put it in a `VITE_` variable. |
| `OLLAMA_BASE_URL` | Backend | For AI analysis | `http://127.0.0.1:11434` locally. Set to a network-reachable Ollama-compatible service URL when deployed. The backend appends `/api/chat`. |
| `OLLAMA_MODEL` | Backend | For AI analysis | `qwen3.5:4b`. Set this to a model available from the configured inference service. |
| `CORS_ORIGINS` | Backend | For separate deployed sites | Comma-separated frontend origins, such as `https://your-site.onrender.com`; local Vite origins are the default. Do not include paths. |
| `DATABASE_PATH` | Backend | No | SQLite file path; defaults to `backend/veriscope.db` in local use. |
| `VITE_API_BASE_URL` | Frontend build | For separate deployed sites | Absolute base URL of the deployed backend, for example `https://your-api.onrender.com`. Leave unset for the local Vite proxy. This value is public in the built frontend and must not contain credentials. |
| `PORT` | Backend host | No local setting | Supplied by Render. Uvicorn must bind to `0.0.0.0` and this port. |

## Deploying separate services on Render

Create both services from the same GitHub repository. Deploy the backend first so its public service URL is available when configuring the frontend.

### Backend Web Service

- **Root Directory:** `backend`
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/health`
- Add these environment variables in the Render dashboard:
  - `TAVILY_API_KEY`: your Tavily key.
  - `OLLAMA_BASE_URL`: the externally reachable base URL of your Ollama-compatible inference service.
  - `OLLAMA_MODEL`: a model name supported by that service (the default is `qwen3.5:4b`).
  - `CORS_ORIGINS`: the exact public origin of the frontend Static Site, with no path. For example, `https://your-site.onrender.com`.
  - `DATABASE_PATH`: optional. Set this to a path on a mounted persistent disk, such as `/var/data/veriscope.db`, if the service has one.

Render provides `PORT`; do not hardcode a production port. The health endpoint confirms the API process is running; it does not verify Tavily credentials or inference availability.

### Frontend Static Site

- **Root Directory:** repository root.
- **Build Command:** `npm ci && npm run build`
- **Publish Directory:** `dist`
- Set `VITE_API_BASE_URL` to the backend's public URL, for example `https://your-api.onrender.com`, without a trailing path. Vite embeds this value at build time, so rebuild/redeploy the Static Site after changing it.

After both services deploy, check the backend `/health`, open the Static Site, and submit a research question. The backend's `CORS_ORIGINS` must match the browser-visible frontend origin exactly.

## Known deployment limitations

- **Local Ollama is not reachable from Render.** The default `127.0.0.1:11434` refers to the backend container itself after deployment, not your MacBook. To get live AI claim verification, conflict analysis, and Ask VeriScope on Render, provision an externally reachable Ollama-compatible inference endpoint, then configure `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in the backend service. No hosted inference service or credentials are provisioned by this project.
- The backend currently sends requests to `/api/chat` without provider-specific authentication headers. An inference service must expose a compatible endpoint reachable from Render without unsupported authentication requirements.
- A valid `TAVILY_API_KEY` is separately required for live source discovery. Do not put backend credentials in frontend build variables.
- SQLite on a Render service's default filesystem is not durable across service replacement or restarts. Use an attached persistent disk and point `DATABASE_PATH` to it if report history must persist; otherwise expect saved reports/history to be ephemeral.
- If hosted inference is not configured or reachable, research can still return actual Tavily sources with AI analysis marked unavailable. Ask VeriScope requires the inference service and cannot answer without it.
