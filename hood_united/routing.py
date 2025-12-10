# routing.py
from django.urls import re_path
from .consumers import ToolCallConsumer
import messaging.routing

websocket_urlpatterns = [
    re_path('ws/toolcall/', ToolCallConsumer.as_asgi()),
] + messaging.routing.websocket_urlpatterns

