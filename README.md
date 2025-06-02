# 🎧 Discord Spotify Presence Sync

This Python project allows you to **sync your Spotify activity to your Discord Rich Presence** in real time using **Discord and Spotify WebSockets**.

---

## ✨ Features

- Displays your **currently playing Spotify track** as a rich presence in Discord.
- Automatically updates your presence when the track changes or playback stops.
- Customizable status with emoji.
- Handles reconnects and heartbeat protocols for both Discord and Spotify.

---

## 📦 Requirements

- Python 3.8+
- A `.env` file with:
  ```env
  TOKEN=your_discord_bot_token
  DISCORD_TOKEN=your_discord_user_token
  ```
- Install dependencies:
  ```bash
  pip install aiohttp websockets python-dotenv colorama
  ```

---

## 🚀 How It Works

1. **Connects to Discord Gateway** using a bot token for presence updates.
2. **Fetches Spotify token** linked to your Discord account.
3. **Connects to Spotify's WebSocket dealer endpoint** using the retrieved token.
4. **Listens for track playback events**, and when a song is playing:
   - Sends detailed track info (name, artist, album art, timestamp) to Discord.
   - Updates your status to show what you're listening to.

---

## 📂 Project Structure

- `main.py`: Main logic for managing both WebSocket connections and presence updates.
- `DiscordClient`: Handles connection, heartbeat, and presence updates with Discord.
- `SpotifyClient`: Fetches token from Discord API, connects to Spotify, parses track events.

---

## 🛠️ Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/discord-spotify-presence.git
   cd discord-spotify-presence
   ```

2. Create a `.env` file:
   ```env
   TOKEN=your_discord_bot_token
   DISCORD_TOKEN=your_discord_user_token
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the app:
   ```bash
   python main.py
   ```

---

## 🧠 Notes

- You must have your **Spotify account connected to Discord** for the token fetch to work.
- This tool **does not control playback** — it only listens for updates and syncs presence.

---

## ⚠️ Disclaimer

This project is intended for **educational purposes**. Use responsibly and in accordance with the terms of service of both Discord and Spotify.