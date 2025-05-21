import re
import json
import math
import pickle
import asyncio
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Callable, Any, Tuple, Optional, Union

from core.base.schema import Document

from services.tools.prompt import (
    load_prompt,
    apply_chat_template,
    prepare_chat_messages
)

# Đường dẫn lưu trữ mặc định cho index BM25
DEFAULT_SAVE_PATH = Path("./data")
# Tên file lưu trữ index (pickle)
DEFAULT_INDEX_FILE = DEFAULT_SAVE_PATH / "bm25_index.pkl"

class BM25Retriever:
    def __init__(
        self,
        llm_stemmer: Callable,
        agent_prompt_path: str = None,
        prompt_template_path: str = None,
        k1: float = 1.5,
        b: float = 0.75
    ):
        self.agent_prompt = load_prompt("api/config/prompts.yaml")
        if not isinstance(self.agent_prompt, dict):
            self.agent_prompt = {}

        self.prompt_template = load_prompt("core/config/base.yaml")
        if not isinstance(self.prompt_template, dict):
            self.prompt_template = {}

        self.llm_stemmer = llm_stemmer
        self.k1 = k1
        self.b = b

        if DEFAULT_INDEX_FILE.exists():
            self._load_state()
        else:
            self._reset()

    def _reset(self):
        """
        Reset all internal data structures.
        """
        self.documents: List[Document] = []
        self.doc_term_freqs: List[Dict[str, int]] = []
        self.doc_lengths: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.avgdl: float = 0.0
        self.total_docs: int = 0
        self.idf: Dict[str, float] = {}
        self.doc_norm: List[float] = []
        self.inverted_index: Dict[str, List[int]] = {}

    def json_parser(
        self,
        response: str
    ):
        try:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = response.strip()
            json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
            result = json.loads(json_str)
            return result['tokens']
        except Exception:
            return []

    async def stemming(self, text: str) -> List[str]:
        prompt = apply_chat_template(template=self.prompt_template, **{**self.agent_prompt['gemini_tokenizer'], **{'input': text}})
        messages = prepare_chat_messages(prompt=prompt)

        response = await self.llm_stemmer(messages)

        return self.json_parser(response)

    async def tokenize(self, text: str) -> List[str]:
        import tiktoken
        encoding = tiktoken.get_encoding("o200k_base")
        return [encoding.decode_single_token_bytes(token).strip() for token in encoding.encode(text)]

    async def add_document(
        self,
        docs: Union[Document, List[Document]],
        batch_size: int = 64
    ) -> None:
        """
        Thêm một hoặc nhiều Document vào index theo từng batch nhỏ,
        đồng thời đảm bảo tính chính xác của TF, DF, IDF, avgdl và doc_norm.
        """
        # 1. Chuẩn hóa thành list
        if not isinstance(docs, list):
            docs = [docs]

        # 2. Stem từng batch để giới hạn concurrency
        all_token_lists: List[List[str]] = []
        for start in range(0, len(docs), batch_size):
            batch = docs[start:start + batch_size]
            stem_tasks = [self.tokenize(doc.text) for doc in batch]
            stemmed = await asyncio.gather(*stem_tasks)
            all_token_lists.extend(stemmed)
            if start + batch_size < len(docs):
                # Giới hạn tốc độ để tránh quá tải
                # Chờ 30 giây giữa các batch
                import time
                time.sleep(30)

        # 3. Tính TF và độ dài document mới
        new_tfs = [Counter(tokens) for tokens in all_token_lists]
        new_lengths = [len(tokens) for tokens in all_token_lists]

        # 4. Cập nhật documents, term freqs, lengths
        start_index = self.total_docs
        for doc, tf, dl in zip(docs, new_tfs, new_lengths):
            self.documents.append(doc)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(dl)
        old_total = self.total_docs
        self.total_docs += len(docs)

        # 5. Cập nhật avgdl
        sum_new_lengths = sum(new_lengths)
        self.avgdl = (
            (self.avgdl * old_total + sum_new_lengths) / self.total_docs
            if old_total > 0 else sum_new_lengths / self.total_docs
        )

        # 6. Cập nhật DF và inverted_index
        for offset, tf in enumerate(new_tfs):
            idx = start_index + offset
            for term in tf:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
                self.inverted_index.setdefault(term, []).append(idx)

        # 7. Tính lại IDF cho toàn bộ terms
        N = self.total_docs
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        # 8. Tính lại doc_norm cho tất cả tài liệu
        self.doc_norm = [
            self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            for dl in self.doc_lengths
        ]

    async def delete_by_file_name(self, file_name: str) -> None:
        """
        Xóa tất cả document có metadata['file_name'] == file_name và rebuild index.
        """

        # 1. Tìm index của docs cần xóa
        remove_idxs = [
            i for i, doc in enumerate(self.documents)
            if doc.metadata.get('file_name') == file_name
        ]
        if not remove_idxs:
            return  # Không có document nào trùng file_name

        # 2. Tính tổng độ dài của docs bị xóa
        removed_len = sum(self.doc_lengths[i] for i in remove_idxs)
        old_total = self.total_docs

        # 3. Cập nhật total_docs và avgdl
        self.total_docs = old_total - len(remove_idxs)
        if self.total_docs > 0:
            self.avgdl = (self.avgdl * old_total - removed_len) / self.total_docs
        else:
            self.avgdl = 0.0

        # 4. Cập nhật doc_freqs và idf
        for i in remove_idxs:
            tf = self.doc_term_freqs[i]
            for term in tf.keys():
                # Giảm df
                self.doc_freqs[term] -= 1
                if self.doc_freqs[term] <= 0:
                    # Nếu df về 0, xóa hoàn toàn term
                    del self.doc_freqs[term]
                    del self.idf[term]
                else:
                    # Tính lại idf cho term còn tồn tại
                    df = self.doc_freqs[term]
                    N = self.total_docs
                    self.idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        # 5. Loại bỏ document ra khỏi lists, theo thứ tự giảm dần để không lệch index
        for idx in sorted(remove_idxs, reverse=True):
            del self.documents[idx]
            del self.doc_term_freqs[idx]
            del self.doc_lengths[idx]

        # 6. Xây dựng lại inverted_index từ doc_term_freqs hiện tại
        self.inverted_index = defaultdict(list)
        for i, tf in enumerate(self.doc_term_freqs):
            for term in tf.keys():
                self.inverted_index[term].append(i)

        # 7. Tính lại doc_norm cho các document còn lại
        self.doc_norm = [
            self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            for dl in self.doc_lengths
        ]

    async def get_scores(self, query: str) -> List[Tuple[Document, float]]:
        if not query.strip():
            return [(doc, 0.0) for doc in self.documents]

        qf_counts = Counter(await self.tokenize(query))
        scores: Dict[int, float] = defaultdict(float)
        k1p = self.k1 + 1

        for term, qf in qf_counts.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            for idx in self.inverted_index.get(term, []):
                tf = self.doc_term_freqs[idx].get(term, 0)
                denom = tf + self.doc_norm[idx]
                scores[idx] += idf * tf * k1p / denom * qf

        # Convert to list and sort
        ranked = [(self.documents[i], score) for i, score in scores.items()]
        return sorted(ranked, key=lambda x: x[1], reverse=True)

    async def get_top_k(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        scores = await self.get_scores(query)
        return scores[:k]

    async def get_relevance_metrics(self, query: str) -> Dict[str, Any]:
        tokens = await self.tokenize(query)
        return {
            'query_tokens': tokens,
            'unique_query_terms': len(set(tokens)),
            'total_query_terms': len(tokens),
            'terms_with_idf': [t for t in set(tokens) if t in self.idf],
            'terms_without_idf': [t for t in set(tokens) if t not in self.idf]
        }

    def save_index(self):
        file_path = DEFAULT_INDEX_FILE
        DEFAULT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        state = {
            'docs': [
                {'text': d.text,
                 'metadata': getattr(d, 'metadata', {}),
                 'id': getattr(d, 'id_', None)}
                for d in self.documents
            ],
            'k1': self.k1,
            'b': self.b,
            'doc_term_freqs': self.doc_term_freqs,
            'doc_lengths': self.doc_lengths,
            'doc_freqs': self.doc_freqs,
            'avgdl': self.avgdl,
            'total_docs': self.total_docs,
            'idf': self.idf,
            'doc_norm': self.doc_norm,
            'inverted_index': self.inverted_index
        }
        with open(file_path, 'wb') as f:
            pickle.dump(state, f)

    def _load_state(self):
        """
        Load persisted index state from DEFAULT_INDEX_FILE.
        """
        with open(DEFAULT_INDEX_FILE, 'rb') as f:
            state = pickle.load(f)

        self.documents = [
            Document(id_=d['id'], text=d['text'], metadata=d.get('metadata', {}))
            for d in state['docs']
        ]
        self.k1 = state.get('k1', self.k1)
        self.b = state.get('b', self.b)
        self.doc_term_freqs = state.get('doc_term_freqs', [])
        self.doc_lengths = state.get('doc_lengths', [])
        self.doc_freqs = state.get('doc_freqs', {})
        self.avgdl = state.get('avgdl', 0.0)
        self.total_docs = state.get('total_docs', len(self.documents))
        self.idf = state.get('idf', {})
        self.doc_norm = state.get('doc_norm', [])
        self.inverted_index = state.get('inverted_index', {})
