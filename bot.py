import discord
from discord.ext import commands
from gtts import gTTS
import yt_dlp
import os
import asyncio
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

AUTO_CHANNEL_NAME = "creamzone"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

speak_queue = asyncio.Queue()
is_speaking = False

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000 -ac 2'
}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command()
async def say(ctx, *, text):
    await ctx.message.delete()
    await speak_queue.put((ctx, text))
    await process_queue()

@bot.command()
async def play(ctx, url: str):
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await voice_channel.connect()

        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
        }

        # ถ้าไม่ใช่ลิงก์ YouTube ให้ใช้ ytsearch
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"ytsearch:{url}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            stream_url = info['url']
            title = info.get('title', 'ไม่ทราบชื่อเพลง')

        message = await ctx.send(f"🎶 กำลังเล่น: **{title}**")

        await speak_queue.put((ctx, stream_url))
        await process_queue()

    else:
        await ctx.send("คุณต้องอยู่ใน voice channel ก่อนครับ")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.message.delete()
        ctx.voice_client.stop()

        if not speak_queue.empty():
            await process_queue()

async def process_queue():
    global is_speaking
    if is_speaking:
        return

    is_speaking = True
    while not speak_queue.empty():
        ctx, item = await speak_queue.get()

        if isinstance(item, str) and (item.startswith("http://") or item.startswith("https://")):
            await play_stream(ctx, item)
        else:
            await speak_text(ctx, item)
        
    is_speaking = False

async def play_stream(ctx, stream_url):
    if ctx.voice_client:
        ctx.voice_client.stop()
        ctx.voice_client.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS))

        while ctx.voice_client.is_playing():
            await asyncio.sleep(1)

async def speak_text(ctx, text):
    if ctx.voice_client:
        filename = "tts.mp3"
        tts = gTTS(text=text, lang='th', slow=False)
        tts.save(filename)
        ctx.voice_client.stop()
        ctx.voice_client.play(discord.FFmpegPCMAudio(filename))

        while ctx.voice_client.is_playing():
            await asyncio.sleep(0.5)

        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                print(f"ลบไฟล์ {filename} ไม่สำเร็จ: {e}")
    else:
        await ctx.send("บอทยังไม่ได้ join voice channel")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    ctx = await bot.get_context(message)

    if message.channel.name == AUTO_CHANNEL_NAME:
        if ctx.voice_client:
            try:
                await message.delete()
            except discord.errors.Forbidden:
                await message.channel.send("ผมไม่มีสิทธิ์ลบข้อความ 😥")

            await speak_queue.put((ctx, message.content))
            await process_queue()
        else:
            await message.channel.send("บอทยังไม่ได้ join voice channel ใช้ `!join` ก่อนนะ")

# ดึง Token จาก .env
bot.run(os.getenv("DISCORD_TOKEN"))
