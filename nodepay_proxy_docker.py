import asyncio
import signal
import requests
import json
import time
import uuid
import ssl
import websockets
from loguru import logger
import os
from websockets_proxy import Proxy, proxy_connect
from dotenv import load_dotenv 
import ast

load_dotenv()

WEBSOCKET_URL = "wss://nw.nodepay.ai:4576/websocket"
SERVER_HOSTNAME = "nw.nodepay.ai"
RETRY_INTERVAL = 60000  # in milliseconds
PING_INTERVAL = 10000  # in milliseconds

CONNECTION_STATES = {
    "CONNECTING": 0,
    "OPEN": 1,
    "CLOSING": 2,
    "CLOSED": 3,
}

NP_TOKEN = os.getenv("NP_TOKEN")
proxy_list_str = os.getenv("PROXY_LIST")

# Convert the string representation of the list back to a Python list
PROXY_LIST = ast.literal_eval(proxy_list_str)

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
            "uid": USER_ID,
        }
    }

async def connect_socket_proxy(http_proxy, token, reconnect_interval=RETRY_INTERVAL, ping_interval=PING_INTERVAL):
    browser_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, http_proxy))
    logger.info(f"Browser ID: {browser_id}")

    retries = 0

    while True:
        try:
            proxy = Proxy.from_url(http_proxy)
            custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            proxy = Proxy.from_url(http_proxy)
            async with proxy_connect(WEBSOCKET_URL, proxy=proxy, ssl=ssl_context, server_hostname=SERVER_HOSTNAME,
                                     extra_headers=custom_headers) as websocket:
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
                                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "extension_version",
                                "token": token,
                                "origin_action": "AUTH",
                            }
                            await send_ping(data["id"], auth_info)
                        else:
                            logger.error("Failed to authenticate")

        except asyncio.CancelledError:
            logger.info("Task was cancelled")
            break
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"Connection closed with error: {e.code} - {e.reason}")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("Connection closed normally")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            retries += 1
            logger.info(f"Retrying in {reconnect_interval / 1000} seconds...")
            await asyncio.sleep(reconnect_interval / 1000)


async def shutdown(loop, signal=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")

    logger.info("Napping for 3 seconds before shutdown...")
    await asyncio.sleep(3)
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    [task.cancel() for task in tasks]

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All tasks cancelled, stopping loop")
    loop.stop()

async def main():
    try:
        loop = asyncio.get_running_loop()
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(loop, signal=s)))

        tasks = []
        for proxy in PROXY_LIST:
            task = asyncio.create_task(connect_socket_proxy(proxy, NP_TOKEN))
            tasks.append(task)

        await asyncio.gather(*tasks)

    except FileNotFoundError:
        logger.error("proxy-list.txt not found. Please make sure the file exists.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")