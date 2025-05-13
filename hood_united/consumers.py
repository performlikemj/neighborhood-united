# consumers.py
from channels.generic.websocket import WebsocketConsumer
import json

class ToolCallConsumer(WebsocketConsumer):
    # Class-level dictionary to track connected consumers
    connected_consumers = {}

    async def connect(self):
        await self.accept()
        # Use a unique identifier for each user to track the connection
        user_id = self.scope["user"].id
        ToolCallConsumer.connected_consumers[user_id] = self

    async def disconnect(self, close_code):
        user_id = self.scope["user"].id
        if user_id in ToolCallConsumer.connected_consumers:
            del ToolCallConsumer.connected_consumers[user_id]

    @classmethod
    async def send_update(cls, user_id, update_data):
        consumer = cls.connected_consumers.get(user_id)
        if consumer:
            await consumer.send(text_data=json.dumps(update_data))
