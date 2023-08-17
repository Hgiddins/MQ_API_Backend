from abc import ABC, abstractmethod

class Queue(ABC):
    def __init__(self):
        self.queue_name = None
        self.max_number_of_messages = None
        self.max_message_length = None
        self.inhibit_put = None
        self.inhibit_get = None
        self.description = None
        self.time_created = None
        self.time_altered = None
        self.current_depth = None
        self.holds_messages = None
        self.messages = []
        self.type_name = None

    @abstractmethod
    def get_type_name(self):
        pass

    def to_dict(self):
        return self.__dict__

    def __str__(self):
        return str(self.__dict__)


class RemoteQueue(Queue):
    type_name = "Remote"

    def __init__(self):
        super().__init__()
        self.target_queue_name = None
        self.target_qmgr_name = None
        self.transmission_queue_name = None
        self.current_depth = 0
        self.holds_messages = False

    def get_type_name(self):
        return RemoteQueue.type_name


class TransmissionQueue(Queue):
    type_name = "Transmission"

    def __init__(self):
        super().__init__()
        self.open_input_count = None
        self.open_output_count = None
        self.holds_messages = True

    def get_type_name(self):
        return TransmissionQueue.type_name


class AliasQueue(Queue):
    type_name = "Alias"

    def __init__(self):
        super().__init__()
        self.target_queue_name = None
        self.current_depth = 0
        self.holds_messages = False

    def get_type_name(self):
        return AliasQueue.type_name


class LocalQueue(Queue):
    type_name = "Local"

    def __init__(self):
        super().__init__()
        self.open_input_count = None
        self.open_output_count = None
        self.holds_messages = True

    def get_type_name(self):
        return LocalQueue.type_name
