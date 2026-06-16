"""
Pure unit tests for RAG service components.

No database, no HTTP client, no external API calls.
All LLM interactions are replaced with AsyncMock / MagicMock.

Covered:
  - history_summarizer  : _estimate_tokens, compress_history
  - query_rewriter      : rewrite_query
  - BM25Indexer         : build, search, _tokenize
  - HierarchicalChunker : chunk (table vs text handling)
  - MetadataTagger      : tag (namespace, chunk_id, offset)
  - pipeline            : _to_lc_messages helper
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from app.services.rag.generation.history_summarizer import (
    MAX_HISTORY_TOKENS,
    RECENT_KEEP,
    _estimate_tokens,
    compress_history,
)
from app.services.rag.ingestion.bm25_keyword_indexer import BM25Indexer
from app.services.rag.ingestion.chunk_tagger import MetadataTagger
from app.services.rag.ingestion.document_chunker import HierarchicalChunker
from app.services.rag.pipeline import _to_lc_messages
from app.services.rag.retrieval.query_rewriter import rewrite_query

# ── helpers ───────────────────────────────────────────────────────────────────


def _history(n_pairs: int, chars_each: int = 10) -> list[dict]:
    content = "x" * chars_each
    return [
        msg
        for _ in range(n_pairs)
        for msg in (
            {"role": "user", "content": content},
            {"role": "assistant", "content": content},
        )
    ]


def _make_docs(texts: list[str], category: str = "NarrativeText") -> list[Document]:
    return [
        Document(page_content=t, metadata={"category": category, "page_number": 1}) for t in texts
    ]


def _bm25_indexer(tmp_path):
    """Build a BM25Indexer whose _dir points to pytest's tmp_path (no __init__ I/O)."""
    indexer = BM25Indexer.__new__(BM25Indexer)
    indexer._dir = tmp_path
    return indexer


# ─────────────────────────────────────────────────────────────────────────────
# history_summarizer
# ─────────────────────────────────────────────────────────────────────────────


class TestEstimateTokens:
    def test_empty(self):
        assert _estimate_tokens([]) == 0

    def test_single_message(self):
        assert _estimate_tokens([{"role": "user", "content": "abcd"}]) == 1  # 4 chars / 4

    def test_multiple_messages(self):
        msgs = [
            {"role": "user", "content": "x" * 400},
            {"role": "assistant", "content": "y" * 800},
        ]
        assert _estimate_tokens(msgs) == 300  # 1200 / 4


class TestCompressHistory:
    async def test_empty_history_returned_unchanged(self):
        llm = MagicMock()
        assert await compress_history([], llm) == []
        llm.ainvoke.assert_not_called()

    async def test_short_history_returned_unchanged(self):
        history = _history(2, chars_each=5)  # tiny — well under token limit
        llm = MagicMock()
        result = await compress_history(history, llm)
        assert result == history
        llm.ainvoke.assert_not_called()

    async def test_not_compressed_when_len_lte_recent_keep(self):
        """Even if content is large, we cannot split if len(history) <= RECENT_KEEP."""
        # 3 pairs = 6 messages = exactly RECENT_KEEP; each message is huge
        history = _history(n_pairs=RECENT_KEEP // 2, chars_each=MAX_HISTORY_TOKENS * 4)
        llm = MagicMock()
        result = await compress_history(history, llm)
        assert result == history
        llm.ainvoke.assert_not_called()

    async def test_compresses_when_over_limit(self):
        """When tokens > MAX_HISTORY_TOKENS AND len > RECENT_KEEP, LLM is called."""
        # Need: total chars > MAX_HISTORY_TOKENS * 4
        # And:  len(history) > RECENT_KEEP (6)
        chars_per_msg = (MAX_HISTORY_TOKENS * 4) // 4  # each of 4 msgs already hits limit
        history = _history(n_pairs=RECENT_KEEP, chars_each=chars_per_msg)
        # len = RECENT_KEEP * 2 = 12 > 6 ✓

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Summary of old messages.")

        result = await compress_history(history, mock_llm)

        mock_llm.ainvoke.assert_called_once()
        assert len(result) == RECENT_KEEP + 1  # [summary] + last RECENT_KEEP msgs

    async def test_summary_message_at_front(self):
        chars_per_msg = (MAX_HISTORY_TOKENS * 4) // 4
        history = _history(n_pairs=RECENT_KEEP, chars_each=chars_per_msg)
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="The user asked about leave.")

        result = await compress_history(history, mock_llm)

        assert result[0]["role"] == "assistant"
        assert "[Earlier conversation summary]" in result[0]["content"]

    async def test_recent_messages_preserved_verbatim(self):
        chars_per_msg = (MAX_HISTORY_TOKENS * 4) // 4
        history = _history(n_pairs=RECENT_KEEP, chars_each=chars_per_msg)
        expected_recent = history[-RECENT_KEEP:]

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Old summary.")

        result = await compress_history(history, mock_llm)
        assert result[1:] == expected_recent


# ─────────────────────────────────────────────────────────────────────────────
# query_rewriter
# ─────────────────────────────────────────────────────────────────────────────


class TestRewriteQuery:
    async def test_returns_none_for_no_retrieval_token(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="[NO_RETRIEVAL]")
        result = await rewrite_query(
            "thanks",
            [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
            llm,
        )
        assert result is None

    async def test_no_retrieval_token_embedded_in_text(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="Sure: [NO_RETRIEVAL] — chitchat detected.")
        result = await rewrite_query("ok", [], llm)
        assert result is None

    async def test_returns_standalone_question(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="What is the annual leave entitlement?")
        result = await rewrite_query(
            "How many days?",
            [
                {"role": "user", "content": "Tell me about leave."},
                {"role": "assistant", "content": "Employees get 20 days."},
            ],
            llm,
        )
        assert result == "What is the annual leave entitlement?"

    async def test_strips_whitespace_from_result(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="  Rewritten question.  ")
        result = await rewrite_query("follow up", [], llm)
        assert result == "Rewritten question."

    async def test_builds_correct_message_sequence(self):
        """History must be interleaved as Human/AI before the current question."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="Standalone q.")

        history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply1"},
        ]
        await rewrite_query("follow", history, llm)

        msgs = llm.ainvoke.call_args[0][0]
        # [SystemMessage, HumanMessage(msg1), AIMessage(reply1), HumanMessage(follow)]
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "msg1"
        assert isinstance(msgs[2], AIMessage)
        assert msgs[2].content == "reply1"
        assert isinstance(msgs[3], HumanMessage)
        assert msgs[3].content == "follow"

    async def test_empty_history_still_works(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="Standalone question.")
        result = await rewrite_query("What are the benefits?", [], llm)
        assert result == "Standalone question."


# ─────────────────────────────────────────────────────────────────────────────
# BM25Indexer
# ─────────────────────────────────────────────────────────────────────────────


class TestBM25Tokenizer:
    """Tests for the internal _tokenize method (no disk I/O needed)."""

    def setup_method(self):
        self.idx = BM25Indexer.__new__(BM25Indexer)

    def test_lowercases_input(self):
        tokens = self.idx._tokenize("Annual Leave Policy")
        assert all(t == t.lower() for t in tokens)

    def test_removes_stopwords(self):
        tokens = self.idx._tokenize("the leave policy is for all employees")
        for stop in ("the", "is", "for"):
            assert stop not in tokens
        assert "leave" in tokens
        assert "policy" in tokens

    def test_removes_single_character_tokens(self):
        tokens = self.idx._tokenize("a b cd leave")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens

    def test_empty_string_returns_empty(self):
        assert self.idx._tokenize("") == []

    def test_special_chars_removed(self):
        tokens = self.idx._tokenize("leave! policy? (2024)")
        assert "leave" in tokens
        assert "policy" in tokens
        # parentheses stripped
        assert "(2024)" not in tokens


class TestBM25BuildAndSearch:
    def test_search_returns_empty_when_no_index(self, tmp_path):
        idx = _bm25_indexer(tmp_path)
        assert idx.search("leave policy", "missing_namespace") == []

    def test_build_creates_pkl_file(self, tmp_path):
        idx = _bm25_indexer(tmp_path)
        idx.build(_make_docs(["Employees get 20 days annual leave."]), "ns_a")
        assert (tmp_path / "ns_a.pkl").exists()

    def test_search_finds_relevant_chunk(self, tmp_path):
        # BM25Okapi IDF = log((N-df+0.5)/(df+0.5)); with N=2 and df=1 this is 0.
        # Need N >= 3 so terms get a positive IDF and non-zero scores.
        idx = _bm25_indexer(tmp_path)
        docs = [
            Document(
                page_content="Employees get 20 days annual leave.",
                metadata={"chunk_id": "id_001", "doc_id": "d1"},
            ),
            Document(
                page_content="Sick leave is 10 days per year.",
                metadata={"chunk_id": "id_002", "doc_id": "d1"},
            ),
            Document(
                page_content="Overtime compensation rules.",
                metadata={"chunk_id": "id_003", "doc_id": "d1"},
            ),
        ]
        idx.build(docs, "ns_b")
        results = idx.search("annual leave", "ns_b", k=5)
        assert len(results) >= 1
        chunk_ids = [r[0] for r in results]
        assert "id_001" in chunk_ids

    def test_search_excludes_zero_score(self, tmp_path):
        """Results with BM25 score of 0 must be filtered out."""
        idx = _bm25_indexer(tmp_path)
        idx.build(_make_docs(["apple orange banana fruit"], category="NarrativeText"), "ns_c")
        results = idx.search("quantum nuclear reactor", "ns_c", k=5)
        for _, score, _ in results:
            assert score > 0

    def test_search_returns_tuple_of_chunk_id_score_text(self, tmp_path):
        idx = _bm25_indexer(tmp_path)
        docs = [
            Document(
                page_content="leave policy annual days", metadata={"chunk_id": "cid", "doc_id": "d"}
            ),
            Document(
                page_content="overtime compensation salary",
                metadata={"chunk_id": "cid2", "doc_id": "d"},
            ),
            Document(
                page_content="travel reimbursement expense",
                metadata={"chunk_id": "cid3", "doc_id": "d"},
            ),
        ]
        idx.build(docs, "ns_d")
        results = idx.search("leave", "ns_d", k=1)
        assert len(results) == 1
        cid, score, text = results[0]
        assert cid == "cid"
        assert isinstance(score, float)
        assert "leave" in text

    def test_rebuild_overwrites_existing_index(self, tmp_path):
        idx = _bm25_indexer(tmp_path)
        idx.build(_make_docs(["old content alpha"]), "ns_e")
        # Rebuild with 3 docs so BM25 IDF is positive for discriminating terms
        idx.build(
            _make_docs(["new content beta gamma", "unrelated words here", "another filler chunk"]),
            "ns_e",
        )
        results = idx.search("beta", "ns_e", k=5)
        assert len(results) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# HierarchicalChunker
# ─────────────────────────────────────────────────────────────────────────────


class TestHierarchicalChunker:
    def setup_method(self):
        self.chunker = HierarchicalChunker()

    def _doc(self, content: str, category: str = "NarrativeText", page: int = 1) -> Document:
        return Document(page_content=content, metadata={"category": category, "page_number": page})

    def test_parent_count_equals_input_doc_count(self):
        docs = [self._doc("Text A"), self._doc("| A | B |", "Table"), self._doc("Text C")]
        parents, _ = self.chunker.chunk(docs)
        assert len(parents) == 3

    def test_table_is_single_child_chunk(self):
        docs = [self._doc("Col A | Col B\nVal 1 | Val 2", "Table")]
        _, children = self.chunker.chunk(docs)
        table_children = [c for c in children if c.metadata.get("element_type") == "Table"]
        assert len(table_children) == 1

    def test_text_element_produces_at_least_one_child(self):
        docs = [self._doc("This is a narrative text element.")]
        _, children = self.chunker.chunk(docs)
        assert len(children) >= 1

    def test_long_text_is_split_into_multiple_children(self):
        # Long enough to force a split (500 tokens chunk_size)
        long_text = "This is a sentence with some words. " * 200
        docs = [self._doc(long_text)]
        _, children = self.chunker.chunk(docs)
        assert len(children) >= 2

    def test_children_have_parent_id(self):
        docs = [self._doc("Some content here.")]
        _, children = self.chunker.chunk(docs)
        for child in children:
            assert child.metadata.get("parent_id") is not None

    def test_parents_have_no_parent_id(self):
        docs = [self._doc("Content.")]
        parents, _ = self.chunker.chunk(docs)
        for parent in parents:
            assert parent.metadata.get("parent_id") is None

    def test_child_chunk_type_is_child(self):
        docs = [self._doc("Content here.")]
        _, children = self.chunker.chunk(docs)
        for child in children:
            assert child.metadata["chunk_type"] == "child"

    def test_parent_chunk_type_is_parent(self):
        docs = [self._doc("Content here.")]
        parents, _ = self.chunker.chunk(docs)
        for parent in parents:
            assert parent.metadata["chunk_type"] == "parent"

    def test_empty_children_are_dropped(self):
        docs = [self._doc("   ")]
        _, children = self.chunker.chunk(docs)
        for child in children:
            assert child.page_content.strip() != ""

    def test_page_num_propagated_to_children(self):
        docs = [self._doc("Content on page 7.", page=7)]
        _, children = self.chunker.chunk(docs)
        for child in children:
            assert child.metadata["page_num"] == 7


# ─────────────────────────────────────────────────────────────────────────────
# MetadataTagger
# ─────────────────────────────────────────────────────────────────────────────


class TestMetadataTagger:
    def setup_method(self):
        self.tagger = MetadataTagger()
        self.doc_id = uuid.uuid4()
        self.user_id = uuid.uuid4()

    def _chunks(self, n: int) -> list[Document]:
        return [Document(page_content=f"content {i}", metadata={}) for i in range(n)]

    def test_user_corpus_namespace(self):
        tagged = self.tagger.tag(self._chunks(1), self.doc_id, self.user_id)
        assert tagged[0].metadata["namespace"] == f"user_{self.user_id}"

    def test_none_user_id_namespace(self):
        tagged = self.tagger.tag(self._chunks(1), self.doc_id, None)
        assert tagged[0].metadata["namespace"] == f"user_{None}"

    def test_chunk_id_format_from_zero(self):
        tagged = self.tagger.tag(self._chunks(3), self.doc_id, self.user_id, 0)
        for i, t in enumerate(tagged):
            assert t.metadata["chunk_id"] == f"{str(self.doc_id)[:8]}_{i:06d}"

    def test_chunk_id_format_with_offset(self):
        tagged = self.tagger.tag(self._chunks(2), self.doc_id, self.user_id, 10)
        assert tagged[0].metadata["chunk_id"] == f"{str(self.doc_id)[:8]}_000010"
        assert tagged[1].metadata["chunk_id"] == f"{str(self.doc_id)[:8]}_000011"

    def test_doc_id_is_string(self):
        tagged = self.tagger.tag(self._chunks(1), self.doc_id, self.user_id)
        assert tagged[0].metadata["doc_id"] == str(self.doc_id)

    def test_user_id_is_string(self):
        tagged = self.tagger.tag(self._chunks(1), self.doc_id, self.user_id)
        assert tagged[0].metadata["user_id"] == str(self.user_id)

    def test_none_user_id_stored_as_string(self):
        tagged = self.tagger.tag(self._chunks(1), self.doc_id, None)
        assert tagged[0].metadata["user_id"] == "None"

    def test_existing_metadata_preserved(self):
        chunks = [Document(page_content="text", metadata={"page_number": 3, "category": "Table"})]
        tagged = self.tagger.tag(chunks, self.doc_id, self.user_id)
        assert tagged[0].metadata["page_number"] == 3
        assert tagged[0].metadata["category"] == "Table"

    def test_output_length_matches_input(self):
        chunks = self._chunks(5)
        tagged = self.tagger.tag(chunks, self.doc_id, self.user_id)
        assert len(tagged) == 5


# ─────────────────────────────────────────────────────────────────────────────
# pipeline._to_lc_messages
# ─────────────────────────────────────────────────────────────────────────────


class TestToLcMessages:
    def test_empty_history_returns_empty_list(self):
        assert _to_lc_messages([]) == []

    def test_user_role_becomes_human_message(self):
        msgs = _to_lc_messages([{"role": "user", "content": "hello"}])
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "hello"

    def test_assistant_role_becomes_ai_message(self):
        msgs = _to_lc_messages([{"role": "assistant", "content": "world"}])
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].content == "world"

    def test_alternating_roles_preserved(self):
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        msgs = _to_lc_messages(history)
        assert len(msgs) == 4
        assert isinstance(msgs[0], HumanMessage)
        assert isinstance(msgs[1], AIMessage)
        assert isinstance(msgs[2], HumanMessage)
        assert isinstance(msgs[3], AIMessage)

    def test_content_preserved(self):
        history = [{"role": "user", "content": "test content 123"}]
        msgs = _to_lc_messages(history)
        assert msgs[0].content == "test content 123"
