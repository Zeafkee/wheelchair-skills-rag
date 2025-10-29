import os, json
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

load_dotenv()
INDEX_DIR = os.getenv("INDEX_DIR", ".rag_index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Tip: set CHROMA_TELEMETRY_DISABLED=1 in .env to silence telemetry warnings

chroma_client = chromadb.PersistentClient(path=INDEX_DIR)

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL
)

def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def to_doc_text(doc):
    # Build a rich, retrievable text from structured fields
    lines = [doc.get("title",""), doc.get("content","")]
    s = doc.get("structured", {})
    if s:
        if s.get("prerequisites"): lines.append("Prerequisites: " + "; ".join(s["prerequisites"]))
        if s.get("stroke_patterns"): lines.append("Stroke patterns: " + "; ".join(s["stroke_patterns"]))
        if s.get("safety_notes"): lines.append("Safety: " + "; ".join(s["safety_notes"]))
        if s.get("steps"):
            lines.append("Steps:")
            for step in s["steps"]:
                line = f"{step.get('n')}. {step.get('instruction')}"
                cues = step.get("cues") or []
                if cues:
                    line += " Cues: " + "; ".join(cues)
                lines.append(line)
        if s.get("common_errors"): lines.append("Common errors: " + "; ".join(s["common_errors"]))
        if s.get("corrections"): lines.append("Corrections: " + "; ".join(s["corrections"]))
    return "\n".join([l for l in lines if l])

def load_documents():
    docs = []
    for path in ["data/skills.jsonl", "data/faq.jsonl", "data/rubrics.jsonl"]:
        if not os.path.exists(path):
            continue
        for doc in iter_jsonl(path):
            docs.append(doc)
    return docs

def clean_metadata(d: dict) -> dict:
    # Chroma requires primitives only; drop None
    md = {
        "type": d.get("type"),
        "title": d.get("title"),
        "level": d.get("level"),
        "category": d.get("category"),
        "source": d.get("source"),
    }
    return {k: v for k, v in md.items() if isinstance(v, (str, int, float, bool))}

def main():
    collection = chroma_client.get_or_create_collection(
        name="wheelchair_skills",
        embedding_function=openai_ef,
        metadata={"hnsw:space": "cosine"},
    )
    docs = load_documents()
    ids, metadatas, documents = [], [], []
    for d in docs:
        ids.append(d["id"])
        metadatas.append(clean_metadata(d))
        documents.append(to_doc_text(d))
    # Upsert
    if ids:
        try:
            collection.delete(ids=ids)
        except Exception:
            pass
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Ingested {len(ids)} documents into collection 'wheelchair_skills' at {INDEX_DIR}")

if __name__ == "__main__":
    main()