import os
import json
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pathlib import Path
from bs4 import BeautifulSoup

router = APIRouter()

SYLLABUS_DIR = os.getenv("SYLLABUS_DIR", "/app/data/syllabus")
PROMPTS_DIR = os.getenv("PROMPTS_DIR", "/app/data/prompts")

# ── Hardcoded fallbacks (used only if no file exists on disk) ──
_FALLBACK_PROMPTS = {
    "ask_agent": (
        "You are an expert tutor for {SUBJECT}.\n"
        "Topic: {TOPIC}\nFocus: {CONCEPT}\nContext: {CLARIFICATION}\n\n"
        "Task: Generate comprehensive study notes for this concept.\n"
        "Use LaTeX ($...$) for math. Structure with headings."
    ),
    "mcq_widget": (
        "You are an expert MCQ designer for {SUBJECT}.\n"
        "Topic: {TOPIC}\nFocus: {CONCEPT}\nContext: {CLARIFICATION}\n\n"
        "Task: Generate exactly {NUM_QUESTIONS} MCQs at {LEVEL} difficulty.\n"
        "Use LaTeX ($...$) for math.\n"
        "After each question's 4 options, put the answer and explanation inside a <details> tag.\n"
        "Separate questions with ---."
    ),
}


@router.get("/prompts/{function_name}")
async def get_prompt_template(function_name: str, exam: str = ""):
    """
    Returns a prompt template for the given function_name.
    
    Resolution order:
    1. Per-exam override: SYLLABUS_DIR/{exam}/prompts/{function_name}.txt
    2. Global default:   PROMPTS_DIR/{function_name}.txt
    3. Hardcoded fallback (minimal)
    """
    # 1. Per-exam override
    if exam:
        exam_prompt = Path(SYLLABUS_DIR) / exam / "prompts" / f"{function_name}.txt"
        if exam_prompt.is_file():
            return PlainTextResponse(exam_prompt.read_text(encoding="utf-8"))

    # 2. Global default
    global_prompt = Path(PROMPTS_DIR) / f"{function_name}.txt"
    if global_prompt.is_file():
        return PlainTextResponse(global_prompt.read_text(encoding="utf-8"))

    # 3. Hardcoded fallback
    fallback = _FALLBACK_PROMPTS.get(function_name)
    if fallback:
        return PlainTextResponse(fallback)

    return PlainTextResponse(
        f"No prompt template found for '{function_name}'.",
        status_code=404
    )


def parse_html_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"filename": os.path.basename(file_path), "error": str(e)}
    
    soup = BeautifulSoup(content, 'html.parser')
    links = []
    metadata = {}
    
    a_tags = soup.find_all('a')
    for a in a_tags:
        # Extract data attributes
        data_attrs = {k.replace('data-', ''): v for k, v in a.attrs.items() if k.startswith('data-')}
        
        # Populate metadata once from the first link (as they share lesson/core/agent-text)
        if not metadata and data_attrs:
            metadata = {
                "lesson": data_attrs.get("lesson", ""),
                "concept": data_attrs.get("core", ""),
                "clarification": data_attrs.get("agent-text", "")
            }
        
        links.append({
            "label": a.text.strip(),
            "data": data_attrs
        })
        
    return {
        "filename": os.path.basename(file_path),
        "metadata": metadata,
        "links": links
    }

@router.get("/index")
async def get_syllabus_index():
    """
    Recursively scans the syllabus directory, parses HTML files, and builds a strict-sorted JSON tree.
    """
    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return {"error": "Data directory not found."}

    def build_tree(current_path):
        tree = {}
        
        # Get directories and sort them alphabetically
        dirs = [d for d in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, d))]
        dirs.sort() # Enforces 01_unit, 02_unit order
        
        for d in dirs:
            subtree = build_tree(os.path.join(current_path, d))
            # Only add to tree if it's not empty or if it's a leaf
            if subtree or any(f.endswith('.html') for f in os.listdir(os.path.join(current_path, d))):
                tree[d] = subtree
                
        # Get HTML files
        files = [f for f in os.listdir(current_path) if os.path.isfile(os.path.join(current_path, f)) and f.endswith('.html')]
        
        # Sort files: core_ first, then related_, then others alphabetically
        def file_sort_key(f):
            if f.startswith('core_'):
                return (0, f)
            elif f.startswith('related_'):
                return (1, f)
            return (2, f)
            
        files.sort(key=file_sort_key)
        
        if files:
            parsed_files = []
            for f in files:
                parsed = parse_html_file(os.path.join(current_path, f))
                parsed_files.append(parsed)
            tree["_files"] = parsed_files
            
        return tree

    return build_tree(base_path)


@router.get("/meta")
async def get_syllabus_meta():
    """
    Auto-discovers all syllabus.json files under SYLLABUS_DIR.
    Infers exam/course context from the directory path.
    Returns an array of all discovered syllabi for the History filter tree.
    
    Expected structure:
      SYLLABUS_DIR/
        CSIR_Physical_Sciences/   ← top-level folder (exam context)
          phys100/                ← course folder
            syllabus.json         ← discovered here
            unit_01/
              unit_1A/
                core_xxx.html
    """
    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return []

    result = []
    for syllabus_file in base_path.rglob("syllabus.json"):
        try:
            with open(syllabus_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Infer context from directory path
            # e.g., CSIR_Physical_Sciences/phys100/syllabus.json
            rel_path = syllabus_file.relative_to(base_path)
            parts = rel_path.parts[:-1]  # Remove 'syllabus.json' itself

            # First part = exam/program folder, rest = course context
            data["_exam_folder"] = parts[0].replace('_', ' ') if len(parts) > 0 else "General"
            data["_course_folder"] = parts[1] if len(parts) > 1 else ""
            data["_path"] = "/".join(parts)

            result.append(data)
        except Exception as e:
            result.append({
                "error": str(e),
                "path": str(syllabus_file)
            })

    return result
