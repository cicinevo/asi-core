from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict

router = APIRouter(prefix="/api", tags=["command"])

class CommandIn(BaseModel):
    task: str
    args: Optional[Dict] = None
    priority: Optional[int] = 5

@router.post("/command")
async def receive_command(cmd: CommandIn):
    # TODO: enqueue to worker / DB; for now just echo back
    return {
        "status": "accepted",
        "task": cmd.task,
        "args": cmd.args or {},
        "priority": cmd.priority
    }
