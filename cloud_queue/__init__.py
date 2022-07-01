from .redis_queue import RedisQueue

if None in [RedisQueue]:
    raise AssertionError("just to satisfy the linter")
