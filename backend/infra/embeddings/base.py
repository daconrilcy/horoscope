from abc import ABC, abstractmethod


class Embeddings(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
