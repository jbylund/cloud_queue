"""Cloud Queue Tests"""
import logging
import os
import queue
import random
import time
import unittest

from cloud_queue import redis_queue

logging.basicConfig(level=logging.INFO)


class TestRedisQueue(unittest.TestCase):
    """Test for cloud queue"""

    def setUp(self):
        os.environ["REDIS_HOST"] = "192.168.1.125"
        os.environ["REDIS_PORT"] = "6380"
        self.rq = redis_queue.RedisQueue()

    def test_we_got_the_right_one(self):
        if "packages" in redis_queue.__file__:
            raise AssertionError("Path is maybe messed up?")

    def test_construction(self):
        rq = redis_queue.RedisQueue()
        if rq is None:
            raise AssertionError()

    def test_empty(self):
        # check that it _is_ empty
        if not self.rq.empty():
            raise AssertionError("Should be empty before taking any action")
        # then put a thing
        self.rq.put(None)
        # check that it is _not_ empty
        if self.rq.empty():
            raise AssertionError("Should not be empty after putting a thing")

    def test_full(self):
        if self.rq.full():
            raise AssertionError()

    def test_get_1(self):
        # get with an empty queue and a timeout of 0 raises immediately
        delta = 0.11
        before = time.time()
        try:
            item = self.rq.get(block=True, timeout=0.001)
        except queue.Empty:
            duration = time.time() - before
        else:
            raise AssertionError(f"Should not have gotten an item, but got {item}")
        if delta < duration:
            raise AssertionError(f"Should have raised queue.Empty immediately, took {duration}")

    def test_get_2(self):
        # get with an empty queue and timeout raises after timeout
        delta = 0.21  # this is awful
        wait_time = 0.4
        before = time.time()
        try:
            item = self.rq.get(block=True, timeout=wait_time)
        except queue.Empty:
            duration = time.time() - before
        else:
            raise AssertionError(f"Should not have gotten an item, but got {item}")
        if duration < wait_time or wait_time + delta < duration:
            raise AssertionError(f"Should have waited ~{wait_time} but took {duration} ({duration - wait_time} too long)")

    def test_get_3(self):
        # get with a non empty queue works
        to_send = redis_queue.get_random_name()
        self.rq.put(to_send)
        got_back = self.rq.get()
        if to_send != got_back:
            raise AssertionError(f"Send {to_send}, but got back {got_back}")

    def test_get_nowait(self):
        delta = 0.02
        before = time.time()
        try:
            item = self.rq.get_nowait()
        except queue.Empty:
            duration = time.time() - before
        else:
            raise AssertionError(f"Should not have gotten an item, but got {item}")
        if delta < duration:
            raise AssertionError(f"Should have raised queue.Empty immediately, took {duration}")

    def test_info(self):
        self.rq.info()  # just check that it _can_ work

    def test_put(self):
        # testing putting also tests getting, because we need to round trip a thing
        to_send = redis_queue.get_random_name()
        self.rq.put(to_send)
        got_back = self.rq.get()
        if to_send != got_back:
            raise AssertionError(f"Send {to_send}, but got back {got_back}")

    def test_put_nowait(self):
        self.test_put()

    def test_qsize(self):
        def by_len():
            return len(self.rq)

        def by_qsize():
            return self.rq.qsize()

        def do_test(method):
            sizes = []
            sizes.append(self.rq.qsize())
            oloops = 4
            iloops = 5
            for _ in range(oloops):
                for _ in range(iloops):
                    self.rq.put(redis_queue.get_random_name())
                sizes.append(method())
            expected = list(range(0, oloops * iloops + 1, iloops))
            if sizes != expected:
                raise AssertionError(sizes)

        do_test(by_len)
        self.rq.clear()
        do_test(by_qsize)

    def test_clear(self):
        # put 10 things
        for _ in range(10):
            self.rq.put(None)

        self.rq.clear()  # clear
        if not self.rq.empty():
            raise AssertionError("Should be empty")

    def test_join(self):
        return  # not done yet

    def test_task_done(self):
        return  # not done yet


class TestRedisPriorityQueue(TestRedisQueue):
    """Test for cloud queue"""

    def setUp(self):
        os.environ["REDIS_HOST"] = "192.168.1.125"
        os.environ["REDIS_PORT"] = "6379"
        self.rq = redis_queue.RedisPriorityQueue()

    def test_construction(self):
        rq = redis_queue.RedisPriorityQueue()
        if rq is None:
            raise AssertionError()

    def test_orderedness(self):
        to_send = list(range(20))
        expected = list(range(20))
        random.shuffle(to_send)
        for item in to_send:
            self.rq.put(item, priority=item)
        got_back = []
        while True:
            try:
                got_back.append(self.rq.get(block=False))
            except queue.Empty:
                break
        if got_back != expected:
            raise AssertionError("very bad")
