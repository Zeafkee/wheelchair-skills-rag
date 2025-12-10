# rag_practice_service.py (güncellendi: daha esnek step çıkarıcı, temizleme ve tolerant eşleme)
import re
import json
from pathlib import Path

# gerçek skill_steps dizini (data/skill_steps)
SKILL_DIR = Path(__file__).resolve().parents[1] / "data" / "skill_steps"


def clean_rag_text(text: str):
    """
    RAG tarafından dönen adım metnini temizler:
    - Markdown bold/italic temizleme
    - Inline cue bölümlerini ayırma (ör. "- **Cues**: ...")
    - Eğer 'Title: instruction' formunda ise başlığı ayırır
    Returns: dict with keys: title, instruction, cue
    """
    if not text:
        return {"title": None, "instruction": "", "cue": None}

    t = text

    # Remove bold/italic markers
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = t.strip()

    # Extract inline cue patterns like "- **Cues**: blah" or "- Cue: blah" at end of line
    # We'll try to find the last cue occurrence and take it out
    cue = None
    cue_match = re.search(r'[-–]\s*(?:\*\*?)?Cues?\*?\*?\s*[:\-]?\s*(.+)$', t, re.I)
    if not cue_match:
        cue_match = re.search(r'[-–]\s*(?:Cue|İpucu)\s*[:\-]?\s*(.+)$', t, re.I)
    if cue_match:
        cue = cue_match.group(1).strip()
        # remove the matched cue substring from the text
        t = re.sub(re.escape(cue_match.group(0)) + r'\s*$', '', t).strip()

    # If form "Title: instruction" split
    title = None
    title_match = re.match(r'^\s*([^:]+):\s*(.+)$', t)
    if title_match:
        title = title_match.group(1).strip()
        instr = title_match.group(2).strip()
    else:
        instr = t

    return {"title": title, "instruction": instr, "cue": cue}


def extract_numbered_steps(answer: str):
    """
    RAG cevabından numaralı step'leri daha esnek şekilde çıkarır.
    Desteklenen biçimler: "1. ...", "1) ...", "Step 1: ..." ve çok satırlı açıklamalar.
    Döndürür: list of dicts with keys step_number, instruction, title (optional), cue (optional)
    """
    steps = []
    cur = None

    if not answer:
        return steps

    for line in answer.splitlines():
        # yeni step başlığı tespit et (1., 1), Step 1:, vb.)
        m = re.match(r'^\s*(?:Step\s+)?(\d+)[\.\)]\s*(.*)', line, re.I)
        if m:
            # önceki step'i kaydet
            if cur:
                # temizle ve append et
                cleaned = clean_rag_text(cur["instruction"])
                steps.append({
                    "step_number": cur["step_number"],
                    "title": cleaned.get("title"),
                    "instruction": cleaned.get("instruction"),
                    "cue": cur.get("cue") or cleaned.get("cue")
                })
            cur = {
                "step_number": int(m.group(1)),
                "instruction": m.group(2).strip() or "",
                "cue": None
            }
            continue

        if cur is None:
            # numbered header gelmeden önceki satırları atla
            continue

        # cue satırı (çeşitli formatları yakala)
        cue_m = re.match(r'^\s*(?:Cue|Cues|İpucu)\s*[:\-]?\s*(.*)', line, re.I)
        if cue_m:
            existing = cur.get('cue') or ""
            cur['cue'] = (existing + " " + cue_m.group(1).strip()).strip()
            continue

        # "- Cue: ..." veya " - **Cue**: ..." gibi alt satırlar
        dash_cue = re.match(r'^\s*[-*]\s*(?:Cue|Cues|İpucu)\s*[:\-]?\s*(.*)', line, re.I)
        if dash_cue:
            existing = cur.get('cue') or ""
            cur['cue'] = (existing + " " + dash_cue.group(1).strip()).strip()
            continue

        # normal açıklama satırı -> instruction'a ekle (çok satırlı desteği)
        if line.strip():
            if cur.get("instruction"):
                cur["instruction"] += " " + line.strip()
            else:
                cur["instruction"] = line.strip()

    # son kalan adımı ekle
    if cur:
        cleaned = clean_rag_text(cur["instruction"])
        steps.append({
            "step_number": cur["step_number"],
            "title": cleaned.get("title"),
            "instruction": cleaned.get("instruction"),
            "cue": cur.get("cue") or cleaned.get("cue")
        })

    return steps


def load_skill_json(skill_id: str):
    """
    Skill JSON'unu data/skill_steps içinden yükler.
    """
    path = SKILL_DIR / f"{skill_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Skill JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def map_steps_to_skill(rag_steps, skill_json):
    """
    HYBRID STRATEGY (daha toleranslı):
    1) step_number birebir eşleşirse onu kullan
    2) eşleşme yoksa sıraya göre eşle
    3) input_actions yoksa bile step dönebilir (expected_actions boş olabilir)
    4) skill_json içindeki 'cues' listesi varsa ilk elemanı kullan
    """
    skill_steps = skill_json.get("steps", [])
    # normalize skill steps map: support keys "step_number" or "n"
    skill_step_map = {}
    for s in skill_steps:
        key = s.get("step_number") or s.get("n")
        if key is not None:
            skill_step_map[int(key)] = s

    final_steps = []

    # 1) birebir step_number ile eşle
    for rag_step in rag_steps:
        sn = rag_step.get("step_number")
        skill_step = skill_step_map.get(sn)
        # determine cue: rag cue preferred, else skill cue(s)
        cue_val = rag_step.get("cue")
        if not cue_val and skill_step:
            cues = skill_step.get("cues") or skill_step.get("cue")
            if isinstance(cues, list) and cues:
                cue_val = cues[0]
            elif isinstance(cues, str):
                cue_val = cues

        # expected actions from skill input_actions if present
        expected_actions = []
        if skill_step:
            for ia in skill_step.get("input_actions", []):
                if isinstance(ia, dict) and ia.get("action"):
                    expected_actions.append(ia.get("action"))

        final_steps.append({
            "step_number": sn,
            "text": rag_step.get("instruction") or (skill_step.get("instruction") if skill_step else ""),
            "title": rag_step.get("title"),
            "cue": cue_val,
            "expected_actions": expected_actions
        })

    # 2) Eğer HİÇ eşleşme yoksa sıraya göre eşle (fallback)
    if not final_steps and rag_steps:
        for i, rag_step in enumerate(rag_steps):
            if i >= len(skill_steps):
                # no more skill steps to map to
                break
            skill_step = skill_steps[i]
            # cue fallback
            cues = skill_step.get("cues") or skill_step.get("cue")
            cue_val = None
            if isinstance(cues, list) and cues:
                cue_val = cues[0]
            elif isinstance(cues, str):
                cue_val = cues

            expected_actions = []
            for ia in skill_step.get("input_actions", []):
                if isinstance(ia, dict) and ia.get("action"):
                    expected_actions.append(ia.get("action"))

            final_steps.append({
                "step_number": skill_step.get("step_number") or skill_step.get("n") or (i + 1),
                "text": rag_step.get("instruction") or skill_step.get("instruction"),
                "title": rag_step.get("title") or skill_step.get("title"),
                "cue": rag_step.get("cue") or cue_val,
                "expected_actions": expected_actions
            })

    return final_steps