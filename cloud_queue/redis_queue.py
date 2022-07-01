import functools
import os
import pickle
import queue
import random
import string
import time

import redis

DEFAULT_CONFIG = {
    "db": 10,
    "host": "localhost",
    "port": 6379,
}


def get_config():
    needle = "REDIS_"
    starting_env_config = {k[len(needle) :].lower(): v for k, v in dict(os.environ).items() if k.startswith(needle)}  # noqa
    port = starting_env_config.get("port")
    if port:
        starting_env_config["port"] = int(port)
    merged_config = {}
    merged_config.update(DEFAULT_CONFIG)
    merged_config.update(starting_env_config)
    return merged_config


@functools.lru_cache(maxsize=None)
def get_words():
    words = set()
    good_letters = set(string.ascii_lowercase)
    with open("/usr/share/dict/words") as wordsfile:
        for iword in wordsfile:
            iword = iword.strip()
            if iword != iword.lower():
                continue
            if iword.rstrip("s") in words:
                continue
            if set(iword) - good_letters:
                continue
            words.add(iword)
    return sorted(words)


def get_random_name():
    return "-".join(random.choices(get_words(), k=3))


class BaseQueue(queue.Queue):
    def __init__(self, maxsize=None, queue_name=None, **kwargs):
        pass

    def empty(self):
        raise NotImplementedError()

    def full(self):
        raise NotImplementedError()

    def get(self, block=True, timeout=None):
        raise NotImplementedError()

    def get_nowait(self):
        return self.get(block=False)

    def info(self):
        raise NotImplementedError()

    def join(self):
        raise NotImplementedError()

    def put(self, item, block=True, timeout=None):
        raise NotImplementedError()

    def put_nowait(self, item):
        raise NotImplementedError()

    def qsize(self):
        raise NotImplementedError()

    def __len__(self):
        return self.qsize()

    def task_done(self):
        raise NotImplementedError()

    def clear(self):
        raise NotImplementedError()


class RedisQueue(BaseQueue):
    def __init__(self, maxsize=None, queue_name=None, **kwargs):
        # TODO: use a pool of redis clients
        use_config = {}
        use_config.update(get_config())
        use_config.update(kwargs)
        self.client = redis.Redis(**use_config)
        self.name = queue_name or get_random_name()
        # print(f"Using {self.name}")

    def empty(self):
        return 0 == self.qsize()

    def full(self):
        return False

    def get(self, block=True, timeout=None):
        # timeout of None means infinite timeout
        if block:
            if timeout:
                timeout = max(0.001, timeout - 0.01)
            maybe_tuple = self.client.blpop(self.name, timeout=timeout)
        else:
            maybe_tuple = self.client.lpop(self.name)
        if maybe_tuple is None:
            raise queue.Empty()
        queue_name, item = maybe_tuple
        return pickle.loads(item)

    def info(self):
        return dict(sorted(self.client.info().items()))

    def join(self):
        raise NotImplementedError()

    def put(self, item, block=True, timeout=None):
        return self.client.lpush(self.name, pickle.dumps(item))

    def put_nowait(self, item):
        raise NotImplementedError()

    def qsize(self):
        return self.client.llen(self.name)

    def task_done(self):
        raise NotImplementedError()

    def clear(self):
        return self.client.delete(self.name)


class RedisPriorityQueue(BaseQueue):
    def __init__(self, maxsize=None, queue_name=None, **kwargs):
        # TODO: use a pool of redis clients
        use_config = {}
        use_config.update(get_config())
        use_config.update(kwargs)
        self.client = redis.Redis(**use_config)
        self.name = queue_name or get_random_name()
        # print(f"Using {self.name}")

    def get_default_priority(self):
        return time.time()

    def empty(self):
        return 0 == self.qsize()

    def put(self, item, block=True, timeout=None, priority=None):
        if priority is None:
            priority = self.get_default_priority()
        return self.client.zadd(self.name, {pickle.dumps(item): priority})

    def full(self):
        return False

    def get(self, block=True, timeout=None):
        try:
            self.client.zmpop(1, [self.name + "test"], min=True)
        except redis.exceptions.ResponseError:
            self.get = self.get_zrange
        else:
            self.get = self.get_bzm
        return self.get(block=block, timeout=timeout)

    def get_zrange(self, block=True, timeout=None):
        deadline = None
        if timeout is not None:
            deadline = time.time() + timeout
        while True:
            maybe_encoded_items = self.client.zrange(self.name, 0, 0)
            try:
                encoded_item = maybe_encoded_items[0]
            except IndexError:
                if not block or deadline < time.time():
                    raise queue.Empty()
            else:
                if 0 != self.client.zrem(self.name, encoded_item):
                    return pickle.loads(encoded_item)

    def get_bzm(self, block=True, timeout=None):
        # can use ZREMRANGEBYRANK if bzmpop is unavailable
        # timeout of None means infinite timeout
        if block:
            if timeout is None:
                timeout = 0
            elif 0 == timeout:
                raise AssertionError("block=True with timeout=0 makes no sense")
            else:
                timeout = max(0.002, timeout - 0.01)
            maybe_tuple = self.client.bzmpop(timeout, 1, [self.name], min=True)
        else:
            maybe_tuple = self.client.zmpop(1, [self.name], min=True)
        if maybe_tuple is None:
            raise queue.Empty()
        queue_name, item_score_pairs = maybe_tuple
        if len(item_score_pairs) != 1:
            raise AssertionError("???")
        encoded_item, score = item_score_pairs[0]
        return pickle.loads(encoded_item)

    def info(self):
        return dict(sorted(self.client.info().items()))

    def qsize(self):
        return self.client.zcard(self.name)

    def clear(self):
        return self.client.delete(self.name)
