"""
Vera Bot — FastAPI server for the magicpin AI Challenge.
Endpoints: /v1/healthz, /v1/metadata, /v1/context, /v1/tick, /v1/reply
"""
from __future__ import annotations
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from .config import TEAM_NAME, TEAM_MEMBERS, MODEL_DISPLAY, APPROACH, VERSION, PORT, HOST
from .models import (ContextRequest, TickRequest, ReplyRequest, HealthResponse,
                      MetadataResponse, ContextsLoaded, TickResponse, TickAction)
from .context_store import ContextStore
from .suppression import SuppressionRegistry
from .composer import Composer
from .conversation import ConversationManager
from .loader import preload_dataset

store = ContextStore()
suppression = SuppressionRegistry()
composer = Composer(store, suppression)
conversation_mgr = ConversationManager(composer, suppression)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    preload_dataset(store)
    print(f"[SERVER] Vera Bot v{VERSION} ready. Contexts: {store.counts()}")
    yield

app = FastAPI(title="Vera Bot", version=VERSION, lifespan=lifespan)


@app.get("/v1/healthz")
async def healthz():
    c = store.counts()
    return HealthResponse(status="ok", uptime_seconds=int(time.time() - _start_time),
                          contexts_loaded=ContextsLoaded(**c))


@app.get("/v1/metadata")
async def metadata():
    return MetadataResponse(team_name=TEAM_NAME, team_members=TEAM_MEMBERS,
                            model=MODEL_DISPLAY, approach=APPROACH, version=VERSION)


@app.post("/v1/context")
async def push_context(req: ContextRequest, response: Response):
    accepted, ack_id, stored_at, cur_ver = store.upsert(req.scope, req.context_id, req.version, req.payload)
    if accepted:
        return {"accepted": True, "ack_id": ack_id, "stored_at": stored_at}
    response.status_code = 409
    return {"accepted": False, "reason": "stale_version", "current_version": cur_ver or req.version}


@app.post("/v1/tick")
async def tick(req: TickRequest):
    triggers = []
    for tid in req.available_triggers:
        tdata = store.get("trigger", tid)
        if tdata:
            triggers.append((tdata.get("urgency", 1), tid, tdata))
    triggers.sort(key=lambda x: -x[0])

    actions = []
    for urgency, tid, tdata in triggers:
        if len(actions) >= 20:
            break
        result = composer.compose_for_trigger(tid, tdata, req.now)
        if not result:
            continue
        conv_id = result.get("conversation_id", "")
        conversation_mgr.get_or_create(conv_id, result.get("merchant_id", ""), result.get("customer_id"))
        conversation_mgr.record_outbound(conv_id, result["body"], tdata.get("kind", ""), tid)
        actions.append(result)

    return TickResponse(actions=[TickAction(**a) for a in actions])


@app.post("/v1/reply")
async def reply(req: ReplyRequest):
    return conversation_mgr.handle_reply(
        req.conversation_id, req.merchant_id or "", req.customer_id,
        req.from_role, req.message, req.turn_number)


def main():
    import uvicorn
    uvicorn.run("bot.server:app", host=HOST, port=PORT, reload=False, log_level="info")

if __name__ == "__main__":
    main()
