from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    def get_chat_model(self):
        pass

    @abstractmethod
    def get_embedding_mode(self):
        pass