
import asyncio
import requests
import json
import time
import uuid
import websockets
from loguru import logger
import os
from websockets_proxy import Proxy, proxy_connect
from dotenv import load_dotenv 

load_dotenv()

WEBSOCKET_URL = "wss://nw.nodepay.ai:4576/websocket"
RETRY_INTERVAL = 60000  # in milliseconds
PING_INTERVAL = 10000  # in milliseconds
CONNECTION_STATES = {
    "CONNECTING": 0,
    "OPEN": 1,
    "CLOSING": 2,
    "CLOSED": 3,
}

NP_TOKEN = os.getenv("NP_TOKEN")

headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer ' + NP_TOKEN
}
response = requests.request("GET", "https://api.nodepay.ai/api/network/device-networks?page=0&size=10&active=false", headers=headers)
out = json.loads(response.text)
USER_ID = out['data'][0]['user_id']


async def call_api_info(token):
    # Simulate API call to get user info
    # Replace with actual API call logic if needed
    return {
        "code": 0,
        "data": {
            "uid": USER_ID,  # Replace with actual user ID
        }
    }

async def connect_socket(token, reconnect_interval=RETRY_INTERVAL, ping_interval=PING_INTERVAL):
    browser_id = str(uuid.uuid4())
    logger.info(f"Browser ID: {browser_id}")

    retries = 0

    while True:
        try:
            custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            async with websockets.connect(WEBSOCKET_URL,extra_headers=custom_headers) as websocket:
                logger.info("Connected to WebSocket")
                retries = 0

                async def send_ping(guid, options={}):
                    payload = {
                        "id": guid,
                        "action": "PING",
                        **options,
                    }
                    await websocket.send(json.dumps(payload))


                async def send_pong(guid):
                    payload = {
                        "id": guid,
                        "origin_action": "PONG",
                    }
                    await websocket.send(json.dumps(payload))

                async for message in websocket:
                    data = json.loads(message)

                    if data["action"] == "PONG":
                        await send_pong(data["id"])
                        await asyncio.sleep(ping_interval / 1000)  # Wait before sending ping
                        await send_ping(data["id"])

                    elif data["action"] == "AUTH":
                        api_response = await call_api_info(token)
                        if api_response["code"] == 0 and api_response["data"]["uid"]:
                            user_info = api_response["data"]
                            auth_info = {
                                "user_id": user_info["uid"],
                                "browser_id": browser_id,
                                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # Replace with actual user agent
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "extension_version",  # Replace with actual version
                                "token": token,
                                "origin_action": "AUTH",
                            }
                            await send_ping(data["id"], auth_info)
                        else:
                            logger.error("Failed to authenticate")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            retries += 1
            logger.info(f"Retrying in {reconnect_interval / 1000} seconds...")
            await asyncio.sleep(reconnect_interval / 1000)

async def main():
    await connect_socket(NP_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())