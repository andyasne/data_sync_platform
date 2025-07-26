import os, redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(redis_url, decode_responses=True)