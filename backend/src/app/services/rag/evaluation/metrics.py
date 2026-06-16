from dataclasses import dataclass


@dataclass
class MetricSet:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float

    @property
    def overall(self) -> float:
        return (
            self.faithfulness + self.answer_relevancy + self.context_precision + self.context_recall
        ) / 4


class RAGMetricsEvaluator:
    async def evaluate_single(
        self,
        question: str,
        generated_answer: str,
        contexts: list[str],
        ground_truth: str,
    ) -> MetricSet:
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )

            data = Dataset.from_dict(
                {
                    "question": [question],
                    "answer": [generated_answer],
                    "contexts": [contexts],
                    "ground_truth": [ground_truth],
                }
            )
            result = evaluate(
                data,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            )
            return MetricSet(
                faithfulness=float(result["faithfulness"]),
                answer_relevancy=float(result["answer_relevancy"]),
                context_precision=float(result["context_precision"]),
                context_recall=float(result["context_recall"]),
            )
        except Exception:
            return MetricSet(
                faithfulness=0.0,
                answer_relevancy=0.0,
                context_precision=0.0,
                context_recall=0.0,
            )
