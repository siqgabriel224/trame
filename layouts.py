"""Transporte leve de layouts; o formato persistido/exportado continua completo."""

import base64
import copy
import hashlib
from urllib.parse import urlencode

import access

PREFIX = "/api/layout?"


def reference(order_id, item_id, image, snapshot=""):
    digest = hashlib.sha256(image.encode("utf-8")).hexdigest()
    params = {"order": order_id, "item": item_id, "v": digest}
    if snapshot:
        params["snapshot"] = snapshot
    return PREFIX + urlencode(params)


def _scopes(order):
    yield "", order
    snapshot = order.get("quoteSnapshot")
    historical = snapshot.get("order") if isinstance(snapshot, dict) else None
    if isinstance(historical, dict):
        yield "quote", historical


def compact(state):
    result = copy.deepcopy(state)
    for order in result.get("orders", []):
        for scope, source in _scopes(order):
            for item in source.get("items", []):
                image = item.get("image", "")
                if image:
                    item["image"] = reference(order["id"], item["id"], image, scope)
    return result


def _restore_order(order, originals):
    if not isinstance(order, dict) or not isinstance(order.get("items", []), list):
        return
    original = originals.get(order.get("id"), {})
    originals_by_scope = dict(_scopes(original))
    for scope, candidate in _scopes(order):
        if not isinstance(candidate.get("items", []), list):
            continue
        items = {item["id"]: item for item in originals_by_scope.get(scope, {}).get("items", [])}
        for item in candidate.get("items", []):
            if not isinstance(item, dict):
                continue
            image = item.get("image", "")
            if not isinstance(image, str) or not image.startswith(PREFIX):
                continue
            prior = items.get(item.get("id"), {})
            source = prior.get("image", "")
            if not source or image != reference(order.get("id"), item.get("id"), source, scope):
                raise access.Conflict(
                    "O layout mudou. Atualize o pedido antes de salvar. Seu formulário foi mantido."
                )
            item["image"] = source


def restore_submission(data, old, changes=False):
    """Resolve only references to the same persisted order/item/content.

    Never download URLs supplied by a client, and never trust a stale reference.
    Both the comparison base and the candidate need the original representation.
    """
    originals = {order["id"]: order for order in old.get("orders", [])}
    if changes:
        rows = data.get("changes")
        if isinstance(rows, list):
            for change in rows:
                if isinstance(change, dict) and change.get("key") == "orders":
                    _restore_order(change.get("before"), originals)
                    _restore_order(change.get("after"), originals)
    elif isinstance(data.get("orders"), list):
        for order in data["orders"]:
            _restore_order(order, originals)


def read(state, order_id, item_id, digest, snapshot=""):
    order = next((o for o in state.get("orders", []) if o["id"] == order_id), None)
    if not order:
        return None
    order = dict(_scopes(order)).get(snapshot)
    if not order:
        return None
    item = next((i for i in order.get("items", []) if i["id"] == item_id), None)
    image = item.get("image", "") if item else ""
    if (
        not image
        or len(digest) != 64
        or hashlib.sha256(image.encode("utf-8")).hexdigest() != digest
    ):
        return None
    header, _, encoded = image.partition(",")
    mime = header.removeprefix("data:").removesuffix(";base64")
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        return None
    try:
        return mime, base64.b64decode(encoded, validate=True)
    except ValueError:
        return None
