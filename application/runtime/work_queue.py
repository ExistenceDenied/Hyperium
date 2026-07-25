from collections import deque


class WorkQueue:

    def __init__(self):
        self._queue = deque()

    def add(self, work_item):
        self._queue.append(work_item)

    def add_many(self, work_items):
        self._queue.extend(work_items)

    def pop(self):
        if self._queue:
            return self._queue.popleft()
        return None

    def is_empty(self):
        return len(self._queue) == 0

    def __len__(self):
        return len(self._queue)