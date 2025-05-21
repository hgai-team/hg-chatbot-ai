from typing import Any, Literal, Optional

from llama_index.core.schema import Document as BaseDocument

SAMPLE_TEXT = "A sample Document from hg_chatbot"

class Document(BaseDocument):
    """
    Base document class, mostly inherited from Document class from llama-index.

    This class accept one positional argument `content` of an arbitrary type, which will
        store the raw content of the document. If specified, the class will use
        `content` to initialize the base llama_index class.

    Attributes:
        content: raw content of the document, can be anything
        source: id of the source of the Document. Optional.
        channel: the channel to show the document. Optional.:
            - chat: show in chat message
            - info: show in information panel
            - index: show in index panel
            - debug: show in debug panel
    """

    content: Any = None
    source: Optional[str] = None
    channel: Optional[Literal["chat", "info", "index", "debug", "plot"]] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __bool__(self):
        return bool(self.content)

    @classmethod
    def example(cls) -> "Document":
        document = Document(
            text=SAMPLE_TEXT,
            metadata={"filename": "README.md", "category": "codebase"},
        )
        return document

    def __str__(self):
        return str(self.content)

class DocumentWithEmbedding(Document):
    """Subclass of Document which must contains embedding

    Use this if you want to enforce component's IOs to must contain embedding.
    """

    def __init__(self, embedding: list[float], *args, **kwargs):
        kwargs["embedding"] = embedding
        super().__init__(*args, **kwargs)
