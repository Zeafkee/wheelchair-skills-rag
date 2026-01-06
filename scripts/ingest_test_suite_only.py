import os
import json
import shutil
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

load_dotenv()
INDEX_DIR = os.getenv("INDEX_DIR", ".rag_index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Tip: set CHROMA_TELEMETRY_DISABLED=1 in .env to silence telemetry warnings

# If you want to re-create a fresh index each run, you can remove the dir first
# CAREFUL: This deletes the whole persistent index
def clear_index_dir(path):
    if os.path.exists(path):
        print(f"Removing existing index directory: {path}")
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"Failed to remove index dir: {e}")

# Use the persistent client after optionally clearing index
def create_chroma_client(path):
    return chromadb.PersistentClient(path=path)

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL
)

def iter_json(path):
    # Handles a JSON file that contains a list or a single object
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        for item in data:
            yield item
    elif isinstance(data, dict):
        # If file is a dict with key "skills" use it, otherwise yield the dict itself
        if "skills" in data and isinstance(data["skills"], list):
            for item in data["skills"]:
                yield item
        else:
            yield data

def to_doc_text(doc):
    # Build a rich, retrievable text from structured fields
    if doc.get("content") or doc.get("title"):
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
    # Fallback for test_suites JSON schema
    parts = []
    label = doc.get("label") or doc.get("title") or ""
    if label:
        parts.append(label)
    instrs = doc.get("instructions") or []
    if instrs:
        parts.append("Instructions:")
        parts.extend(instrs)
    if doc.get("completion_condition"):
        parts.append("Completion condition: " + str(doc.get("completion_condition")))
    if doc.get("requires_helpers") is not None:
        parts.append("Requires helpers: " + str(doc.get("requires_helpers")))
    if doc.get("notes"):
        parts.append("Notes: " + str(doc.get("notes")))
    return "\n".join(parts)

def load_documents_only_test_suite(test_suite_path="data/test_suites/32_skill_tests.json"):
    docs = []
    if not os.path.exists(test_suite_path):
        raise FileNotFoundError(f"Test suite not found: {test_suite_path}")
    for doc in iter_json(test_suite_path):
        docs.append(doc)
    return docs

def clean_metadata(d: dict) -> dict:
    # Chroma requires primitives only; drop None
    md = {
        "type": d.get("type"),
        "title": d.get("title") or d.get("label"),
        "level": d.get("level"),
        "category": d.get("category") or d.get("mapped_skill_id"),
        "source": d.get("source"),
    }
    # If this looks like a test_suites entry, set type to 'test_suite'
    if d.get("test_id") or d.get("mapped_skill_id") or d.get("instructions"):
        md["type"] = md.get("type") or "test_suite"
    return {k: v for k, v in md.items() if isinstance(v, (str, int, float, bool))}

def main(test_suite_path="data/test_suites/32_skill_tests.json", clear_index=False):
    if clear_index:
        clear_index_dir(INDEX_DIR)

    chroma_client = create_chroma_client(INDEX_DIR)

    collection = chroma_client.get_or_create_collection(
        name="wheelchair_skills",
        embedding_function=openai_ef,
        metadata={"hnsw:space": "cosine"},
    )

    docs = load_documents_only_test_suite(test_suite_path)
    ids, metadatas, documents = [], [], []
    for d in docs:
        # Normalise id & title for test_suites
        if d.get("id"):
            _id = d["id"]
        elif d.get("test_id"):
            _id = d["test_id"]
        elif d.get("mapped_skill_id"):
            _id = d["mapped_skill_id"]
        else:
            # fallback: generate an id from title/label
            _id = (d.get("title") or d.get("label") or "")[:200]
        ids.append(_id)
        metadatas.append(clean_metadata(d))
        documents.append(to_doc_text(d))

    # Upsert (delete existing ids first to avoid duplicates)
    if ids:
        try:
            collection.delete(ids=ids)
        except Exception:
            pass
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Ingested {len(ids)} documents from '{test_suite_path}' into collection 'wheelchair_skills' at {INDEX_DIR}")

if __name__ == "__main__":
    # set clear_index=True the first time to ensure only these docs exist
    main(test_suite_path="data/test_suites/32_skill_tests.json", clear_index=True)