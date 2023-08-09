from threading import Lock

class QueueThresholdManager:
    def __init__(self):
        self._thresholds = {}
        self.defaultThreshold = 0.8
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

    def thresholdWarning(self, queue, thresholdLimit):
        if queue.current_depth == queue.max_number_of_messages:
            return {
                "object_type": "queue",
                "error_code": "QUEUE_FULL",
                "queue_name": queue.queue_name,
                "number_of_messages": queue.current_depth,
                "max_num_messages": queue.max_number_of_messages,
                "current_threshold": queue.threshold,
                "max_threshold": thresholdLimit,
                "message": "The queue is 100% full. Immediate action required!"
            }
        elif queue.threshold >= thresholdLimit:
            return {
                "object_type": "queue",
                "error_code": "THRESHOLD_EXCEEDED",
                "queue_name": queue.queue_name,
                "number_of_messages": queue.current_depth,
                "max_num_messages": queue.max_number_of_messages,
                "current_threshold": queue.threshold,
                "max_threshold": thresholdLimit,
                "message": "The threshold limit of the queue has been exceeded. Please take necessary actions to avoid potential issues."
            }
        else:
            return None


