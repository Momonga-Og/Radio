import asyncio
import logging
import aiohttp
import subprocess
import os
import discord
from discord.ext import commands
import interactions  

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
bot = interactions.Client(intents=intents)  # Initialize the bot with interactions.Client

# Access bot token 
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Radio mars station RSS feed URL
RADIO_MARS_RSS_URL = 'https://www.radiomars.ma/ar/categorie/لايف-مارس/feed/'

# FFmpeg path 
FFMPEG_PATH = 'path/to/ffmpeg'  # Example: '/usr/bin/ffmpeg'

# asyncio to make the bot 2 things fetch the feed and prodcast it 
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

# # join a voice channel and start streaming audio
async def join_and_play(ctx, voice_channel):
    if voice_channel is None:
        await ctx.respond('You must be in a voice channel to use this command.')
        return

    # Connect to VC
    voice_client = await voice_channel.connect()

    # to keep audio plying
    async def play_audio():
        while True:
            stream_url = await get_stream_url(RADIO_MARS_RSS_URL)
            if not stream_url:
                logging.warning('Stream URL not found, retrying in 5 seconds')
                await asyncio.sleep(5)
                continue

            # ffmpeg setup dont you think about touching this lines
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

            # stream stopped when the user dsiconennect
            if voice_client.is_connected():
                await voice_client.disconnect()
            break

    # audio task
    play_audio_task = asyncio.create_task(play_audio())

    # stop routine when disco
    await asyncio.gather(play_audio_task, voice_client.wait_for_disconnect())

# Define slash commands
@bot.slash_command(
    name="join",
    description="Join your voice channel and stream radio"
)
async def join(ctx):
    await join_and_play(ctx, ctx.author.voice.channel)

@bot.slash_command(
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
