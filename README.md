# Wheelchair Skills RAG Pack

This pack turns a wheelchair skills manual into a structured knowledge base for a Retrieval-Augmented Generation (RAG) assistant that:
- Guides users through skills step-by-step
- Warns on common errors and safety issues
- Builds personalized training plans based on observed performance
- Can be integrated with a Unity simulation

## Contents

- `data/skills.jsonl` — Canonical skill knowledge base (structured from your txt).
- `data/faq.jsonl` — Common Q&A to improve retrieval coverage.
- `data/rubrics.jsonl` — Evaluation rubrics and progressions.
- `data/training_plan_template.json` — Template for adaptive training plans.
- `data/telemetry.schema.json` — Schema for telemetry from Unity for real-time checks.
- `schemas/skill.schema.json` — JSON Schema for skill docs validation.
- `prompts/system.txt` — System prompt to enforce safety-first guidance behavior.
- `prompts/user_guidance_template.txt` — Template for user-specific guidance prompts.
- `scripts/ingest.py` — Chunk, embed, and index the KB (Chroma).
- `scripts/serve.py` — Simple FastAPI app with a `/ask` RAG endpoint.
- `requirements.txt` — Python deps.
- `.env.example` — Environment variables.

## Quickstart

1) Create a virtualenv and install deps:
```
python -m venv .venv
# Windows PowerShell:
. .\.venv\Scripts\Activate.ps1
# Windows cmd:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

2) Set environment variables:
- Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` (uppercase key).
- Optionally set `EMBEDDING_MODEL`, `LLM_MODEL`.
- Optional: set `CHROMA_TELEMETRY_DISABLED=1` to silence Chroma telemetry logs.

3) Ingest the data (build the vector index):
```
python scripts/ingest.py
```

4) Run the server:
```
python -m uvicorn scripts.serve:app --reload --port 8000
```

5) Test the RAG endpoint:
```
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{
  "question": "How do I pop casters safely and what common mistakes should I avoid?",
  "filters": {"level": "intermediate"}
}'
```

PowerShell example:
```
$body = @{
  question = "How do I pop casters safely and what mistakes should I avoid?"
  filters  = @{ level = "intermediate" }
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -ContentType "application/json" -Body $body
```

## How to run (detailed)

- Activate the virtualenv each new terminal session:
  - PowerShell: `. .\.venv\Scripts\Activate.ps1`
  - cmd: `.venv\Scripts\activate`
  - macOS/Linux: `source .venv/bin/activate`

- Install/upgrade dependencies:
```
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

- Configure `.env`:
```
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
INDEX_DIR=.rag_index
CHROMA_TELEMETRY_DISABLED=1  # optional; reduces log noise
```

- Build the index and run:
```
python scripts/ingest.py
python -m uvicorn scripts.serve:app --reload --port 8000
```

### Run without a virtualenv (not recommended)
```
python -m pip install --upgrade pip setuptools wheel
python -m pip install --user -r requirements.txt
python scripts/ingest.py
python -m uvicorn scripts.serve:app --reload --port 8000
```
Tip: Using `python -m uvicorn` ensures the right interpreter.

## Troubleshooting

- Telemetry warnings like “capture() takes 1 positional argument…”:
  - Add `CHROMA_TELEMETRY_DISABLED=1` to `.env`.

- OpenAI/httpx compatibility (e.g., “proxies” argument error):
  - Pin compatible versions:
    - `pip install "openai==1.43.0" "httpx==0.27.2"`

- Metadata NoneType error during ingest:
  - Already handled in `scripts/ingest.py`. If seen, wipe the index and re-run:
    - Windows: `rmdir /s /q .rag_index`
    - macOS/Linux: `rm -rf .rag_index`

- Uvicorn not found:
  - Use `python -m uvicorn ...` or ensure the venv is activated.

## How RAG “Training” Works

RAG typically doesn’t require finetuning the LLM. Instead, you:
- Prepare high-quality, structured documents (this pack).
- Embed documents into vectors (ingest step).
- At query time, retrieve the best-matching chunks.
- Feed retrieved context + your prompts into the LLM to produce an answer.
- Iterate on chunking, metadata, retrieval settings, and prompts (“train” the system behavior) rather than the model weights.

Key knobs:
- Chunk size (e.g., 500–800 tokens) and overlap (50–100 tokens).
- Retrievers (top_k: 4–10), and optional rerankers.
- Metadata filters (e.g., `level`, `category`, `spotter_required`).
- Prompt design (system + user templates).
- Evaluation sets and offline retrieval metrics (MRR, Recall@k).

## Suggested Iteration Loop

1) Start with this pack and `/ask`.
2) Add synthetic queries to `data/faq.jsonl` where retrieval fails.
3) Adjust `chunk_size`, `chunk_overlap`, `top_k` in `ingest.py` or `serve.py`.
4) Add a reranker if needed (e.g., Cohere Rerank, Cross-Encoder).
5) Map Unity telemetry to common errors via `telemetry.schema.json` and produce warnings/next steps.
6) Store per-user session logs to adapt training plans using `data/training_plan_template.json`.

## Safety Considerations

- Always include safety notes and spotter requirements in guidance.
- Offer “abort/stop” guidance when risk thresholds are exceeded.
- Encourage professional supervision for high-risk and advanced skills.
- The provided content is for simulation and training aid; not a substitute for professional instruction.

## Unity Integration (High Level)

- Unity sends: user query + current skill context + telemetry (posture, speed, slope, collisions).
- Backend `/ask` returns: step-by-step guidance, safety checks, and next-step cues derived from retrieved context.
- Use `telemetry.schema.json` to structure events; add a separate scoring endpoint later to map telemetry to common errors and adaptive plans.

See `unity/unity_integration.md` for details.