import kivy
kivy.require('1.8.0')
from kivy.uix.spinner import Spinner

class ChannelNameSpinner(Spinner):
    channelType = None
    filterList = None
    def __init__(self, **kwargs):
        super(ChannelNameSpinner, self).__init__(**kwargs)
        self.register_event_type('on_channels_updated')
        self.values = []
     
    def on_channels_updated(self, system_channels):
        self.values = system_channels.channel_names
