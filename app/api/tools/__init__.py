from fastapi import APIRouter

from app.api.tools import (
    discovery,
    faktory,
    dao,
    agent_account,
    wallet,
    evaluation,
    social,
)

# Create the main router
router = APIRouter(prefix="/tools", tags=["tools"])

# Include all sub-routers with appropriate prefixes
router.include_router(discovery.router, prefix="", tags=["tool-discovery"])
router.include_router(faktory.router, prefix="/faktory", tags=["faktory"])
router.include_router(dao.router, prefix="/dao", tags=["dao"])
router.include_router(
    agent_account.router, prefix="/agent_account", tags=["agent-account"]
)
router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
router.include_router(social.router, prefix="/social", tags=["social"])
