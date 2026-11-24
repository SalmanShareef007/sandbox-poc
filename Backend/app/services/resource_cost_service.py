import logging
import re
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import dataclass, replace
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
_CACHE_SECONDS = 3600
_CACHE_LIMIT = 256
_MAX_RETRIES = 2
_MAX_INLINE_WAIT_SECONDS = 2
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CostSnapshot:
    costs: dict[str, dict]
    fetched_at: datetime
    stale: bool = False


_cache: OrderedDict[tuple[str, str], tuple[float, CostSnapshot]] = OrderedDict()
_cooldowns: OrderedDict[str, float] = OrderedDict()
_inflight: dict[tuple[str, str], Future[CostSnapshot]] = {}
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


def _validate_group(resource_id: str) -> None:
    if not _GROUP_ID.fullmatch(resource_id):
        raise ValueError("Sandbox resource group ID is invalid.")


def _billing_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_cost_snapshot(resource_id: str) -> CostSnapshot:
    _validate_group(resource_id)
    group = resource_id.casefold()
    key = (group, _billing_month())
    with _lock:
        now = monotonic()
        entry = _cache.get(key)
        if entry:
            _cache.move_to_end(key)
            if entry[0] > now:
                return deepcopy(entry[1])
        until = _cooldowns.get(group, 0)
        if until > now:
            if entry:
                return deepcopy(replace(entry[1], stale=True))
            raise ResourceCostThrottled(ceil(until - now))
        _cooldowns.pop(group, None)
        future = _inflight.get(key)
        owner = future is None
        if future is None:
            _inflight[key] = future = Future()

    if not owner:
        return deepcopy(future.result())

    try:
        snapshot = CostSnapshot(_fetch_resource_costs(resource_id), datetime.now(timezone.utc))
    except BaseException as exc:
        with _lock:
            _inflight.pop(key)
            if isinstance(exc, ResourceCostThrottled):
                _cooldowns[group] = monotonic() + exc.retry_after
                _cooldowns.move_to_end(group)
                while len(_cooldowns) > _CACHE_LIMIT:
                    _cooldowns.popitem(last=False)
                if entry:
                    logger.warning("Azure throttled cost refresh; serving the cached snapshot for %s", resource_id)
                    stale = replace(entry[1], stale=True)
                    future.set_result(stale)
                    return deepcopy(stale)
            future.set_exception(exc)
        raise
    with _lock:
        _cache[key] = (monotonic() + _CACHE_SECONDS, snapshot)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
        _inflight.pop(key)
        future.set_result(snapshot)
    return deepcopy(snapshot)


def list_resources(resource_id: str) -> list[dict]:
    _validate_group(resource_id)
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
    return [
        {"id": resource["id"], "name": resource["name"], "type": resource["type"],
         "region": resource.get("location"), "sku": (resource.get("sku") or {}).get("name")}
        for resource in resources
    ]


def _fetch_resource_costs(resource_id: str) -> dict[str, dict]:
    with azure_credential() as credential, httpx.Client(timeout=30) as client:
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}"}
        costs: dict[str, dict] = {}
        url = f"{_MANAGEMENT}{resource_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01"
        query = {"type": "ActualCost", "timeframe": "MonthToDate", "dataset": {
            "granularity": "None", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceId"}],
        }}
        for _ in range(100):
            _validate_link(url, resource_id)
            response = _request_with_retry(client, "POST", url, headers=headers, json=query)
            if response.status_code == 204:
                break
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
    return costs


def list_resource_costs(resource_id: str) -> list[dict]:
    costs = get_cost_snapshot(resource_id).costs
    return [
        {"id": resource["id"], "name": resource["name"], "type": resource["type"],
         **costs.get(resource["id"].casefold(), {"cost": None, "currency": None})}
        for resource in list_resources(resource_id)
    ]
