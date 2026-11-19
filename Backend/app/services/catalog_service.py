import re
from uuid import uuid4

from app.core.config import settings
from app.services.audit_service import AuditService
from app.services.storage_service import JSONStorageService as Storage

COLLECTION = "business_units.json"


def unit_code(unit: dict) -> str:
    return unit.get("shortCode") or re.sub(r"[^a-z0-9]", "", unit["name"].lower())[:3] or "sbx"


def list_units(include_inactive: bool = False) -> list[dict]:
    return sorted(
        [{**item, "shortCode": unit_code(item)} for item in Storage.read(COLLECTION) if include_inactive or item.get("active", True)],
        key=lambda item: item["name"].casefold(),
    )


def save_unit(payload, claims: dict, unit_id: str | None = None) -> dict:
    from app.services.sandbox_service import SandboxError

    with Storage.lock():
        units = Storage.read(COLLECTION)
        existing = next((item for item in units if item["id"] == unit_id), None)
        if unit_id and not existing:
            raise SandboxError("Business unit not found.", 404)
        if any(item["name"].casefold() == payload.name.casefold() and item["id"] != unit_id for item in units):
            raise SandboxError("A business unit with this name already exists.", 409)
        if any(unit_code(item).casefold() == payload.short_code.casefold() and item["id"] != unit_id for item in units):
            raise SandboxError("This short code is already assigned to another business unit.", 409)
        unit = {"id": unit_id or str(uuid4()), "name": payload.name, "shortCode": payload.short_code, "costCenters": payload.cost_centers, "active": payload.active}
        if existing:
            units[units.index(existing)] = unit
        else:
            units.append(unit)
        Storage.write(COLLECTION, units)
        AuditService.log_action(claims["oid"], "business_unit_updated" if existing else "business_unit_created", "business_unit", unit["id"])
        return unit


def validate_selection(name: str, cost_center: str) -> dict | None:
    from app.services.sandbox_service import SandboxError

    if not settings.BUSINESS_UNIT_CATALOG_REQUIRED:
        return
    unit = next((item for item in list_units() if item["name"] == name), None)
    if not unit:
        raise SandboxError("Select an active business unit from the configured catalogue.")
    allowed = unit["costCenters"] if settings.COST_CENTER_MODE == "business_unit" else settings.SHARED_COST_CENTERS
    if settings.COST_CENTER_MODE != "free_text" and cost_center not in allowed:
        raise SandboxError("Select a cost centre configured for this business unit.")
    return unit


def import_units(payloads: list, claims: dict) -> list[dict]:
    from app.services.sandbox_service import SandboxError

    names = [payload.name.casefold() for payload in payloads]
    if len(set(names)) != len(names):
        raise SandboxError("Import contains duplicate business-unit names.")
    codes = [payload.short_code for payload in payloads]
    if len(set(codes)) != len(codes):
        raise SandboxError("Import contains duplicate business-unit short codes.")
    with Storage.lock():
        units = Storage.read(COLLECTION)
        by_name = {item["name"].casefold(): item for item in units}
        for payload in payloads:
            existing = by_name.get(payload.name.casefold())
            if existing:
                existing.update(name=payload.name, shortCode=payload.short_code, costCenters=payload.cost_centers, active=payload.active)
            else:
                units.append({"id": str(uuid4()), "name": payload.name, "shortCode": payload.short_code, "costCenters": payload.cost_centers, "active": payload.active})
        final_codes = [unit_code(item).casefold() for item in units]
        if len(set(final_codes)) != len(final_codes):
            raise SandboxError("A short code conflicts with another business unit.", 409)
        Storage.write(COLLECTION, units)
        AuditService.log_action(claims["oid"], "business_units_imported", "business_unit", "catalogue", {"count": len(payloads)})
        return list_units(include_inactive=True)


def configuration() -> dict:
    from app.services.subscription_service import selection

    current = selection()
    return {
        "subscriptionId": current["subscriptionId"], "subscriptionName": current.get("displayName"),
        "subscriptionChangePending": bool(current.get("requestedSubscriptionId")),
        "subscriptionChangeError": current.get("lastError"),
        "maxBudget": settings.MAX_SANDBOX_BUDGET, "budgetCurrency": settings.BUDGET_CURRENCY,
        "environment": settings.TERRAFORM_ENVIRONMENT,
        "budgetAlertThresholds": settings.BUDGET_ALERT_THRESHOLDS,
        "businessUnits": list_units(), "costCenterMode": settings.COST_CENTER_MODE,
        "sharedCostCenters": settings.SHARED_COST_CENTERS,
        "regions": settings.ALLOWED_REGIONS,
        "roles": [role for role in settings.ALLOWED_SANDBOX_ROLES if role in ("Contributor", "Owner") and (role != "Owner" or settings.ALLOW_OWNER_ROLE_REQUESTS)],
        "durations": settings.ALLOWED_DURATIONS_DAYS, "extensionDays": settings.ALLOWED_EXTENSION_DAYS,
        "maxExtensionDays": settings.MAX_EXTENSION_DAYS,
        "expiryGraceDays": settings.EXPIRY_GRACE_DAYS, "expiryReminderDays": settings.EXPIRING_THRESHOLD_DAYS,
        "adminCleanupApprovalRequired": True,
    }