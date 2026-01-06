# scripts/serve.py (küçük prompt netleştirmesi eklendi)
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from fastapi import Body

from .user_progress import UserProgressManager
from .skill_steps_parser import get_skill_steps, parse_all_skills, save_parsed_skills
from .rag_practice_service import (
    extract_numbered_steps,
    load_skill_from_test_suite,
    map_steps_to_skill
)

load_dotenv()
INDEX_DIR = os.getenv("INDEX_DIR", ".rag_index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
chroma_client = chromadb.PersistentClient(path=INDEX_DIR)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL
)
collection = chroma_client.get_or_create_collection(
    name="wheelchair_skills",
    embedding_function=openai_ef,
    metadata={"hnsw:space":"cosine"}
)

class AskRequest(BaseModel):
    question: str
    filters: dict | None = None
    top_k: int = 6

# New model for test suite queries
class TestQueryRequest(BaseModel):
    query: str
    filters: dict | None = None
    top_k: int = 6

# ==================== User Progress Request Models ====================

class RecordInputRequest(BaseModel):
    step_number: int
    expected_input: str
    actual_input: str
    timestamp: Optional[str] = None

class RecordErrorRequest(BaseModel):
    step_number: int
    error_type: str
    expected_action: str
    actual_action: str

class CompleteAttemptRequest(BaseModel):
    success: bool

# ==================== User Progress Manager ====================

# UserProgressManager örneği
progress_manager = UserProgressManager()

app = FastAPI(title="Wheelchair Skills RAG")

SYSTEM_PROMPT = """You are a wheelchair skills coach. Use the provided context to:
- Give concise step-by-step guidance
- Emphasize safety & spotter use when needed
- Warn about common errors; [...]
"""

def build_prompt(question: str, context_chunks: list[str]):
    context_text = "\n\n---\n\n".join(context_chunks)
    user_prompt = f"""User question: {question}

Context:
{context_text}

Respond with:
1) Brief overview
2) Steps (3–7) as a numbered list ONLY — use the exact prefix '1.','2.', etc. For each step include the instruction on the same line. If you have a short cue for the step, put it on the follow...
"""
    return user_prompt

def ask_rag(question: str, filters: dict | None = None, top_k: int = 6):
    where = None
    if filters:
        where = {}
        for k, v in filters.items():
            if k in ("type", "title", "level", "category", "source"):
                where[k] = v

    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        where=where
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]

    prompt = build_prompt(question, docs)

    chat = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    answer = chat.choices[0].message.content

    citations = [
        {"id": _id, "title": meta.get("title"), "type": meta.get("type")}
        for _id, meta in zip(ids, metas)
    ]

    return {
        "answer": answer,
        "citations": citations,
        "used_filters": where or {}
    }

@app.post("/ask")
def ask(req: AskRequest):
    return ask_rag(req.question, req.filters, req.top_k)

# New endpoint: semantic (vector) query against test_suites documents
@app.post("/test_suites/query")
def query_test_suites(req: TestQueryRequest):
    """
    Query the ingested test_suites (data/test_suites/*.json).
    Returns matched documents (vector search) restricted to docs with metadata.type == 'test_suite'
    Optional filters can further restrict results (e.g., {"mapped_skill_id":"beginner-wheeling-forward"})
    """
    where = {"type": "test_suite"}
    if req.filters:
        for k, v in req.filters.items():
            # allow category / mapped_skill_id filter via 'category' metadata field
            if k == "mapped_skill_id":
                where["category"] = v
            elif k in ("title", "level", "source", "type"):
                where[k] = v
            else:
                # attach any custom primitive filter
                where[k] = v

    results = collection.query(
        query_texts=[req.query],
        n_results=req.top_k,
        where=where
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]

    # Return raw docs + metadata so caller can use label/instructions fields if present
    return {
        "query": req.query,
        "results": [
            {"id": _id, "document": doc, "metadata": meta}
            for _id, doc, meta in zip(ids, docs, metas)
        ],
        "used_filters": where
    }

# ==================== User Progress Endpoints ====================

@app.post("/user/{user_id}/create")
def create_user(user_id: str):
    """
    Yeni kullanıcı oluştur.
    """
    user = progress_manager.create_user(user_id)
    return {"success": True, "user": user}

@app.get("/user/{user_id}/progress")
def get_user_progress(user_id: str):
    """
    Kullanıcı ilerleme bilgilerini getir.
    """
    user = progress_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return user

# ==================== Skill Attempt Endpoints ====================

@app.post("/user/{user_id}/skill/{skill_id}/start-attempt")
def start_skill_attempt(user_id: str, skill_id: str):
    """
    Yeni beceri denemesi başlat.
    """
    attempt_id = progress_manager.start_skill_attempt(user_id, skill_id)
    
    # Beceri adımlarını da döndür
    skill_steps = get_skill_steps(skill_id)
    
    return {
        "success": True,
        "attempt_id": attempt_id,
        "skill_id": skill_id,
        "skill_steps": skill_steps
    }

@app.post("/attempt/{attempt_id}/record-input")
def record_input(attempt_id: str, req: RecordInputRequest):
    """
    Adım input'unu kaydet.
    """
    success = progress_manager.record_step_input(
        attempt_id,
        req.step_number,
        req.expected_input,
        req.actual_input,
        req.timestamp
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Deneme bulunamadı")
    
    return {"success": True, "message": "Input kaydedildi"}

@app.post("/attempt/{attempt_id}/record-error")
def record_error(attempt_id: str, req: RecordErrorRequest):
    """
    Adım hatasını kaydet.
    """
    success = progress_manager.record_step_error(
        attempt_id,
        req.step_number,
        req.error_type,
        req.expected_action,
        req.actual_action
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Deneme bulunamadı")
    
    return {"success": True, "message": "Hata kaydedildi"}

@app.post("/attempt/{attempt_id}/complete")
def complete_attempt(attempt_id: str, req: CompleteAttemptRequest):
    """
    Beceri denemesini tamamla.
    """
    success = progress_manager.complete_skill_attempt(attempt_id, req.success)
    
    if not success:
        raise HTTPException(status_code=404, detail="Deneme bulunamadı")
    
    return {"success": True, "message": "Deneme tamamlandı"}

@app.post("/attempt/{attempt_id}/record-step")
def record_step_telemetry(attempt_id: str, payload: dict = Body(...)):
    """
    Accepts a richer telemetry payload for a tutorial step.
    """
    success = progress_manager.record_step_telemetry(attempt_id, payload)
    if not success:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return {"success": True, "message": "Step telemetry recorded"}

# ==================== Analytics Endpoints ====================

@app.get("/user/{user_id}/skill/{skill_id}/stats")
def get_skill_stats(user_id: str, skill_id: str):
    """
    Belirli bir beceri için istatistikleri getir.
    """
    stats = progress_manager.get_skill_stats(user_id, skill_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail="İstatistik bulunamadı")
    
    return stats

@app.get("/user/{user_id}/common-errors")
def get_common_errors(user_id: str, skill_id: Optional[str] = None):
    """
    Kullanıcının en sık yaptığı hataları getir.
    """
    user = progress_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    errors = progress_manager.get_common_errors(user_id, skill_id)
    return {"errors": errors}

@app.get("/user/{user_id}/weak-steps")
def get_weak_steps(user_id: str, skill_id: str):
    """
    En çok hata yapılan adımları getir.
    """
    user = progress_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    weak_steps = progress_manager.get_weak_steps(user_id, skill_id)
    return {"weak_steps": weak_steps}

@app.get("/user/{user_id}/recommended-skills")
def get_recommended_skills(user_id: str):
    """
    Kullanıcı için önerilen becerileri getir.
    """
    user = progress_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    recommendations = progress_manager.get_recommended_skills(user_id)
    return {"recommendations": recommendations}

# ==================== Training Plan Endpoints ====================

@app.post("/user/{user_id}/generate-plan")
def generate_training_plan(user_id: str):
    """
    Kullanıcı için kişiselleştirilmiş eğitim planı oluştur.
    """
    plan = progress_manager.generate_training_plan(user_id)
    return plan

# ==================== Skill Steps Endpoints ====================

@app.get("/skills/{skill_id}/steps")
def get_skill_steps_endpoint(skill_id: str):
    """
    Belirli bir becerinin adımlarını getir.
    """
    steps = get_skill_steps(skill_id)
    
    if not steps:
        raise HTTPException(status_code=404, detail="Beceri bulunamadı")
    
    return steps

@app.post("/skills/parse")
def parse_skills():
    """
    Tüm becerileri parse et ve kaydet.
    """
    parsed_skills = parse_all_skills()
    save_parsed_skills(parsed_skills)
    
    return {
        "success": True,
        "message": f"{len(parsed_skills)} beceri parse edildi",
        "skill_count": len(parsed_skills)
    }

from fastapi import Response

@app.post("/ask/practice")
def ask_practice(req: AskRequest, response: Response):
    response.headers["X-Code-Version"] = "v5-single-action"
    rag = ask_rag(req.question, req.filters)

    # 1️⃣ skill seç (ilk skill citation yeterli)
    skill_id = None
    for c in rag.get("citations", []):
        if c["type"] in ("skill", "test_suite"):
            skill_id = c["id"]
            break

    if not skill_id:
        return {"error": "No skill citation found"}

    # 2️⃣ RAG step'lerini çıkar
    rag_steps = extract_numbered_steps(rag["answer"])

    # 3️⃣ Skill JSON yükle (Test Suite üzerinden)
    # RAG returns citations with 'id'. We try to find that ID in 32_skill_tests.json
    skill_json = load_skill_from_test_suite(skill_id)
    
    # If not found directly, maybe it's a 'skill' type citation that maps to 'mapped_skill_id'
    if not skill_json:
        # fallback: try to find if any test suite maps to this skill_id
        skill_json = load_skill_from_test_suite(skill_id)

    # 4️⃣ Filtrele + Unity'ye uygun hale getir
    final_steps = map_steps_to_skill(rag_steps, skill_json or {})

    return {
        "skill_id": skill_id,
        "steps": final_steps
    }