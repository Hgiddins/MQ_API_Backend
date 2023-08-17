from threading import Lock
import datetime

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
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if queue.current_depth == queue.max_number_of_messages:
            return {
                "object_type": "queue",
                "issue_code": "QUEUE_FULL",
                "queue_name": queue.queue_name,
                "max_threshold": thresholdLimit,
                "message": "The queue is 100% full. Immediate action required!",
                "timestamp": current_time,
                "object_details": str(queue)
            }
        elif queue.threshold >= thresholdLimit:
            return {
                "object_type": "queue",
                "issue_code": "THRESHOLD_EXCEEDED",
                "queue_name": queue.queue_name,
                "max_threshold": thresholdLimit,
                "message": f"The queue has exceeded the {thresholdLimit * 100}% threshold limit. Please take necessary actions to avoid potential issues.",
                "timestamp": current_time,
                "object_details": str(queue)
            }
        else:
            return None


