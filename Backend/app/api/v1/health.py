
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Azure Sandbox Platform API",
        "version": "1.0.0"
    }
