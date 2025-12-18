#!/usr/bin/env python3
"""
WebSocket connection test script for troubleshooting.

Usage:
    python scripts/test_websocket.py <websocket_url> <jwt_token>

Examples:
    # Test local development
    python scripts/test_websocket.py ws://localhost:8000/ws/chat/1/ <your_jwt_token>
    
    # Test production
    python scripts/test_websocket.py wss://sautai-django-westus2.redcliff-686826f3.westus2.azurecontainerapps.io/ws/chat/1/ <your_jwt_token>

Requirements:
    pip install websockets
"""
import asyncio
import sys
import json

try:
    import websockets
except ImportError:
    print("Error: websockets package not installed.")
    print("Install it with: pip install websockets")
    sys.exit(1)


async def test_websocket(url: str, token: str):
    """
    Test WebSocket connection and basic messaging.
    """
    full_url = f"{url}?token={token}"
    print(f"\n[TEST] Connecting to: {url}")
    print(f"[TEST] Token provided: {token[:20]}...{token[-10:]}")
    print("-" * 60)
    
    try:
        # Attempt connection with a timeout
        async with websockets.connect(
            full_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            print("[SUCCESS] WebSocket connection established!")
            print(f"[INFO] Protocol: {ws.subprotocol or 'none'}")
            
            # Send a read receipt to test bidirectional communication
            test_message = json.dumps({"type": "read"})
            print(f"\n[TEST] Sending test message: {test_message}")
            await ws.send(test_message)
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"[SUCCESS] Received response: {response}")
            except asyncio.TimeoutError:
                print("[INFO] No response received (this may be normal for 'read' messages)")
            
            # Keep connection open briefly to test stability
            print("\n[TEST] Keeping connection open for 3 seconds...")
            await asyncio.sleep(3)
            
            print("[SUCCESS] Connection remained stable!")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"[ERROR] Server rejected connection with status code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"[DEBUG] Response headers: {dict(e.headers)}")
    except websockets.exceptions.InvalidHandshake as e:
        print(f"[ERROR] WebSocket handshake failed: {e}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[ERROR] Connection closed unexpectedly: code={e.code}, reason={e.reason}")
    except ConnectionRefusedError:
        print("[ERROR] Connection refused - is the server running?")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nError: Missing required arguments")
        print("Usage: python scripts/test_websocket.py <websocket_url> <jwt_token>")
        sys.exit(1)
    
    url = sys.argv[1]
    token = sys.argv[2]
    
    # Validate URL format
    if not url.startswith(('ws://', 'wss://')):
        print(f"Error: URL must start with ws:// or wss://")
        print(f"Got: {url}")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_websocket(url, token))


if __name__ == "__main__":
    main()
