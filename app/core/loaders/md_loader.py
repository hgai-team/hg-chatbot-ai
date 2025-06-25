import io
from pathlib import Path
from typing import Union, Optional, Dict, List

from datetime import datetime

from llama_index.readers.file import FlatReader
from llama_index.core.node_parser import (
    HierarchicalNodeParser,
    get_leaf_nodes,
)
from llama_index.core.readers.base import BaseReader
from core.base import Document


class MarkdownReader(BaseReader):
    """
    Reader to load Markdown files, split into hierarchical nodes using HierarchicalNodeParser,
    and return a list of Document(text, metadata) objects.
    """

    def _serialize_rels(
        self,
        rels
    ):
        out = {}
        for rel, val in rels.items():
            key = rel.name.lower()
            if isinstance(val, list):
                out[key] = [v.to_dict() for v in val]
            else:
                out[key] = val.to_dict()
        return out

    def __init__(
        self,
        chunk_sizes: Optional[List[int]] = None,
        chunk_overlap: int = 64,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
    ):
        default_chunk_sizes = [2048, 768]

        self.parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=chunk_sizes or default_chunk_sizes,
            chunk_overlap=chunk_overlap,
            include_metadata=include_metadata,
            include_prev_next_rel=include_prev_next_rel,
        )

    def load_data(
        self,
        file: Union[str, Path, io.BytesIO],
        extra_info: Optional[Dict] = None,
    ) -> List[Document]:
        if isinstance(file, (str)):
            file = Path(file)
        if not isinstance(file, (Path)):
            raise TypeError("Input 'file' must be a str or Path")

        md_docs = FlatReader().load_data(file)
        all_nodes = self.parser.get_nodes_from_documents(md_docs)
        leaf_nodes = get_leaf_nodes(all_nodes)

        all_docs, leaf_docs = [], []
        for node in all_nodes:
            meta = {
                "relationships": self._serialize_rels(node.relationships),
                "start": node.start_char_idx,
                "end":   node.end_char_idx,
                "uploaded_at": datetime.now(),
                **(extra_info or {})
            }
            all_docs.append(
                Document(
                    id_=node.id_,
                    text=node.get_content(),
                    metadata=meta
                )
            )
        for node in leaf_nodes:
            meta = {
                "relationships": self._serialize_rels(node.relationships),
                "start": node.start_char_idx,
                "end":   node.end_char_idx,
                "uploaded_at": datetime.now(),
                **(extra_info or {})
            }
            leaf_docs.append(
                Document(
                    id_=node.id_,
                    text=node.get_content(),
                    metadata=meta
                )
            )
        return all_docs, leaf_docs
