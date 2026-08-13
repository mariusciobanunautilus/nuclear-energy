from types import SimpleNamespace

import pytest

from nuclear_energy.embeddings import create_embedding, create_embeddings, dimensions_for_model


class FakeEmbeddingEndpoint:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        data = [
            SimpleNamespace(index=index, embedding=[float(index), float(index + 1)])
            for index, _text in enumerate(kwargs["input"])
        ]
        return SimpleNamespace(data=list(reversed(data)))


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddingEndpoint()


def test_create_embeddings_batches_and_orders_results():
    client = FakeClient()

    embeddings = create_embeddings(
        ["  first\nchunk  ", "second chunk", "third chunk"],
        batch_size=2,
        client=client,
    )

    assert embeddings == [[0.0, 1.0], [1.0, 2.0], [0.0, 1.0]]
    assert len(client.embeddings.calls) == 2
    assert client.embeddings.calls[0]["input"] == ["first chunk", "second chunk"]
    assert client.embeddings.calls[0]["model"] == "text-embedding-3-small"
    assert client.embeddings.calls[0]["dimensions"] == 1536
    assert client.embeddings.calls[0]["encoding_format"] == "float"


def test_create_embedding_returns_single_vector():
    client = FakeClient()

    assert create_embedding("query", client=client) == [0.0, 1.0]


def test_create_embeddings_rejects_empty_text():
    with pytest.raises(ValueError):
        create_embeddings(["   "], client=FakeClient())


def test_dimensions_for_model_only_sets_dimensions_for_embedding_3_models():
    assert dimensions_for_model("text-embedding-3-small") == 1536
    assert dimensions_for_model("text-embedding-3-large") == 1536
    assert dimensions_for_model("text-embedding-ada-002") is None
