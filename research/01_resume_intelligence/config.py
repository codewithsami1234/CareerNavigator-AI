"""Central configuration for the resume-intelligence pipeline.

Everything that is a tunable threshold or a file location lives here so the
rest of the code contains no magic numbers. Phase 1 thresholds are unchanged.
Phase 2 image, OCR and layout settings are grouped at the bottom of this file.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Editable data files (kept outside the Python code on purpose).
SKILLS_TAXONOMY_PATH = DATA_DIR / "skills_taxonomy.json"
SECTION_ALIASES_PATH = DATA_DIR / "section_aliases.json"
JOB_SECTION_ALIASES_PATH = DATA_DIR / "job_section_aliases.json"

# ---- File validation -------------------------------------------------------
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def file_too_large_message(size_bytes: int) -> str:
    """Say how many bytes were received. One decimal place rounds 10 MiB + 1 byte to 10.0 MB."""
    return (
        f"File is too large ({size_bytes} bytes). "
        f"The limit is {MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_MB} MB)."
    )

# ---- Text-extraction quality checks ---------------------------------------
# Minimum number of letters/digits for a document to count as "has real text".
MIN_MEANINGFUL_CHARS = 50
# A PDF whose pages average fewer letters/digits than this is treated as
# image-only / non-extractable (OCR needed, Phase 2).
MIN_CHARS_PER_PDF_PAGE = 40
# A single page with fewer letters/digits than this is reported as "mostly empty".
MIN_CHARS_FOR_NONEMPTY_PAGE = 20
# Resumes are short; extra pages are ignored (with a warning).
MAX_PDF_PAGES = 30
# Vertical gap (as a fraction of line height) that counts as a paragraph break in PDFs.
PDF_PARAGRAPH_GAP_RATIO = 0.5

# ---- Section detection -----------------------------------------------------
# Headings that may carry content on the same line, e.g. "Skills: Python, SQL".
INLINE_HEADING_SECTIONS = {"skills", "languages", "certifications", "courses", "interests"}
MAX_HEADING_WORDS = 6
MAX_HEADING_CHARS = 70

# ---- Skill extraction ------------------------------------------------------
# A skill found in these sections counts as evidence of *use*; elsewhere it is
# only a *mention*. Proficiency is never inferred from either.
USED_EVIDENCE_SECTIONS = {"experience", "projects"}
# Sections that are never scanned for skills (contact details, human languages...).
SKILL_SCAN_EXCLUDED_SECTIONS = {"contact", "languages", "references", "interests", "declaration"}
MAX_EVIDENCE_PER_SKILL = 3
EVIDENCE_TEXT_MAX_CHARS = 200

SCHEMA_VERSION = "1.0"

# ---- Public GitHub metadata ------------------------------------------------
# Official API only. A token is optional and is read from the environment by
# the GitHub module; it is never written here.
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TIMEOUT_SECONDS = 15
GITHUB_CACHE_SECONDS = 900
GITHUB_MAX_REPOS = 8
GITHUB_README_SCAN_CHARS = 8000

# ---- Evidence-based readiness rubric ---------------------------------------
# These weights are an explicit preliminary rubric, not a trained model.
# A matched required item earns full credit. A related or missing required
# item earns none. Preferred and unverified items are reported and left out
# of the denominator so missing optional or unproven information is not scored
# as a failure.
READINESS_MATCHED_CREDIT = 1.0
READINESS_UNSATISFIED_CREDIT = 0.0

# ---- Phase 2: images, OCR, layout diagnostics ------------------------------
# Image types are accepted by the Phase 2 document interface only.
# ``parse_document`` / ``analyze_resume`` still allow PDF, DOCX and TXT.
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
PHASE2_EXTENSIONS = SUPPORTED_EXTENSIONS | IMAGE_EXTENSIONS

MAX_IMAGE_PIXELS = 25_000_000
MIN_IMAGE_SIDE_PX = 32
MAX_IMAGE_SIDE_PX = 10_000
# Resize bounds for OCR. Aspect ratio is preserved; upscaling is capped.
OCR_TARGET_MIN_WIDTH = 1400
OCR_MAX_WIDTH = 2400
OCR_MAX_UPSCALE = 3.0
PDF_RENDER_DPI = 200

# Skew search (degrees). Correction runs only when the estimate is large enough
# to matter and the corrected image scores at least as well as the original.
SKEW_SEARCH_DEGREES = 12.0
SKEW_SEARCH_STEP = 0.5
SKEW_CORRECT_MIN_DEGREES = 0.6

# A PDF page with at least this many letters/digits keeps its native text and
# is not sent to OCR. Below this, Phase 2 treats the page as scanned or sparse.
NATIVE_PAGE_SUFFICIENT_CHARS = 80

# Header/footer removal (text PDFs, 3+ pages only). Lines must sit in the
# margin and repeat; the first page keeps them.
PDF_MARGIN_TOP_RATIO = 0.09
PDF_MARGIN_BOTTOM_RATIO = 0.91
PDF_HEADER_MIN_PAGES = 3
PDF_MARGIN_LINE_MAX_CHARS = 80

# Quality warnings. These are heuristic thresholds, not pass/fail grades.
LOW_RESOLUTION_MIN_SIDE = 900
LOW_CONTRAST_STD = 28.0
EXCESSIVE_SKEW_DEGREES = 5.0
CROWDED_INK_RATIO = 0.42
BLANK_INK_RATIO = 0.005
LOW_OCR_CHARS = 80
# A page is unreadable only when low confidence agrees with a noisy page or
# with text that is not resume wording. Confidence alone does not reject it.
OCR_UNRELIABLE_MAX_CONFIDENCE = 45.0
OCR_UNRELIABLE_WORDLIKE_RATIO = 0.55
OCR_UNRELIABLE_MIN_COMMON_WORDS = 5
OCR_GIBBERISH_MAX_CONFIDENCE = 28.0
OCR_GIBBERISH_WORDLIKE_RATIO = 0.38
UNUSUAL_ASPECT_MIN = 0.55
UNUSUAL_ASPECT_MAX = 0.92

# Tesseract. ``TESSERACT_CMD`` is optional; the resolver also checks PATH and
# the default Windows install location. Empty string means "not set".
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip() or None
OCR_LANGUAGE = "eng"
OCR_OEM = 3
OCR_PSM = 6
OCR_TIMEOUT_SECONDS = 45
MAX_OCR_STRATEGY_ATTEMPTS = 2

# Provenance labels stored with extracted text.
METHOD_NATIVE_PDF = "native_pdf"
METHOD_NATIVE_DOCX = "native_docx"
METHOD_NATIVE_TEXT = "native_text"
METHOD_OCR = "ocr"

# ---- Local HTTP API --------------------------------------------------------
# Used only by the optional FastAPI process. Streamlit does not read these.
# A wildcard origin is never accepted. Set CAREERNAV_CORS_ORIGINS to a
# comma-separated list when the React dev server uses another origin.
API_HOST = "127.0.0.1"
API_PORT = 8000
API_DEFAULT_CORS_ORIGIN = "http://localhost:5173"


def api_cors_origins() -> list:
    """Return the allowed browser origins. ``*`` is ignored."""
    raw = os.environ.get(
        "CAREERNAV_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    origins = []
    for part in str(raw).split(","):
        origin = part.strip().rstrip("/")
        if origin and origin != "*":
            origins.append(origin)
    # Hosted platforms often expose the public HTTPS origin this way.
    for key in ("RENDER_EXTERNAL_URL", "BLITZ_APP_URL", "PUBLIC_APP_URL"):
        hosted = os.environ.get(key, "").strip().rstrip("/")
        if hosted and hosted not in origins:
            origins.append(hosted)
    if not origins:
        return [API_DEFAULT_CORS_ORIGIN]
    return origins
