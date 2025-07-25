import queue
from flask import Blueprint, Response, stream_with_context, current_app, json

class Announcer:
    def __init__(self):
        self.listeners = []

    def listen(self):
        q = queue.Queue(maxsize=5)
        self.listeners.append(q)
        return q

    def announce(self, msg: dict):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]

announcer = Announcer()
sse_bp = Blueprint("sse", __name__)

@sse_bp.route("/")
def stream():
    def event_stream():
        q = announcer.listen()
        while True:
            data = q.get()
            yield f"data: {json.dumps(data)}\n\n"
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
