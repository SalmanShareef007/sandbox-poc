from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.core.security import get_current_user, require_admin
from app.schemas.configuration import BusinessUnitUpdate, SubscriptionUpdate
from app.services import catalog_service
from app.services import subscription_service

router = APIRouter(tags=["Configuration"])


@router.get("/configuration")
def configuration(current_user: dict = Depends(get_current_user)):
    return catalog_service.configuration()


@router.get("/admin/subscriptions")
def available_subscriptions(admin: dict = Depends(require_admin)):
    try:
        return subscription_service.available_subscriptions()
    except Exception:
        from app.services.sandbox_service import SandboxError

        raise SandboxError("Unable to list subscriptions for the configured Azure identity. Check its subscription read permissions.", 502) from None


@router.put("/admin/subscription", status_code=202)
def select_subscription(payload: SubscriptionUpdate, admin: dict = Depends(require_admin)):
    return subscription_service.request_change(str(payload.subscription_id), admin)


@router.get("/admin/business-units")
def business_units(admin: dict = Depends(require_admin)):
    return catalog_service.list_units(include_inactive=True)


@router.post("/admin/business-units", status_code=201)
def create_business_unit(payload: BusinessUnitUpdate, admin: dict = Depends(require_admin)):
    return catalog_service.save_unit(payload, admin)


@router.put("/admin/business-units/{unit_id}")
def update_business_unit(unit_id: str, payload: BusinessUnitUpdate, admin: dict = Depends(require_admin)):
    return catalog_service.save_unit(payload, admin, unit_id)


@router.post("/admin/business-units/import")
def import_business_units(payload: Annotated[list[BusinessUnitUpdate], Body(min_length=1, max_length=1000)], admin: dict = Depends(require_admin)):
    return catalog_service.import_units(payload, admin)