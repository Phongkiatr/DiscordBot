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
    'options': '-vn -b:a 320k -ar 48000 -ac 2 -f pcm_s16le'
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
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': 'downloads/%(id)s.%(ext)s',
        }

        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'ไม่ทราบชื่อเพลง')

            if not filename.endswith(".mp3"):
                filename = os.path.splitext(filename)[0] + ".mp3"

        # ส่งข้อความแจ้งเตือนการเล่นเพลง
        message = await ctx.send(f"🎶 กำลังเล่น: **{title}**")

        # เพิ่มเพลงในคิว
        await speak_queue.put((ctx, filename))
        await process_queue()

        # ลบข้อความหลังจากเล่นเสร็จ
        await message.delete()
    else:
        await ctx.send("คุณต้องอยู่ใน voice channel ก่อนครับ")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()

        if not speak_queue.empty():
            await process_queue()
        else:
            await ctx.send("ไม่มีกำหนดการเล่นเสียงแล้วครับ")
    else:
        await ctx.send("บอทยังไม่ได้เล่นเสียงครับ")

async def process_queue():
    global is_speaking
    if is_speaking:
        return

    is_speaking = True
    while not speak_queue.empty():
        ctx, item = await speak_queue.get()

        if isinstance(item, str) and item.endswith(".mp3") and os.path.exists(item):
            await play_audio_from_queue(ctx, item)
        else:
            await speak_text(ctx, item)

    if speak_queue.empty():
        await ctx.send("ไม่มีเสียงในคิวครับ.")
        
    is_speaking = False

async def play_audio_from_queue(ctx, audio_file):
    if ctx.voice_client:
        ctx.voice_client.stop()
        ctx.voice_client.play(discord.FFmpegPCMAudio(audio_file))

        while ctx.voice_client.is_playing():
            await asyncio.sleep(1)

        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except Exception as e:
                print(f"ลบไฟล์ {audio_file} ไม่สำเร็จ: {e}")

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
