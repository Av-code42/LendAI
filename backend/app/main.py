from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.dispatcher import AgentStepLimitExceeded, ProhibitedToolError, ToolInputValidationError, ToolTimeoutError
from app.agent.orchestrator import AgentRunNotAllowedError
from app.api import applications, reviews
from app.core.config import settings
from app.core.state_machine import InvalidTransitionError
from app.ml.scoring import ModelNotTrainedError

app = FastAPI(title="LendAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(reviews.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"message": message})


@app.exception_handler(InvalidTransitionError)
def handle_invalid_transition(request: Request, exc: InvalidTransitionError):
    return _error(409, str(exc))


@app.exception_handler(ProhibitedToolError)
def handle_prohibited_tool(request: Request, exc: ProhibitedToolError):
    return _error(403, str(exc))


@app.exception_handler(ToolInputValidationError)
def handle_tool_input_validation(request: Request, exc: ToolInputValidationError):
    return _error(422, str(exc))


@app.exception_handler(AgentStepLimitExceeded)
def handle_step_limit(request: Request, exc: AgentStepLimitExceeded):
    return _error(409, str(exc))


@app.exception_handler(ToolTimeoutError)
def handle_tool_timeout(request: Request, exc: ToolTimeoutError):
    return _error(504, str(exc))


@app.exception_handler(AgentRunNotAllowedError)
def handle_agent_run_not_allowed(request: Request, exc: AgentRunNotAllowedError):
    return _error(409, str(exc))


@app.exception_handler(ModelNotTrainedError)
def handle_model_not_trained(request: Request, exc: ModelNotTrainedError):
    return _error(503, str(exc))
