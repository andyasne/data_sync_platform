from flask import Blueprint, Response, stream_with_context
from .redis_client import r           # <-- same client for every process
import json

sse_bp = Blueprint("sse", __name__)

CHANNEL = "sync_events"

def announce(payload: dict):
    print("PUBLISH", payload, flush=True)  
    r.publish(CHANNEL, json.dumps(payload))   # one-liner!

def _event_stream():
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(CHANNEL)
    for msg in pubsub.listen():               # blocks efficiently
        yield f"data: {msg['data']}\n\n"

@sse_bp.route("/stream")
def stream():
    return Response(
        stream_with_context(_event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
