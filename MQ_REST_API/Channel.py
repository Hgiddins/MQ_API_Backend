class Channel:
    def __init__(self, channel_name=None, channel_type=None):
        self.channel_name = channel_name
        self.channel_type = channel_type

    def __str__(self):
        return str(self.__dict__)

    def to_dict(self):
        return {
            "channel_name": self.channel_name,
            "channel_type": self.channel_type,
        }

class SenderChannel(Channel):
    def __init__(self, channel_name=None, channel_type=None, transmission_queue_name=None, connection_name=None):
        super().__init__(channel_name, channel_type)
        self.transmission_queue_name = transmission_queue_name
        self.connection_name = connection_name

    def to_dict(self):
        return {
            "channel_name": self.channel_name,
            "channel_type": self.channel_type,
            "transmission_queue_name": self.transmission_queue_name,
            "connection_name": self.connection_name,
        }

class ReceiverChannel(Channel):
    def __init__(self, channel_name=None, channel_type=None):
        super().__init__(channel_name, channel_type)

    # Inherits to_dict from Channel

class ApplicationChannel(Channel):
    def __init__(self, channel_name=None, channel_type=None):
        super().__init__(channel_name, channel_type)

    # Inherits to_dict from Channel
