import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

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