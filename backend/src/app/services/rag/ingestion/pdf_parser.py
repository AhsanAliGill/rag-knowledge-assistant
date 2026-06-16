import hashlib
import logging
import re
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_HEADER_FOOTER_RE = re.compile(
    r"(?i)^[\s\S]{0,120}(?:manual|handbook|guide|policy|procedure)"
    r"[\s\S]{0,60}(?:v\s*\d+[\.\d]*|version\s*\d+[\.\d]*)"
    r"[\s\S]{0,40}page\s+\d+\s+of\s+\d+[\s\S]{0,40}$"
)


def _is_header_footer(text: str) -> bool:
    return bool(_HEADER_FOOTER_RE.match(text.strip()))


class DocumentParser:
    """
    PDF parser using PyMuPDF (fitz) — 10-50x faster than pdfminer/Unstructured.
    Each page becomes one Document with page_number metadata.
    Header/footer boilerplate is removed before elements are returned.
    """

    def parse(
        self,
        file_path: str,
        table_pages: list[int] | None = None,
    ) -> tuple[list[Document], int, str]:
        path = Path(file_path)
        logger.info("Parsing PDF: %s (%.1f MB)", path.name, path.stat().st_size / 1_048_576)

        loader = PyMuPDFLoader(file_path)
        elements: list[Document] = loader.load()

        if not elements:
            logger.warning("No elements extracted from: %s", file_path)
            return [], 0, ""

        # PyMuPDF uses 0-based "page" key — normalise to 1-based "page_number"
        # so the rest of the pipeline (chunk_tagger, _save_chunks) stays unchanged.
        for e in elements:
            if "page" in e.metadata:
                e.metadata["page_number"] = e.metadata.pop("page") + 1

        page_count = max(
            (int(e.metadata.get("page_number", 0)) for e in elements),
            default=0,
        )

        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

        before = len(elements)
        elements = [e for e in elements if not _is_header_footer(e.page_content)]
        dropped = before - len(elements)
        if dropped:
            logger.info("Dropped %d header/footer elements", dropped)

        logger.info(
            "Parsed %d pages | sha256=%s...",
            page_count, sha256[:12],
        )
        return elements, page_count, sha256
