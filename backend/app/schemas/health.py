from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["route53-clone-api"] = "route53-clone-api"


class RootResponse(BaseModel):
    message: str
