import uuid

from langchain_core.documents import Document


class MetadataTagger:
    def tag(
        self,
        chunks: list[Document],
        doc_id: uuid.UUID,
        user_id: uuid.UUID,
        chunk_offset: int = 0,
    ) -> list[Document]:
        namespace = f"user_{user_id}"
        tagged: list[Document] = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{str(doc_id)[:8]}_{chunk_offset + i:06d}"
            tagged.append(
                Document(
                    page_content=chunk.page_content,
                    metadata={
                        **chunk.metadata,
                        "chunk_id": chunk_id,
                        "doc_id": str(doc_id),
                        "user_id": str(user_id),
                        "namespace": namespace,
                    },
                )
            )

        return tagged
