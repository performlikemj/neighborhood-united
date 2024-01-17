# consumers.py
from channels.generic.websocket import WebsocketConsumer
import json

print("consumers.py")
class ToolCallConsumer(WebsocketConsumer):
    async def connect(self):
        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Handle disconnection
        pass

    async def receive(self, text_data):
        # Process received message
        text_data_json = json.loads(text_data)
        tool_call = text_data_json['tool_call']

        # Import ai_call here to avoid circular import
        from customer_dashboard.views import ai_call

        # Call your ai_call function
        tool_outputs = ai_call(tool_call, self.scope["user"])

        # Send response back to WebSocket
        await self.send(text_data=json.dumps({
            'tool_outputs': tool_outputs
        }))