"""Regenerate the synthetic fixture files in tests/fixtures/.

Run from the project folder:  python tests/make_fixtures.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import sample_data as sd  # noqa: E402

OUT = HERE / "fixtures"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sd.write_txt(OUT / "sample_resume_full.txt", sd.FULL_RESUME)
    sd.write_docx(OUT / "sample_resume_full.docx", sd.FULL_RESUME)
    sd.write_pdf(OUT / "sample_resume_full.pdf", sd.FULL_RESUME)
    sd.write_txt(OUT / "sample_resume_variant_headings.txt", sd.VARIANT_HEADINGS_RESUME)
    sd.write_txt(OUT / "sample_resume_no_contact.txt", sd.NO_CONTACT_RESUME)
    sd.write_txt(OUT / "sample_resume_no_sections.txt", sd.NO_SECTIONS_RESUME)
    sd.write_image_only_pdf(OUT / "image_only_scan_like.pdf")
    sd.write_encrypted_pdf(OUT / "encrypted.pdf")
    (OUT / "malformed.pdf").write_bytes(b"This is not really a PDF file.")
    (OUT / "malformed.docx").write_bytes(b"This is not really a DOCX file.")
    print("Fixtures written to", OUT)


if __name__ == "__main__":
    main()
