import discord
from discord.ext import commands
import asyncio
import logging
import aiohttp
import subprocess
import os

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True  # To handle message-related commands
bot = commands.Bot(command_prefix='!', intents=intents)
# Use the existing command tree from the bot
tree = bot.tree
# Access bot token from environment variable
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

@tree.command(name='hello', description='Replies with Hello!')
async def hello_command(interaction: discord.Interaction):
    await interaction.response.send_message('sir t9awed!')


# Radio station RSS feed URL
RADIO_MARS_RSS_URL = 'https://npr-ice.streamguys1.com/live.mp3'

# FFmpeg path (adjust according to your system installation)
FFMPEG_PATH = r'C:\Users\User\Desktop\ffmpeg\ffmpeg-master-latest-win64-gpl\ffmpeg.exe'

# Function to parse the RSS feed and extract the live stream URL
async def get_stream_url(rss_feed_url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(rss_feed_url) as response:
                if response.status == 200:
                    data = await response.text()
                    try:
                        from xml.etree import ElementTree as ET  # Python 3
                        root = ET.fromstring(data)
                    except ImportError:
                        from xml.etree.ElementTree import fromstring  # Python 2
                        root = fromstring(data)

                    for item in root.findall('channel/item'):
                        for enclosure in item.findall('enclosure'):
                            return enclosure.get('url')
                    return None
        except aiohttp.ClientError as e:
            logging.error(f'Error fetching RSS feed: {e}')
            return None

# Function to join a voice channel and start streaming audio
async def join_and_play(ctx, voice_channel):
    if voice_channel is None:
        await ctx.respond('You must be in a voice channel to use this command.')
        return

    # Connect to voice channel
    voice_client = await voice_channel.connect()

    # Create a coroutine for audio processing
    async def play_audio():
        while True:
            stream_url = await get_stream_url(RADIO_MARS_RSS_URL)
            if not stream_url:
                logging.warning('Stream URL not found, retrying in 5 seconds')
                await asyncio.sleep(5)
                continue

            # Process audio using ffmpeg (replace with appropriate command for your setup)
            process = subprocess.Popen([FFMPEG_PATH, '-i', stream_url, '-f', 's16le', '-ar', '48000', '-ac', '2', '-'], stdout=subprocess.PIPE)
            pcm_data = process.stdout

            try:
                while True:
                    data = await pcm_data.read(discord.opus.OpusVoicePacket.MAX_SIZE)
                    if not data:
                        break
                    await voice_client.send_audio(discord.PCMVoicePacket(data=data, timestamp=ctx.message.created_at))
            except discord.opus.OpusNotLoaded:
                logging.error('Opus not loaded, consider installing libopus')
            except Exception as e:
                logging.error(f'Audio processing error: {e}')

            # Stop stream if an error occurs or when disconnected
            if voice_client.is_connected():
                await voice_client.disconnect()
            break

    # Start the audio processing coroutine
    play_audio_task = asyncio.create_task(play_audio())

    # Wait for the coroutine to finish or for disconnection from voice channel
    await asyncio.gather(play_audio_task, voice_client.wait_for_disconnect())
# Event: when the bot is ready
@bot.event
async def on_ready():
    # Sync command tree with Discord
    try:
        await tree.sync()  # Sync globally or for specific guild
        print(f'Logged in as {bot.user}')
    except Exception as e:
        print(f"Error during command sync: {e}")
# Define slash commands using  library
@tree.command(
    name="join",
    description="Join your voice channel and stream radio"
)
async def join(interaction: discord.Interaction):
    # Check if the user is in a voice channel
    voice_state = interaction.user.voice
    if voice_state is None or voice_state.channel is None:
        await interaction.response.send_message('You must be in a voice channel to use this command.')
        return

    # Get the voice channel
    voice_channel = voice_state.channel

    # Connect to the voice channel
    voice_client = await voice_channel.connect()

    # Start streaming audio
    await join_and_play(interaction, voice_client)

async def join_and_play(interaction, voice_client):
    while True:
        # Get the stream URL
        stream_url = await get_stream_url(RADIO_MARS_RSS_URL)
        if not stream_url:
            logging.warning('Stream URL not found, retrying in 5 seconds')
            await asyncio.sleep(5)
            continue

        # Process audio using ffmpeg or any other suitable method
        process = subprocess.Popen([FFMPEG_PATH, '-i', stream_url, '-f', 's16le', '-ar', '48000', '-ac', '2', '-'], stdout=subprocess.PIPE)
        pcm_data = process.stdout

        try:
            while True:
                data = await pcm_data.read(discord.opus.OpusVoicePacket.MAX_SIZE)
                if not data:
                    break
                await voice_client.send_audio(discord.PCMVoicePacket(data=data, timestamp=datetime.datetime.utcnow()))
        except discord.opus.OpusNotLoaded:
            logging.error('Opus not loaded, consider installing libopus')
        except Exception as e:
            logging.error(f'Audio processing error: {e}')

        # Disconnect if an error occurs
        if not voice_client.is_playing():
            await voice_client.disconnect()
            break


@tree.command(
    name="leave",
    description="Disconnect from the voice channel and stop streaming radio"
)
async def leave(ctx):
    if not bot.voice_clients:
        await ctx.respond('I am not currently connected to a voice channel.')
        return
    for voice_client in bot.voice_clients:
        await voice_client.disconnect()
    await ctx.respond('Disconnected from voice channel and stopped streaming radio.')

# Bot client setup
bot.run(DISCORD_BOT_TOKEN)
