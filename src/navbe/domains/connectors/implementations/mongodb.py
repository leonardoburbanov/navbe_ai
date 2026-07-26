"""MongoDB connector — basic collection CRUD via pymongo."""

from __future__ import annotations

import asyncio
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class MongoDBConfig(ConnectorConfig):
    """MongoDB connection config. Prefer ``uri`` with ``{"$secret": "..."}`` for credentials."""

    uri: str
    database: str | None = None
    timeout_ms: int = 5000


@ConnectorRegistry.register("mongodb")
class MongoDBConnector:
    """CRUD against a MongoDB collection (sync pymongo via ``asyncio.to_thread``)."""

    config_schema = MongoDBConfig
    actions = {
        "create": "Insert one document",
        "read": "Find documents",
        "update": "Update documents matching filter",
        "delete": "Delete documents matching filter",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store MongoDB config."""
        self.config = MongoDBConfig.model_validate(config)

    def _client(self) -> MongoClient:
        return MongoClient(self.config.uri, serverSelectionTimeoutMS=self.config.timeout_ms)

    def _db(self, client: MongoClient, fields: dict[str, Any]) -> Any:
        name = fields.get("database") or self.config.database
        if not name:
            raise ExecutionError(
                "mongodb requires database in config or payload",
                details={"field": "database"},
            )
        return client[name]

    async def test_connection(self) -> bool:
        """Return True when the server responds to ping."""

        def _ping() -> bool:
            try:
                client = self._client()
                try:
                    client.admin.command("ping")
                    return True
                finally:
                    client.close()
            except PyMongoError:
                return False

        return await asyncio.to_thread(_ping)

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a CRUD action on a collection."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for mongodb connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(payload, "collection", "document", "filter", "update")
        collection = fields.get("collection")
        if not collection:
            raise ExecutionError(
                "mongodb actions require collection",
                details={"field": "collection"},
            )

        def _run() -> Any:
            client = self._client()
            try:
                coll = self._db(client, fields)[collection]
                if action == "create":
                    document = fields.get("document")
                    if not isinstance(document, dict):
                        raise ExecutionError(
                            "create requires document object",
                            details={"field": "document"},
                        )
                    result = coll.insert_one(document)
                    return {"inserted_id": str(result.inserted_id)}
                if action == "read":
                    filt = fields.get("filter") or {}
                    limit = int(fields.get("limit") or 100)
                    docs = list(coll.find(filt).limit(limit))
                    for doc in docs:
                        if "_id" in doc:
                            doc["_id"] = str(doc["_id"])
                    return {"documents": docs}
                if action == "update":
                    filt = fields.get("filter")
                    update = fields.get("update")
                    if not isinstance(filt, dict) or not isinstance(update, dict):
                        raise ExecutionError(
                            "update requires filter and update objects",
                            details={"fields": ["filter", "update"]},
                        )
                    # Accept raw update doc; wrap bare fields in $set when no operator.
                    if update and not any(str(k).startswith("$") for k in update):
                        update = {"$set": update}
                    result = coll.update_many(filt, update)
                    return {
                        "matched_count": result.matched_count,
                        "modified_count": result.modified_count,
                    }
                # delete
                filt = fields.get("filter")
                if not isinstance(filt, dict):
                    raise ExecutionError(
                        "delete requires filter object",
                        details={"field": "filter"},
                    )
                result = coll.delete_many(filt)
                return {"deleted_count": result.deleted_count}
            except ExecutionError:
                raise
            except PyMongoError as exc:
                raise ExecutionError(
                    "mongodb action failed",
                    details={"action": action, "collection": collection},
                ) from exc
            finally:
                client.close()

        return await asyncio.to_thread(_run)
