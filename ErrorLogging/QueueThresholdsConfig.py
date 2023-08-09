from threading import Lock

class QueueThresholdManager:
    def __init__(self):
        self._thresholds = {}
        self._lock = Lock()

    def update(self, new_thresholds):
        with self._lock:
            self._thresholds.update(new_thresholds)

    def get(self, queue_name, default=None):
        with self._lock:
            return self._thresholds.get(queue_name, default)

    def contains(self, queue_name):
        with self._lock:
            return queue_name in self._thresholds

