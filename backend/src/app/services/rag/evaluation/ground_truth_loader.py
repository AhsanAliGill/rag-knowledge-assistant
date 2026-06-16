import json
from dataclasses import dataclass
from pathlib import Path

from app.services.config.rag_settings import rag_settings


@dataclass
class QAPair:
    question: str
    expected_answer: str
    source_section: str | None


class GroundTruthStore:
    def __init__(self) -> None:
        self._dir = Path(rag_settings.GROUND_TRUTH_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, doc_id: str, pairs: list[dict]) -> None:
        with open(self._dir / f"{doc_id}.json", "w") as f:
            json.dump(pairs, f, indent=2)

    def load(self, doc_id: str) -> list[QAPair]:
        path = self._dir / f"{doc_id}.json"
        if not path.exists():
            return []
        with open(path) as f:
            data = json.load(f)
        return [
            QAPair(
                question=item["question"],
                expected_answer=item["expected_answer"],
                source_section=item.get("source_section"),
            )
            for item in data
        ]

    def exists(self, doc_id: str) -> bool:
        return (self._dir / f"{doc_id}.json").exists()

    def count(self, doc_id: str) -> int:
        return len(self.load(doc_id))
