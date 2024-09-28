import discord
from akinator_python import Akinator
from redbot.core import commands, Config
from redbot.core.bot import Red

from .views import AkiView, channel_is_nsfw

log = logging.getLogger("red.phenom4n4n.aki")

class Aki(commands.Cog):
    """
    Play Akinator in Discord!
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

    __version__ = "1.2.0"

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return f"{pre_processed}{n}\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, language: str.lower = "en"):
        """
        Start a game of Akinator!
        """
        if language not in {"en", "fr", "es", "de", "it", "nl", "pt", "tr", "ar", "ru", "jp"}:
            await ctx.send(
                "Invalid language. Please choose from the following: en, fr, es, de, it, nl, pt, tr, ar, ru, jp"
            )
            return

        aki = Akinator(language=language)
        question = aki.start_game()
        await ctx.send(question)

        while aki.progression <= 80:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=30.0)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond!")
                return

            answer = msg.content.lower()
            if answer not in ["y", "n", "idk", "p", "pn", "b"]:
                await ctx.send("Please respond with 'y', 'n', 'idk', 'p', 'pn', or 'b'.")
                continue

            if answer == "b":
                question = aki.go_back()
            else:
                question = aki.post_answer(answer)

            await ctx.send(question)

        aki.win()
        await ctx.send(f"I guess: {aki.name} - {aki.description}\nIs this correct? (y/n)")

        def check_final(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["y", "n"]

        try:
            msg = await self.bot.wait_for("message", check=check_final, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond!")
            return

        if msg.content.lower() == "y":
            await ctx.send("Yay! I guessed it right!")
        else:
            await ctx.send("Oh no! Let's try again next time.")
