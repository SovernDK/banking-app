"""In-memory stand-in for the Ollama chat API, used by unit tests (via TestClient) and e2e tests
(served by uvicorn). It answers with categories looked up by counterparty name."""

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class FakeOllamaConfig(BaseModel):
    categories: dict[str, str | None] = {}
    """The category answered for each counterparty name; names left out are not answered."""
    raw_content: str | None = None
    """Sent as the model's message instead of the categories, e.g. to answer malformed JSON."""
    failure_status: int | None = None


class FakeOllamaState(FakeOllamaConfig):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    requests: list[dict[str, Any]] = []

    def questions(self) -> list[dict[str, Any]]:
        """The JSON question each request asked the model."""
        return [json.loads(request["messages"][-1]["content"]) for request in self.requests]


def create_fake_ollama() -> FastAPI:
    fake = FastAPI()
    fake.state.ollama = FakeOllamaState()

    def state() -> FakeOllamaState:
        return fake.state.ollama

    @fake.post("/api/chat", response_model=None)
    async def chat(request: Request) -> JSONResponse | dict[str, Any]:
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        body = await request.json()
        state().requests.append(body)
        failure_status = state().failure_status
        if failure_status is not None:
            return JSONResponse({"error": "fake failure"}, status_code=failure_status)
        asked = json.loads(body["messages"][-1]["content"])["counterparties"]
        content = state().raw_content
        if content is None:
            content = json.dumps(
                {
                    item["id"]: state().categories[item["name"]]
                    for item in asked
                    if item["name"] in state().categories
                }
            )
        return {
            "model": body["model"],
            "message": {"role": "assistant", "content": content},
            "done": True,
        }

    @fake.post("/_fake/configure")
    def configure(config: FakeOllamaConfig) -> None:
        fake.state.ollama = FakeOllamaState(**config.model_dump())

    return fake
