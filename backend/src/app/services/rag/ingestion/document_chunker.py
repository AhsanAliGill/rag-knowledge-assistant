import logging
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.config.rag_settings import rag_settings

logger = logging.getLogger(__name__)

# Strips inline header/footer lines that survive the parser stage because they
# appeared in the middle of a multi-line text element rather than as their own element.
_INLINE_FOOTER_RE = re.compile(
    r"(?im)^[ \t]*[\s\S]{0,120}(?:manual|handbook|guide|policy|procedure)"
    r"[\s\S]{0,60}(?:v\s*\d+[\.\d]*|version\s*\d+[\.\d]*)"
    r"[\s\S]{0,40}page\s+\d+\s+of\s+\d+[ \t]*$\n?"
)


def _clean_chunk(text: str) -> str:
    return _INLINE_FOOTER_RE.sub("", text).strip()


class HierarchicalChunker:
    """
    Table-aware parent-child chunker.

    Strategy:
    - Table elements  → stored as ONE child chunk (entire table preserved, no splitting)
    - Text elements   → split into small child chunks via RecursiveCharacterTextSplitter
    - Every child maps back to a parent via parent_id_key for context expansion
    """

    def __init__(self) -> None:
        self._child_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=rag_settings.CHILD_CHUNK_SIZE,
            chunk_overlap=rag_settings.CHILD_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", ", ", " ", ""],
        )

    def chunk(self, docs: list[Document]) -> tuple[list[Document], list[Document]]:
        """Returns (parent_chunks, child_chunks)."""
        parents: list[Document] = []
        children: list[Document] = []

        for i, doc in enumerate(docs):
            parent_id_key = f"parent_{i:05d}"
            category = doc.metadata.get("category", "NarrativeText")
            page_num = doc.metadata.get("page_number")

            # Parent = full element (section, page, or table)
            parents.append(Document(
                page_content=doc.page_content,
                metadata={
                    **doc.metadata,
                    "chunk_type": "parent",
                    "chunk_id_key": parent_id_key,
                    "parent_id": None,
                    "page_num": page_num,
                    "element_type": category,
                },
            ))

            if category == "Table":
                # Critical: preserve entire table as a single child chunk
                # This prevents column/row leakage during retrieval
                children.append(Document(
                    page_content=_clean_chunk(doc.page_content),
                    metadata={
                        **doc.metadata,
                        "chunk_type": "child",
                        "chunk_id_key": f"{parent_id_key}_c0000",
                        "parent_id": parent_id_key,
                        "child_index": 0,
                        "page_num": page_num,
                        "element_type": "Table",
                    },
                ))
                logger.debug("Table preserved as single chunk | key=%s page=%s", parent_id_key, page_num)
            else:
                # Text/Title/List: split into small semantic child chunks
                child_docs = self._child_splitter.split_documents([doc])
                for j, child in enumerate(child_docs):
                    cleaned = _clean_chunk(child.page_content)
                    if not cleaned:
                        continue
                    child.page_content = cleaned
                    child.metadata.update({
                        "chunk_type": "child",
                        "chunk_id_key": f"{parent_id_key}_c{j:04d}",
                        "parent_id": parent_id_key,
                        "child_index": j,
                        "page_num": page_num,
                        "element_type": category,
                    })
                    children.append(child)

        table_count = sum(1 for p in parents if p.metadata.get("element_type") == "Table")
        logger.info(
            "Chunking done | parents=%d children=%d tables=%d",
            len(parents), len(children), table_count,
        )
        return parents, children
