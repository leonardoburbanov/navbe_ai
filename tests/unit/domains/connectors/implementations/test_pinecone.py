"""Tests for Pinecone data-plane connector."""

from pytest_httpserver import HTTPServer

from navbe.domains.connectors.implementations.pinecone import PineconeConnector


async def test_create_upsert(httpserver: HTTPServer) -> None:
    """create POSTs /vectors/upsert."""
    httpserver.expect_request("/vectors/upsert", method="POST").respond_with_json(
        {"upsertedCount": 1}
    )
    connector = PineconeConnector(
        {"api_key": "key", "host": httpserver.url_for("/").rstrip("/")}
    )
    result = await connector.execute(
        "create",
        {"vectors": [{"id": "1", "values": [0.1, 0.2]}]},
    )
    assert result == {"upsertedCount": 1}


async def test_read_query(httpserver: HTTPServer) -> None:
    """read with vector POSTs /query."""
    httpserver.expect_request("/query", method="POST").respond_with_json({"matches": []})
    connector = PineconeConnector(
        {"api_key": "key", "host": httpserver.url_for("/").rstrip("/")}
    )
    result = await connector.execute("read", {"vector": [0.1], "top_k": 3})
    assert result == {"matches": []}
