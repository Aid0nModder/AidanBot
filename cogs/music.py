"""
Based on A simple music bot written in discord.py using youtube-dl. by Valentin B.
"""

import discord
from discord.ext import commands

import asyncio, functools, itertools, math, random, youtube_dl
from async_timeout import timeout
from functions import getComEmbed

youtube_dl.utils.bug_reports_message = lambda: ""

class VoiceError(Exception):
    pass
class YTDLError(Exception):
    pass

# handles the data. basicly what gets the video...
class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }
    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx:commands.Context, source:discord.FFmpegPCMAudio, *, data:dict, volume:float=0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    # i'm not even going to pretend i know what this does...
    @classmethod
    async def create_source(cls, ctx:commands.Context, search:str, *, loop:asyncio.BaseEventLoop=None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

# handles the playing embed... that's it
class Song:
    __slots__ = ('source', 'requester', 'client')
    def __init__(self, source:YTDLSource, client):
        self.source = source
        self.requester = source.requester
        self.client = client

    def now_playing(self, ctx):
        return getComEmbed(ctx, self.client, "Music", "**Now Playing:**", f"'{self.source.title}' by {self.source.uploader}.").set_thumbnail(url=self.source.thumbnail)
    def now_playing_text(self):
        return f"'{self.source.title}' by {self.source.uploader}."
    def queue_text(self, i):
        return f"`{i}.` [**{self.source.title}**]({self.source.url})\n"
        
# good old queue, fuck queues
class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]
    def __iter__(self):
        return self._queue.__iter__()
    def __len__(self):
        return self.qsize()
    def clear(self):
        self._queue.clear()
    def shuffle(self):
        random.shuffle(self._queue)
    def remove(self, index: int):
        del self._queue[index]

# plays the music :yroue:
class VoiceState:
    def __init__(self, client:commands.Bot, ctx: commands.Context):
        self.client = client
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = client.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop
    @loop.setter
    def loop(self, value:bool):
        self._loop = value
    @property
    def volume(self):
        return self._volume
    @volume.setter
    def volume(self, value:float):
        self._volume = value
    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # Try to get the next song within 3 minutes. If no song will be added to the queue in time, the player will disconnect due to performance reasons.
                try:
                    async with timeout(180): # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.client.loop.create_task(self.stop())
                    return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)
            emb = self.current.now_playing(self._ctx)
            await self.current.source.channel.send(embed=emb)
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))
        self.next.set()

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()
        if self.voice:
            await self.voice.disconnect()
            self.voice = None

### acctual commands ###

import json
with open('./commanddata.json') as file:
    temp = json.load(file)
    DESC = temp["desc"]

class MusicCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.voice_states = {}

    def get_voice_state(self, ctx):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.client, ctx)
            self.voice_states[ctx.guild.id] = state
        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.client.loop.create_task(state.stop())

    def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage("This command can't be used in DM channels.")
        return True

    async def cog_before_invoke(self, ctx):
        ctx.voice_state = self.get_voice_state(ctx)

    @commands.command(description=DESC["join"], invoke_without_subcommand=True)
    async def join(self, ctx):
        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return
        ctx.voice_state.voice = await destination.connect()

    @commands.command(description=DESC["leave"])
    async def leave(self, ctx):
        if not ctx.voice_state.voice:
            return await ctx.send("I'm not in a voice channel, bruh.")
        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(description=DESC["now"], aliases=['current', 'playing'])
    async def now(self, ctx):
        emb = ctx.voice_state.current.now_playing(ctx)
        await ctx.send(embed=emb)

    @commands.command(description=DESC["pause"])
    async def pause(self, ctx):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(description=DESC["resume"])
    async def resume(self, ctx):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(description=DESC["stop"])
    async def stop(self, ctx):
        ctx.voice_state.songs.clear()
        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(description=DESC["skip"])
    async def skip(self, ctx):
        if ctx.voice_state.is_playing and len(ctx.voice_state.songs) > 0:
            ctx.voice_state.skip()
            await ctx.message.add_reaction('⏭')

    @commands.command(description=DESC["queue"])
    async def queue(self, ctx, *, page:int=1):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send("Huh, it's empty lol.")

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)
        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += song.queue_text(i+1)

        emb = getComEmbed(ctx, self.client, "Music", f"**Queue (Page {page}/{pages}):**", f"**{len(ctx.voice_state.songs)} Tracks:**\n\n{queue}")
        await ctx.send(embed=emb)

    @commands.command(description=DESC["remove"])
    async def remove(self, ctx, index:int):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('The Queue is a bit... empty.')
        ctx.voice_state.songs.remove(index-1)
        await ctx.message.add_reaction('✅')

    @commands.command(description=DESC["loop"])
    async def loop(self, ctx):
        if not ctx.voice_state.is_playing:
            return await ctx.send('It might be a good idea to play a song first.')
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @commands.command(description=DESC["play"])
    async def play(self, ctx, *, search):
        if not ctx.voice_state.voice:
            await ctx.invoke(self.join)
        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.client.loop)
            except YTDLError as e:
                await ctx.send(f'An error occurred while processing this request: {e}')
            else:
                song = Song(source, self.client)
                await ctx.voice_state.songs.put(song)
                await ctx.send(f"**Added to queue:** {song.now_playing_text()}")

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError("You are not connected to any voice channel.")
        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError("Bot is already in a voice channel.")

def setup(client):
    client.add_cog(MusicCog(client))