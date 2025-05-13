# routing.py
from .consumers import ToolCallConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path('ws/toolcall/', ToolCallConsumer.as_asgi()),
]

