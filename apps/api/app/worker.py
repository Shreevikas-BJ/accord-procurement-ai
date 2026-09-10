from redis import Redis
from rq import Worker
from .config import REDIS_URL
from .logging_config import configure_logging

if __name__ == "__main__":
    configure_logging()
    Worker(["documents"], connection=Redis.from_url(REDIS_URL)).work()
