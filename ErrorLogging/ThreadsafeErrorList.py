import threading

class ThreadSafeErrorList:
    def __init__(self):
        self.errors = []
        self.lock = threading.Lock()

    def add_error(self, error):
        with self.lock:
            self.errors.append(error)

    def get_errors(self):
        with self.lock:
            return self.errors.copy()

    def clear_errors(self):
        with self.lock:
            self.errors.clear()
