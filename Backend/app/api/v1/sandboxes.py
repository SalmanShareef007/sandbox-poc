
import logging

import httpx
from azure.core.exceptions import AzureError
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.schemas.decommission import DecommissionCreate
from app.schemas.extension import ExtensionCreate
from app.schemas.sandbox_request import SandboxRequestCreate
from app.services import sandbox_service

router = APIRouter(prefix="/sandboxes", tags=["Sandboxes"])
logger = logging.getLogger(__name__)


@router.get("")
def list_my_sandboxes(current_user: dict = Depends(get_current_user)):
    return sandbox_service.list_for_user(current_user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_sandbox_request(
    payload: SandboxRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    return sandbox_service.create_request(payload, current_user)


@router.get("/{reference}")
def get_sandbox(reference: str, current_user: dict = Depends(get_current_user)):
    from app.core.security import is_admin

    request = sandbox_service.get_request_or_404(reference)

    if not (sandbox_service.is_owner(request, current_user) or is_admin(current_user)):
        raise sandbox_service.SandboxError(f"Sandbox {reference} was not found.", 404)

    return sandbox_service.view_by_reference(reference)


@router.get("/{reference}/lifecycle")
def get_lifecycle(reference: str, current_user: dict = Depends(get_current_user)):
    from app.core.security import is_admin

    request = sandbox_service.get_request_or_404(reference)

    if not (sandbox_service.is_owner(request, current_user) or is_admin(current_user)):
        raise sandbox_service.SandboxError(f"Sandbox {reference} was not found.", 404)

    return sandbox_service.lifecycle(reference)


@router.get("/{reference}/resources")
def get_resources(reference: str, current_user: dict = Depends(get_current_user)):
    return _resource_cost_result(reference, current_user, include_inventory=True)


@router.get("/{reference}/resources/costs")
def get_resource_costs(reference: str, current_user: dict = Depends(get_current_user)):
    return _resource_cost_result(reference, current_user, include_inventory=False)


def _sandbox_resource_group(reference: str, current_user: dict) -> str | None:
    from app.core.security import is_admin

    request = sandbox_service.get_request_or_404(reference)
    if not (sandbox_service.is_owner(request, current_user) or is_admin(current_user)):
        raise sandbox_service.SandboxError(f"Sandbox {reference} was not found.", 404)
    return request.get("resource_id")


@router.get("/{reference}/resources/inventory")
def get_resource_inventory(reference: str, current_user: dict = Depends(get_current_user)):
    from app.services.resource_cost_service import ResourceCostThrottled, list_resources

    resource_id = _sandbox_resource_group(reference, current_user)
    if not resource_id:
        raise HTTPException(status_code=409, detail="Resource inventory is not available for this sandbox.")
    try:
        return list_resources(resource_id)
    except ResourceCostThrottled as exc:
        logger.warning("Azure throttled resource inventory for %s; retry in %s seconds", reference, exc.retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Azure is temporarily limiting inventory requests. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (AzureError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Could not retrieve resource inventory for %s", reference)
        raise HTTPException(status_code=503, detail="Azure resource inventory is unavailable. Try again.") from exc


def _resource_cost_result(reference: str, current_user: dict, *, include_inventory: bool):
    from app.core.config import settings
    from app.services.resource_cost_service import ResourceCostThrottled, get_cost_snapshot, list_resource_costs

    resource_id = _sandbox_resource_group(reference, current_user)
    if not settings.COST_MANAGEMENT_ENABLED or not resource_id:
        raise HTTPException(status_code=409, detail="Resource cost data is not available for this sandbox.")
    try:
        if include_inventory:
            return list_resource_costs(resource_id)
        snapshot = get_cost_snapshot(resource_id)
        return {"costs": snapshot.costs, "fetchedAt": snapshot.fetched_at, "stale": snapshot.stale}
    except ResourceCostThrottled as exc:
        logger.warning("Azure throttled resource costs for %s; retry in %s seconds", reference, exc.retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Azure is temporarily limiting cost requests. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (AzureError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Could not retrieve resource costs for %s", reference)
        raise HTTPException(status_code=503, detail="Azure resource costs are unavailable. Check Azure permissions and try again.") from exc


@router.post("/{reference}/extensions", status_code=status.HTTP_201_CREATED)
def request_extension(
    reference: str,
    payload: ExtensionCreate,
    current_user: dict = Depends(get_current_user),
):
    return sandbox_service.request_extension(reference, payload, current_user)


@router.post("/{reference}/decommission", status_code=status.HTTP_201_CREATED)
def request_decommission(
    reference: str,
    payload: DecommissionCreate,
    current_user: dict = Depends(get_current_user),
):
    return sandbox_service.request_decommission(reference, payload.reason, current_user)


@router.post("/{reference}/decommission/agree")
def agree_decommission(reference: str, current_user: dict = Depends(get_current_user)):
    return sandbox_service.accept_decommission(reference, current_user)
