
from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user
from app.schemas.decommission import DecommissionCreate
from app.schemas.extension import ExtensionCreate
from app.schemas.sandbox_request import SandboxRequestCreate
from app.services import sandbox_service

router = APIRouter(prefix="/sandboxes", tags=["Sandboxes"])


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
