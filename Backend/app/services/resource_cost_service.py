import re
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import ceil
from threading import Lock
from time import monotonic, sleep
from urllib.parse import urlsplit

import httpx

from app.integrations.terraform import azure_credential

_GROUP_ID = re.compile(r"^/subscriptions/[a-z0-9-]+/resourcegroups/[a-z0-9_.()-]+$", re.IGNORECASE)
_MANAGEMENT = "https://management.azure.com"
_CACHE_SECONDS = 300
_CACHE_LIMIT = 256
_MAX_RETRIES = 2
_MAX_INLINE_WAIT_SECONDS = 2
_cache: OrderedDict[str, tuple[float, str, list[dict]]] = OrderedDict()
_cooldowns: OrderedDict[str, float] = OrderedDict()
_inflight: dict[str, Future[list[dict]]] = {}
_lock = Lock()


class ResourceCostThrottled(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Azure rate limited resource cost requests; retry after {retry_after} seconds.")


def _retry_after(response: httpx.Response, attempt: int) -> int:
    value = response.headers.get("Retry-After", "")
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            seconds = (when - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            seconds = 10 * (2 ** attempt)
    if not 0 <= seconds < float("inf"):
        seconds = 10 * (2 ** attempt)
    return max(1, ceil(seconds))


def _request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(_MAX_RETRIES + 1):
        response = client.request(method, url, **kwargs)
        if response.status_code != 429:
            response.raise_for_status()
            return response
        delay = _retry_after(response, attempt)
        if attempt == _MAX_RETRIES or delay > _MAX_INLINE_WAIT_SECONDS:
            raise ResourceCostThrottled(delay)
        sleep(delay)
    raise RuntimeError("Resource cost retry loop exhausted unexpectedly.")


def _validate_link(url: str, resource_id: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() != "management.azure.com" or not parts.path.lower().startswith(resource_id.lower() + "/"):
        raise ValueError("Azure returned an invalid pagination link.")


def list_resource_costs(resource_id: str) -> list[dict]:
    if not _GROUP_ID.fullmatch(resource_id):
        raise ValueError("Sandbox resource group ID is invalid.")

    key = resource_id.casefold()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    with _lock:
        now = monotonic()
        entry = _cache.get(key)
        if entry and entry[0] > now and entry[1] == month:
            _cache.move_to_end(key)
            return deepcopy(entry[2])
        _cache.pop(key, None)
        until = _cooldowns.get(key, 0)
        if until > now:
            raise ResourceCostThrottled(ceil(until - now))
        _cooldowns.pop(key, None)
        future = _inflight.get(key)
        if future is None:
            future = Future()
            _inflight[key] = future
            owner = True
        else:
            owner = False

    if not owner:
        return deepcopy(future.result())

    try:
        result = _fetch_resource_costs(resource_id)
    except BaseException as exc:
        with _lock:
            if isinstance(exc, ResourceCostThrottled):
                _cooldowns[key] = monotonic() + exc.retry_after
                _cooldowns.move_to_end(key)
                while len(_cooldowns) > _CACHE_LIMIT:
                    _cooldowns.popitem(last=False)
            _inflight.pop(key)
            future.set_exception(exc)
        raise
    with _lock:
        _cache[key] = (monotonic() + _CACHE_SECONDS, month, deepcopy(result))
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
        _inflight.pop(key)
        future.set_result(result)
    return deepcopy(result)


def _fetch_resource_costs(resource_id: str) -> list[dict]:
    with azure_credential() as credential, httpx.Client(timeout=30) as client:
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}"}
        resources = []
        url = f"{_MANAGEMENT}{resource_id}/resources?api-version=2021-04-01"
        for _ in range(100):
            _validate_link(url, resource_id)
            response = _request_with_retry(client, "GET", url, headers=headers)
            payload = response.json()
            resources.extend(payload["value"])
            url = payload.get("nextLink")
            if not url:
                break
        else:
            raise ValueError("Azure resource listing exceeded the pagination limit.")

        costs: dict[str, dict] = {}
        url = f"{_MANAGEMENT}{resource_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01"
        query = {"type": "ActualCost", "timeframe": "MonthToDate", "dataset": {
            "granularity": "None", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceId"}],
        }}
        for _ in range(100):
            _validate_link(url, resource_id)
            response = _request_with_retry(client, "POST", url, headers=headers, json=query)
            properties = response.json()["properties"]
            columns = {column["name"].lower(): index for index, column in enumerate(properties["columns"])}
            amount = columns.get("cost", columns.get("pretaxcost"))
            if amount is None or "resourceid" not in columns or "currency" not in columns:
                raise ValueError("Azure cost response is missing required columns.")
            for row in properties.get("rows", []):
                resource = row[columns["resourceid"]]
                if not resource:
                    continue
                key = resource.casefold()
                currency = row[columns["currency"]]
                item = costs.setdefault(key, {"cost": 0.0, "currency": currency})
                if item["currency"] != currency:
                    raise ValueError("Azure returned multiple currencies for a resource.")
                item["cost"] += float(row[amount])
            url = properties.get("nextLink")
            if not url:
                break
        else:
            raise ValueError("Azure cost query exceeded the pagination limit.")

    return [
        {"id": resource["id"], "name": resource["name"], "type": resource["type"],
         "cost": costs[resource["id"].casefold()]["cost"] if resource["id"].casefold() in costs else None,
         "currency": costs[resource["id"].casefold()]["currency"] if resource["id"].casefold() in costs else None}
        for resource in resources
    ]
