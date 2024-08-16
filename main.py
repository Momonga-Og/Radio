import discord
from discord.ext import commands, tasks
import asyncio
import logging
import os
import requests
import io
import pygame

# Configure logging
logging.basicConfig(format="[%(levelname)s] %(asctime)s: %(message)s", level=logging.INFO)

# Discord Intents
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

# Discord bot instance with command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Slash command tree
tree = bot.tree

if os.getenv('CI'):
    print("Running in a CI/CD environment. Skipping audio initialization.")
else:
    # Pygame initialization for audio playback
    pygame.mixer.quit()
    pygame.mixer.init()

# Environment variable for Discord bot token
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Dictionary of radio streams
radio_stations = {
    "Radio Mars": "https://radiomars.ice.infomaniak.ch/radiomars-128.mp3",
    "Hit Radio": "https://hitradio-maroc.ice.infomaniak.ch/hitradio-maroc-128.mp3",
    "Radio Aswat": "https://aswat.ice.infomaniak.ch/aswat-high.mp3",
    "Medina FM": "https://medinafm.ice.infomaniak.ch/medinafm-64.mp3",
    "Qor2an": "https://virmach1.hajjam.net:8005/stream/1/"
}

def play_audio_from_url(url):
    """
    Fetches and plays audio from a URL using Pygame mixer.

    Args:
        url (str): The URL of the audio stream.
    """
    try:
        # Fetch audio data
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Load audio data
            audio_data = io.BytesIO(response.content)
            pygame.mixer.music.load(audio_data)
            logging.info("Audio loaded successfully.")
            # Play audio
            pygame.mixer.music.play()
            logging.info("Audio playback started.")
        else:
            logging.error(f"Failed to fetch audio data: {response.status_code}")
    except Exception as e:
        logging.error(f"Error loading or playing audio: {e}")

@bot.event
async def on_ready():
    """
    Event handler for when the bot is ready.

    Attempts to synchronize slash commands with Discord.
    """
    try:
        await bot.tree.sync()
        logging.info(f'Logged in as {bot.user}')
    except Exception as e:
        logging.error(f"Error during command sync: {e}")
    check_voice_clients.start()  # Start the task to check voice clients

@tree.command(
    name="help",
    description="Shows the available commands and radio stations"
)
async def help_command(interaction: discord.Interaction):
    """
    Provides information about available commands and radio stations.
    """
    commands_list = (
        "**Available Commands:**\n"
        "/help - Show this help message\n"
        "/join - Join your voice channel and choose a radio station to stream\n"
        "/stop - Stop streaming radio while remaining in the voice channel\n"
        "/leave - Disconnect from the voice channel and stop streaming radio\n\n"
        "**Available Radio Stations:**\n"
    )

    radio_list = "\n".join([f"{name}" for name in radio_stations.keys()])

    dm_message = "For further questions, feel free to DM Ogthem in Discord."

    await interaction.response.send_message(commands_list + radio_list + "\n\n" + dm_message)

@tree.command(
    name="join",
    description="Join your voice channel and choose a radio station to stream",
)
async def join(interaction: discord.Interaction):
    """
    Join user's voice channel and start streaming radio.

    Checks for existing connection, user's voice channel presence,
    and handles potential errors. Informs the user if already connected elsewhere.
    """
    # Check for existing connection in the current server
    if bot.voice_clients:
        for voice_client in bot.voice_clients:
            if voice_client.guild.id == interaction.guild.id:
                await interaction.response.send_message(
                    "I am already connected to a voice channel in this server."
                )
                return

    # No existing connection in this server, proceed with joining
    voice_state = interaction.user.voice
    if not voice_state or not voice_state.channel:
        await interaction.response.send_message("You must be in a voice channel to use this command.")
        return

    voice_channel = voice_state.channel

    try:
        voice_client = await voice_channel.connect()
        await interaction.response.send_message(
            "Connected to the voice channel! Please select a radio station to play:",
            view=RadioSelectView(voice_client))
        logging.info(f"Joined voice channel: {voice_channel}")
    except Exception as e:
        logging.error(f"Error joining voice channel: {e}")
        await interaction.response.send_message("Failed to join voice channel.")

class RadioSelectView(discord.ui.View):
    def __init__(self, voice_client):
        super().__init__(timeout=60)
        self.voice_client = voice_client

        options = [
            discord.SelectOption(label=name, value=url)
            for name, url in radio_stations.items()
        ]

        self.add_item(RadioSelect(options, self.voice_client))

class RadioSelect(discord.ui.Select):
    def __init__(self, options, voice_client):
        super().__init__(placeholder="Choose a radio station...", min_values=1, max_values=1, options=options)
        self.voice_client = voice_client

    async def callback(self, interaction: discord.Interaction):
        selected_url = self.values[0]
        selected_name = next((name for name, url in radio_stations.items() if url == selected_url), "Unknown Station")

        try:
            self.voice_client.stop()
            self.voice_client.play(discord.FFmpegPCMAudio(selected_url))
            logging.info(f"Playing radio station: {selected_name}")
            await interaction.response.send_message(f"Now playing: {selected_name}")
        except Exception as e:
            logging.error(f"Error playing audio: {e}")
            await interaction.response.send_message("Failed to start audio playback.")

@tree.command(
    name="stop",
    description="Stop streaming radio while remaining in the voice channel",
)
async def stop(interaction: discord.Interaction):
    """
    Stops the radio stream playback but stays connected to the voice channel.

    Checks for existing connection and handles potential errors.
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not voice_client:
        await interaction.response.send_message("I am not currently streaming radio.")
        return

    if not voice_client.is_playing():
        await interaction.response.send_message("Radio is already stopped.")
        return

    try:
        voice_client.stop()
        logging.info("Audio playback stopped.")
        await interaction.response.send_message("Stopped playing the radio.")
    except Exception as e:
        logging.error(f"Error stopping audio playback: {e}")
        await interaction.response.send_message("Failed to stop audio playback.")

@tree.command(
    name="leave",
    description="Disconnect from the voice channel and stop streaming radio",
)
async def leave(interaction: discord.Interaction):
    """
    Disconnects from the voice channel and stops streaming radio.

    This functionality remains mostly unchanged.
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not voice_client:
        await interaction.response.send_message("I am not currently connected to a voice channel.")
        return

    try:
        await voice_client.disconnect()
        logging.info(f"Disconnected from voice channel: {voice_client.channel}")
        await interaction.response.send_message("Disconnected from the voice channel.")
    except Exception as e:
        logging.error(f"Error disconnecting from voice channel: {e}")
        await interaction.response.send_message("Failed to disconnect from voice channel.")

@tasks.loop(minutes=10)
async def check_voice_clients():
    """
    Task to periodically check the status of voice clients and reconnect if necessary.
    """
    for voice_client in bot.voice_clients:
        if not voice_client.is_playing():
            logging.info(f"Reconnecting to voice channel: {voice_client.channel}")
            try:
                await voice_client.disconnect()
                await voice_client.channel.connect()
                # Optionally, restart playback with a selected radio station here
            except Exception as e:
                logging.error(f"Error reconnecting to voice channel: {e}")

# New super slash command
@tree.command(
    name="super",
    description="A powerful super command with additional capabilities"
)
async def super_command(interaction: discord.Interaction):
    """
    Executes a powerful super command with additional capabilities.
    """
    await interaction.response.send_message("This is the super command! 🚀")

# Bot client setup (remains unchanged)
bot.run(DISCORD_BOT_TOKEN)
