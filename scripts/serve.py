import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

from .user_progress import UserProgressManager
from .skill_steps_parser import get_skill_steps, parse_all_skills, save_parsed_skills

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

SYSTEM_PROMPT = """You are a wheelchair skills coach. Use the provided context to:\n- Give concise step-by-step guidance\n- Emphasize safety & spotter use when needed\n- Warn about common errors; provide corrections\n- End with success criteria and a safety reminder\nIf information is missing, ask a clarifying question first.\n"""

def build_prompt(question: str, context_chunks: list[str]):
    context_text = "\n\n---\n\n".join(context_chunks)
    user_prompt = f"""User question: {question}\n\nContext:\n{context_text}\n\nRespond with:\n1) Brief overview\n2) Steps (3–7)\n3) Safety cues & common errors\n4) Success criteria\n5) If unsafe, an abort path and safer alternative\n"""
    return user_prompt

@app.post("/ask")
def ask(req: AskRequest):
    where = None
    if req.filters:
        where = {}
        for k, v in req.filters.items():
            if k in ("type","title","level","category","source"):
                where[k] = v

    results = collection.query(
        query_texts=[req.question],
        n_results=req.top_k,
        where=where
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]

    prompt = build_prompt(req.question, docs)
    chat = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role":"system","content": SYSTEM_PROMPT},
            {"role":"user","content": prompt}
        ],
        temperature=0.2
    )
    answer = chat.choices[0].message.content
    citations = [{"id": _id, "title": meta.get("title"), "type": meta.get("type")} for _id, meta in zip(ids, metas)]
    return {"answer": answer, "citations": citations, "used_filters": where or {}}


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