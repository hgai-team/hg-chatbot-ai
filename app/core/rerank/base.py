from typing import List, Tuple
from abc import ABC, abstractmethod

class BaseReranker(ABC):


    @abstractmethod
    def rerank(
        self,
        query: str,
        passages: List[str],
        *args,
        **kwargs
    ) -> List[Tuple[str, float]]:
        """
        Given a query and a list of passages, return a list of (passage, score) tuples,
        sorted by score descending.
        """
        ...
