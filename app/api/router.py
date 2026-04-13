from fastapi import APIRouter

from app.api.endpoints import analysis, auth, footprints, health

router = APIRouter()
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
router.include_router(footprints.router, prefix="/footprints", tags=["footprints"])
