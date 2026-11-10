
from fastapi import APIRouter

from app.api.v1 import admin, approvals, auth, configuration, decommission, extensions, health, notifications, sandboxes

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sandboxes.router)
api_router.include_router(approvals.router)
api_router.include_router(extensions.router)
api_router.include_router(decommission.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
api_router.include_router(configuration.router)
