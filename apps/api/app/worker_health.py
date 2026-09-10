"""Container readiness: this host's live RQ process, subscription and heartbeat."""

import os
import socket
from datetime import datetime, timezone
from redis import Redis
from rq import Worker
from .config import REDIS_URL


def healthy():
    connection = Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    connection.ping()
    for worker in Worker.all(connection=connection):
        if worker.hostname != socket.gethostname() or "documents" not in worker.queue_names():
            continue
        if not worker.pid or not worker.last_heartbeat:
            continue
        age = (datetime.now(timezone.utc) - worker.last_heartbeat).total_seconds()
        if age > worker.worker_ttl or worker.get_state() == "stopped":
            continue
        try:
            os.kill(worker.pid, 0)
        except OSError:
            continue
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(0 if healthy() else 1)
