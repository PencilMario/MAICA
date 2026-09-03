from copy import deepcopy

from examples.session_to_request import build_responses_request_body
from maica.maica_utils import AiConnectionManager, G, MaicaSession, is_rag_enabled
from maica.maica_utils import connection_utils


def test_completion_request_body_matches_responses_payload() -> None:
    connection = AiConnectionManager(
        api_key="key",
        base_url="https://models.example/v1",
        model="configured-model",
    )
    connection.model_actual = "resolved-model"
    connection.default_params(
        temperature=0.8,
        timeout=30,
        extra_headers={"x-debug": "true"},
        extra_body={
            "presence_penalty": 9.0,
            "repetition_penalty": 1.0,
        },
    )
    completion_input = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]
    original_input = deepcopy(completion_input)

    body = connection.completions_to_request_body(
        input=completion_input,
        stream=True,
        max_tokens=1600,
        seed=None,
        top_p=0.7,
        temperature=0.22,
        frequency_penalty=0.44,
        presence_penalty=0.34,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    assert body == {
        "input": [{"role": "user", "content": "hello"}],
        "stream": True,
        "top_p": 0.7,
        "temperature": 0.22,
        "model": "resolved-model",
        "max_output_tokens": 1600,
        "instructions": "system prompt",
        "presence_penalty": 0.34,
        "repetition_penalty": 1.0,
        "chat_template_kwargs": {"enable_thinking": False},
        "seed": None,
        "frequency_penalty": 0.44,
    }
    assert completion_input == original_input


def test_session_request_body_uses_project_hyperparameter_defaults() -> None:
    session = MaicaSession(session_num=-1)
    session.load(
        [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hello", "target_lang": "zh"},
        ]
    )
    connection = AiConnectionManager("", "", model="debug-model")
    connection.model_actual = "debug-model"
    connection.default_params(extra_body={"repetition_penalty": 1.0})

    body = build_responses_request_body(session, connection)

    assert body["model"] == "debug-model"
    assert body["stream"] is True
    assert body["max_output_tokens"] == 1600
    assert body["temperature"] == 0.22
    assert body["top_p"] == 0.7
    assert body["frequency_penalty"] == 0.44
    assert body["presence_penalty"] == 0.34
    assert body["seed"] is None
    assert body["repetition_penalty"] == 1.0


def test_vector_pool_constructs_lance_store_from_configured_path(monkeypatch, tmp_path) -> None:
    calls = {}
    expected = object()

    async def fake_create(path, dimensions, table_name=None):
        calls.update(path=path, dimensions=dimensions, table_name=table_name)
        return expected

    monkeypatch.setattr(connection_utils.LanceVectorStore, "async_create", fake_create)
    monkeypatch.setattr(G.A, "VECTOR_DB_PATH", str(tmp_path))
    monkeypatch.setattr(G.A, "EMBEDDING_DIMS", "768")

    result = __import__("asyncio").run(connection_utils.ConnUtils.vector_pool())

    assert result is expected
    assert calls == {
        "path": str(tmp_path),
        "dimensions": 768,
        "table_name": None,
    }


def test_rag_readiness_uses_embedding_and_vector_path(monkeypatch) -> None:
    monkeypatch.setattr(G.A, "EMBEDDING_ADDR", "https://embedding.example/v1")
    monkeypatch.setattr(G.A, "VECTOR_DB_PATH", "vector-db")

    assert is_rag_enabled()
