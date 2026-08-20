from fastapi import APIRouter

from app.api.v1 import audit, cases, evidence, health

router = APIRouter()
router.include_router(health.router)
router.include_router(cases.router)
router.include_router(evidence.router)
router.include_router(audit.router)
