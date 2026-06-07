from fastembed import TextEmbedding


class FastEmbedTextEmbedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name)

    def embed(self, text: str) -> list[float]:
        vector = next(self.model.embed([text]))
        return [float(value) for value in vector.tolist()]
