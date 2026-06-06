import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from jantar.agent.executor import run_agent
from jantar.models import AgentRequest, AgentResponse

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=AgentResponse)
async def agent_run(request: AgentRequest):
    """Run the agent on a user request. Returns answer + audit trail."""
    try:
        return await run_agent(request)
    except Exception:
        logger.exception("Agent run failed")
        return JSONResponse(status_code=500, content={"error": "Internal server error. Check server logs."})
