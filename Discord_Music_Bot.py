import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random

# 봇의 기본 설정 및 권한(Intents) 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 전역 변수 초기화
current_track = None      # 현재 재생 중인 곡
repeat_mode = False       # 반복 재생 모드 ON/OFF

# yt_dlp 옵션 (YouTube 음원 추출 설정)
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
}

# FFmpeg 옵션 (음성 스트림 변환 시 사용)
ffmpeg_options = {
    'options': '-vn',  # 비디오 제외, 오디오만 재생
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

queue = asyncio.Queue()   # 음악 대기열(큐)
now_playing = None        # 현재 재생 중인 소스


class YTDLSource(discord.PCMVolumeTransformer):
    """yt_dlp로부터 음원을 추출하고, 디스코드 음성 재생 가능한 오디오 소스 생성"""

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')  # 곡 제목
        self.url = data.get('webpage_url')  # 유튜브 URL

    @classmethod
    async def create_source(cls, search, *, loop=None, stream=True):
        """검색어나 URL로부터 음원 정보를 가져오고, FFmpegPCMAudio 생성"""
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=not stream))
        if 'entries' in data:  # 검색 결과가 여러개면 첫 번째 선택
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


async def play_next(ctx):
    """큐에서 다음 곡을 가져와 재생하거나, 큐가 비었으면 음성 채널에서 나감"""
    global now_playing
    if queue.empty():
        now_playing = None
        await ctx.send("🎵 Queue is empty. Leaving the channel.")
        await ctx.voice_client.disconnect()
        return

    source = await queue.get()
    now_playing = source
    ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    await ctx.send(f"▶️ Now playing: {source.title}")


@bot.command()
async def join(ctx):
    """봇을 음성 채널에 접속시킴"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f'✅ Joined {channel}')
    else:
        await ctx.send('❌ You are not connected to a voice channel.')


@bot.command()
async def leave(ctx):
    """봇을 음성 채널에서 퇴장시킴"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send('👋 Disconnected from the voice channel.')
    else:
        await ctx.send('❌ I am not connected to any voice channel.')


@bot.command()
async def play(ctx, *, search: str):
    """YouTube URL 또는 검색어로 음악 재생 및 큐 관리"""
    global now_playing
    global current_track

    async with ctx.typing():  # 로딩 중임을 표시
        source = await YTDLSource.create_source(search, loop=bot.loop, stream=True)

        # 봇이 음성 채널에 없으면 연결 시도
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ 음성 채널에 들어가 있어야 해요.")
                return

        # 재생 중이 아니면 바로 재생, 아니면 큐에 추가
        if not ctx.voice_client.is_playing():
            now_playing = source
            current_track = source

            def after_playing(error):
                if error:
                    print(f"Error during playback: {error}")
                elif repeat_mode:
                    fut = asyncio.run_coroutine_threadsafe(repeat_track(ctx), bot.loop)
                    fut.result()
                else:
                    fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
                    fut.result()

            ctx.voice_client.play(source, after=after_playing)
            await ctx.send(f"▶️ Now playing: {source.title}")
        else:
            await queue.put(source)
            await ctx.send(f"📥 Added to queue: {source.title}")


@bot.command()
async def skip(ctx):
    """현재 재생 중인 음악을 스킵함"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭ Skipping current track...")
    else:
        await ctx.send("❌ No music is playing.")


@bot.command()
async def stop(ctx):
    """음악 정지 및 대기열 초기화 후 음성 채널 퇴장"""
    if ctx.voice_client is not None:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
    while not queue.empty():
        await queue.get()
    await ctx.send("음악을 정지하고 큐를 모두 비웠습니다.")


@bot.command()
async def repeat(ctx):
    """반복 재생 모드 ON/OFF 토글"""
    global repeat_mode
    repeat_mode = not repeat_mode
    await ctx.send(f"반복 모드: {'ON' if repeat_mode else 'OFF'}")


def after_playing(error, ctx):
    """곡 재생 완료 후 호출되는 함수, 반복 또는 다음 곡 재생 처리"""
    if repeat_mode:
        fut = asyncio.run_coroutine_threadsafe(repeat_track(ctx), bot.loop)
        fut.result()
    else:
        next_song = queue.get_nowait() if not queue.empty() else None
        if next_song:
            fut = asyncio.run_coroutine_threadsafe(play_next(ctx, next_song), bot.loop)
            fut.result()


async def repeat_track(ctx):
    """현재 곡을 반복 재생"""
    if current_track:
        ctx.voice_client.play(current_track, after=lambda e: after_playing(e, ctx))


@bot.command(name="queue")
async def queue_list(ctx):
    """현재 대기열(큐) 목록 출력"""
    if queue.empty():
        await ctx.send("📭 The queue is currently empty.")
    else:
        items = list(queue._queue)
        msg = "\n".join([f"{i+1}. {track.title}" for i, track in enumerate(items)])
        await ctx.send(f"🎶 **Current Queue:**\n{msg}")


@bot.command()
async def clear(ctx):
    """큐에 남은 모든 곡 삭제"""
    cleared = 0
    while not queue.empty():
        await queue.get()
        cleared += 1
    await ctx.send(f"큐를 비웠습니다. ({cleared}곡 삭제됨)")


@bot.command()
async def nowplaying(ctx):
    """현재 재생 중인 곡 제목 표시"""
    if current_track:
        await ctx.send(f"🎶 Now playing: **{current_track.title}**")
    else:
        await ctx.send("❗ 현재 재생 중인 곡이 없습니다.")


@bot.command()
async def pause(ctx):
    """재생 중인 음악 일시정지"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Music paused.")
    else:
        await ctx.send("⚠️ No music is currently playing.")


@bot.command()
async def resume(ctx):
    """일시정지 된 음악 다시 재생"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Music resumed.")
    else:
        await ctx.send("⚠️ Music is not paused.")


# 봇 실행 (본인의 디스코드 봇 토큰 입력)
bot.run('YOUR_DISCORD_BOT_TOKEN')
