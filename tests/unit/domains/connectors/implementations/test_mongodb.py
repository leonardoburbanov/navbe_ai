"""Tests for MongoDB connector (mocked pymongo)."""

from unittest.mock import MagicMock, patch

import pytest

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.mongodb import MongoDBConnector


async def test_create_inserts_document() -> None:
    """create inserts one document and returns inserted_id."""
    mock_result = MagicMock(inserted_id="abc")
    mock_coll = MagicMock()
    mock_coll.insert_one.return_value = mock_result
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    with patch(
        "navbe.domains.connectors.implementations.mongodb.MongoClient",
        return_value=mock_client,
    ):
        connector = MongoDBConnector({"uri": "mongodb://localhost", "database": "app"})
        result = await connector.execute(
            "create",
            {"collection": "users", "document": {"name": "ada"}},
        )

    assert result == {"inserted_id": "abc"}
    mock_coll.insert_one.assert_called_once_with({"name": "ada"})


async def test_unsupported_action() -> None:
    """Unknown actions raise ExecutionError."""
    connector = MongoDBConnector({"uri": "mongodb://localhost", "database": "app"})
    with pytest.raises(ExecutionError):
        await connector.execute("drop", {})
