import discord
from discord.ext import commands
import asyncio
import logging
import os
import requests
import io
import pygame

# Configure logging -
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

# Check if running in a CI/CD environment
if os.getenv('CI'):
    print("Running in a CI/CD environment. Skipping audio initialization.")
else:
    # Pygame initialization for audio playback
    pygame.mixer.quit()
    pygame.mixer.init()

# Environment variable for Discord bot token
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Radio stream URL
audio_url = "https://hitradio-maroc.ice.infomaniak.ch/hitradio-maroc-128.mp3"


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


@tree.command(
    name="hello",
    description="Replies with Hello!",
)
async def hello_command(interaction: discord.Interaction):
    """
    Simple slash command that replies with "Hello!"
    """
    await interaction.response.send_message("Hello!")


@tree.command(
    name="join",
    description="Join your voice channel and stream radio",
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
        await join_and_play(interaction, voice_client)
        logging.info(f"Joined voice channel: {voice_channel}")
    except Exception as e:
        logging.error(f"Error joining voice channel: {e}")
        await interaction.response.send_message("Failed to join voice channel.")


async def join_and_play(interaction, voice_client):
    """
    Starts streaming audio from the radio URL using FFmpegPCMAudio.

    Handles potential errors during playback.
    """
    stream_url = audio_url  # Replace with your radio stream URL
    if not stream_url:
        logging.warning("Stream URL not found")
        return

    try:
        voice_client.play(discord.FFmpegPCMAudio(stream_url))
        logging.info("Audio playback started.")
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
    voice_client = bot.voice_clients and bot.voice_clients.get(interaction.guild.id)

    if not voice_client:
        await interaction.response.send_message("I am not currently streaming radio.")
        return

    if not voice_client.is_playing():
        await interaction.response.send_message("Radio is already stopped.")
        return

    try:
        voice_client.stop()
        logging.info("Audio playback stopped.")
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
    voice_client = bot.voice_clients and bot.voice_clients.get(interaction.guild.id)

    if not voice_client:
        await interaction.respond("I am not currently connected to a voice channel.")
        return

    try:
        await voice_client.disconnect()
        logging.info(f"Disconnected from voice channel: {voice_client.channel}")
    except Exception as e:
        logging.error(f"Error disconnecting from voice channel: {e}")
        await interaction.respond("Failed to disconnect from voice channel.")

# Bot client setup (remains unchanged)
bot.run(DISCORD_BOT_TOKEN)


