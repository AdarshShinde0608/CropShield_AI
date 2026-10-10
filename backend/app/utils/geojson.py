from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = {key: value for key, value in document.items() if key != "_id"}
    if "_id" in document:
        serialized["id"] = str(document["_id"])
    return serialized


def region_identifier(document: dict[str, Any]) -> str:
    identifier = document.get("region_id", document.get("_id"))
    return str(identifier) if identifier is not None else ""


def region_query(region_id: str) -> dict[str, Any]:
    try:
        object_id = ObjectId(region_id)
    except (InvalidId, TypeError):
        return {"region_id": region_id}
    return {"$or": [{"region_id": region_id}, {"_id": object_id}]}


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}