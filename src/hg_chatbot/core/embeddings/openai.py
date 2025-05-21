from typing import List, Optional, Union

from llama_index.embeddings.openai import OpenAIEmbedding as LlamaOpenAIEmbedding

from core.base import Document, DocumentWithEmbedding

class OpenAIEmbedding:
    """Service for generating text embeddings using LlamaIndex's integration with OpenAI embedding models"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        batch_size: int = 64,
        dimensions: Optional[int] = None,
    ):
        """
        Initialize the OpenAI embedding service via LlamaIndex.

        Args:
            model_name: Name of the OpenAI embedding model to use
            api_key: OpenAI API key for authentication
            batch_size: Maximum number of texts to process in each API call
            dimensions: Optional dimension size for the embeddings (model-dependent)

        Raises:
            ValueError: If either api_key or model_name is not provided
        """

        if api_key is None or model_name is None:
            raise ValueError("Both api_key and model_name must be provided.")

        self.model_name = model_name
        self.batch_size = batch_size
        self.dimensions = dimensions

        # Initialize LlamaIndex embedding model
        embed_kwargs = {"model": model_name}
        if dimensions:
            embed_kwargs["embed_batch_size"] = batch_size
            embed_kwargs["dimensions"] = dimensions

        self.embedding_model = LlamaOpenAIEmbedding(
            api_key=api_key,
            **embed_kwargs
        )

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a single batch of texts.

        Args:
            texts: List of text strings to convert to embeddings

        Returns:
            List of embedding vectors (each vector is a list of floats)
        """
        # LlamaIndex handles the API call and batching internally
        embeddings = self.embedding_model.get_text_embedding_batch(texts)
        return embeddings

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts, processing in batches to avoid API limits.

        Args:
            texts: List of text strings to convert to embeddings

        Returns:
            List of embedding vectors for all input texts
        """
        embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_embeddings = self._embed_batch(batch_texts)
            embeddings.extend(batch_embeddings)

        return embeddings

    def get_embeddings(
        self, docs: Union[Document, List[Document]]
    ) -> List[DocumentWithEmbedding]:
        """
        Generate embeddings for document(s) and wrap them in DocumentWithEmbedding objects.

        This method handles both single documents and lists of documents, extracting
        the text content, generating embeddings, and returning enhanced document objects.

        Args:
            docs: Single Document object or list of Document objects to embed

        Returns:
            List of DocumentWithEmbedding objects containing the original document data
            plus their corresponding embedding vectors
        """
        if not isinstance(docs, list):
            docs = [docs]

        texts = [doc.text for doc in docs]
        embeddings = self.embed_texts(texts)

        result = []
        for doc, embedding in zip(docs, embeddings):
            # Create a new DocumentWithEmbedding with the embedding and copy metadata
            doc_with_embedding = DocumentWithEmbedding(
                embedding=embedding,
                text=doc.text,
                metadata=doc.metadata,
                id_=doc.doc_id
            )
            result.append(doc_with_embedding)

        return result
