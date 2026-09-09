from redis import Redis
from rq import Worker
from .config import REDIS_URL

if __name__ == "__main__":
    Worker(["documents"], connection=Redis.from_url(REDIS_URL)).work()
