import asyncio
import json
import os

import aiohttp
import websockets
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBSOCKET_URL = "wss://gateway.discord.gg/?v=9&encoding=json"
DISCORD_API_URL = "https://discord.com/api/v9/users/@me/connections"
SPOTIFY_WEBSOCKET_URL = "wss://dealer.spotify.com/?access_token={}"
SPOTIFY_TOKEN = os.getenv("SPOTIFY_TOKEN")
DISCORD_TOKEN = os.getenv("TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("Missing tokens in .env file.")


class DiscordClient:
    def __init__(self, token):
        self.token = token
        self.websocket = None
        self.heartbeat_interval = None
        self.last_sequence = None
        self.session_id = None
        self.heartbeat_task = None
        self.activities = [{"name": "Custom Status",
                            "type": 4,
                            "state": "It is a blessing to understand your darkest nature...",
                            "emoji": {"id": None, "name": "🐈", "animated": False},
                            "metadata": {}}]

    async def send_heartbeat(self):
        while True:
            if self.heartbeat_interval:
                await asyncio.sleep(self.heartbeat_interval / 1000)
                heartbeat_payload = {"op": 1, "d": self.last_sequence}
                await self.websocket.send(json.dumps(heartbeat_payload))
                print(f"> Sent Heartbeat: {heartbeat_payload}")
            else:
                await asyncio.sleep(1)

    async def identify_or_resume(self):
        if self.session_id:
            payload = {
                "op": 6,
                "d": {"token": self.token, "session_id": self.session_id, "seq": self.last_sequence},
            }
            await self.websocket.send(json.dumps(payload))
            print(f"> Sent Resume: {payload}")
        else:
            payload = {
                "op": 2,
                "d": {
                    "token": self.token,
                    "capabilities": 30719,
                    "properties": {
                        "os": "Android",
                        "browser": "Discord Android",
                        "device": "p3s",
                    },
                    "presence": {"status": "online", "since": 0, "activities": [self.activities], "afk": True},
                },
            }
            await self.websocket.send(json.dumps(payload))
            print(f"> Sent Identify: {payload}")

    async def update_presence(self, is_playing, track_data=None):
        presence_payload = {
            "op": 3,
            "d": {
                "status": "online",  # if is_playing else "idle",
                "since": 0,
                "activities": [track_data, self.activities] if is_playing else [self.activities],
                "afk": True,
            },
        }
        await self.websocket.send(json.dumps(presence_payload))
        print(f"{Fore.YELLOW}> Updated Presence: {presence_payload}{Style.RESET_ALL}")

    async def listen_messages(self):
        try:
            async for message in self.websocket:
                payload = json.loads(message)
                op = payload.get("op")
                event_type = payload.get("t")
                event_data = payload.get("d")

                if op == 0:
                    self.last_sequence = payload.get("s")
                    print(f"{Fore.GREEN}< Dispatch Event: {event_type}{Style.RESET_ALL}")
                    if event_type == "READY":
                        self.session_id = event_data.get("session_id")
                        print(f"Session ID: {self.session_id}")

                elif op == 10:
                    self.heartbeat_interval = payload["d"]["heartbeat_interval"]
                    print(f"{Fore.BLUE}Hello! Heartbeat Interval: {self.heartbeat_interval}ms{Style.RESET_ALL}")
                    if self.heartbeat_task:
                        self.heartbeat_task.cancel()
                    self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
                    await self.identify_or_resume()

                elif op == 11:
                    print(f"{Fore.CYAN}< Heartbeat ACK{Style.RESET_ALL}")

        except websockets.ConnectionClosed as e:
            print(f"{Fore.RED}Discord Connection closed: {e}{Style.RESET_ALL}")
            if self.heartbeat_task:
                self.heartbeat_task.cancel()

    async def connect(self):
        while True:
            try:
                async with websockets.connect(DISCORD_WEBSOCKET_URL, max_size=2 ** 40) as websocket:
                    self.websocket = websocket
                    await self.listen_messages()
            except Exception as e:
                print(f"{Fore.RED}Discord Error: {e}{Style.RESET_ALL}")
                await asyncio.sleep(5)


class SpotifyClient:
    def __init__(self, discord_client):
        self.token = None
        self.websocket = None
        self.heartbeat_task = None
        self.discord_client = discord_client
        self.spotify_token = SPOTIFY_TOKEN

    async def fetch_token(self):
        headers = {"Authorization": f"{DISCORD_TOKEN}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(DISCORD_API_URL, headers=headers) as response:
                if response.status == 200:
                    connections = await response.json()
                    for conn in connections:
                        if conn.get("type") == "spotify":
                            self.token = conn.get("access_token")
                            print(f"{Fore.GREEN}Spotify token fetched.{Style.RESET_ALL}")
                            return self.token
                print(f"{Fore.RED}Failed to fetch Spotify token.{Style.RESET_ALL}")
                return None

    async def fetch_current_episode_metadata(self):
        url = "https://api.spotify.com/v1/me/player/currently-playing?additional_types=episode"
        headers = {
            "Authorization": f"Bearer {self.spotify_token}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("currently_playing_type") == "episode":
                        await self.prepare_payload(data)
                        return data
        return None

    async def prepare_payload(self, state_data=None):

        is_playing = state_data["is_playing"]

        item = state_data.get("item")
        item_type = item.get("type")

        timestamp = state_data["timestamp"]
        progress_ms = state_data["progress_ms"]
        duration_ms = item["duration_ms"]

        if not item:
            print(
                f"{Fore.MAGENTA}No item in payload — possibly an episode or unavailable track.{Style.RESET_ALL}")
            await self.fetch_current_episode_metadata()
            return

        # Determine content-specific fields
        if item_type == "track":
            name = item["name"]
            state = item["artists"][0]["name"]
            large_text = name
            large_image = f"spotify:{item['album']['images'][0]['url'].split('/')[-1]}"
            metadata_type = "track"
        elif item_type == "episode":
            name = item["name"]
            state = item["show"]["publisher"]  # Or item["show"]["name"]
            large_text = item["show"]["name"]
            large_image = f"spotify:{item['images'][0]['url'].split('/')[-1]}"
            metadata_type = "episode"
        else:
            return  # Unsupported content type

        track_data = {
            "type": 2,
            "name": "Spotify",
            "assets": {
                "large_image": large_image,
                "large_text": large_text
            },
            "details": name,
            "state": state,
            "timestamps": {
                "start": timestamp - progress_ms,
                "end": timestamp + duration_ms,
            },
            "party": {
                "id": "spotify:98141664303927296"
            },
            "sync_id": item["id"],
            "flags": 48,
            "metadata": {
                "context_uri": state_data["context"]["uri"],
                "album_id": item["album"]["id"] if item_type == "track" else None,
                "artist_ids": [a["id"] for a in item["album"]["artists"]] if item_type == "track" else [],
                "type": metadata_type,
                "button_urls": []
            }
        } if is_playing else None

        await self.discord_client.update_presence(is_playing, track_data)

    # Send heartbeat messages periodically
    async def send_heartbeat(self):
        while True:
            heartbeat_message = {"type": "ping"}
            await self.websocket.send(json.dumps(heartbeat_message))
            print(f"{Fore.GREEN}> Sent Heartbeat: {heartbeat_message}{Style.RESET_ALL}")
            await asyncio.sleep(30)

    async def authenticate(self, payload):
        # Spotify WebSocket authentication
        async with aiohttp.ClientSession() as session:
            spotify_url = (
                f'https://api.spotify.com/v1/me/notifications/player?connection_id='
                f'{payload["headers"]["Spotify-Connection-Id"]}'
            )
            headers = {"Authorization": f"Bearer {self.token}"}

            async with session.put(spotify_url, headers=headers) as resp:
                response = json.loads(await resp.text())
                print(f"{Fore.CYAN}Spotify API Response: {response}{Style.RESET_ALL}")

                if response.get("message") == "Subscription created":
                    print(f"{Fore.YELLOW}Subscription created successfully!{Style.RESET_ALL}")
                    await self.fetch_current_episode_metadata()
                    self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
        print(f"{Fore.GREEN}> Sent Spotify Authentication{Style.RESET_ALL}")

    async def listen_messages(self):
        try:
            async for message in self.websocket:
                payload = json.loads(message)
                print(f"{Fore.CYAN}< Spotify Message: {payload}{Style.RESET_ALL}")

                if payload.get("type") == "message":
                    if "hm://pusher/v1/connections" in payload.get("uri", ""):
                        print(f"{Fore.BLUE}Message with method received: {payload}{Style.RESET_ALL}")
                        await self.authenticate(payload)

                # Example: Parse Spotify message and update Discord presence
                if "wss://event" in payload.get("uri", ""):
                    await self.prepare_payload(payload["payloads"][0]["events"][0]["event"])

        except websockets.ConnectionClosed as e:
            print(f"{Fore.RED}Spotify Connection closed: {e}{Style.RESET_ALL}")

    async def connect(self):
        while True:
            if not self.token:
                await self.fetch_token()
                if not self.token:
                    print(f"{Fore.RED}Failed to fetch Spotify token. Retrying in 5 seconds...{Style.RESET_ALL}")
                    await asyncio.sleep(5)
                    continue

            websocket_url = SPOTIFY_WEBSOCKET_URL.format(self.token)

            try:
                print(f"{Fore.GREEN}Connecting to WebSocket server...{Style.RESET_ALL}")
                async with websockets.connect(websocket_url, max_size=2 ** 40) as websocket:
                    self.websocket = websocket
                    reconnect_signal = await self.listen_messages()
                    if reconnect_signal == "reconnect":
                        continue  # Reconnect on signal
            except Exception as e:
                print(f"{Fore.RED}Spotify Error: {e}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Retrying connection in 5 minutes...{Style.RESET_ALL}")
                self.token = None
                await asyncio.sleep(5 * 60)


async def main():
    discord_client = DiscordClient(DISCORD_TOKEN)
    spotify_client = SpotifyClient(discord_client)

    await asyncio.gather(discord_client.connect(), spotify_client.connect())


if __name__ == "__main__":
    asyncio.run(main())
