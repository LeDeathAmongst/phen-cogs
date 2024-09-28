import logging
import aiohttp
import akinator
import discord
from akinator.async_aki import Akinator
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from .views import AkiView, channel_is_nsfw

log = logging.getLogger("red.phenom4n4n.aki")

VALID_LANGUAGES = {"en", "fr", "es", "de", "it", "nl", "pt", "tr", "ar", "ru", "jp"}

class Aki(commands.Cog):
    """
    Play Akinator in Discord!
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8237578807127857,
            force_registration=True,
        )
        self.session = aiohttp.ClientSession()

    __version__ = "1.2.0"

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return f"{pre_processed}{n}\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    async def cog_unload(self):
        await self.session.close()

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, language: str.lower = "en"):
        """
        Start a game of Akinator!
        """
        if language not in VALID_LANGUAGES:
            await ctx.send(
                "Invalid language. Please choose from the following: "
                + ", ".join(VALID_LANGUAGES)
            )
            return

        await ctx.typing()
        aki = Akinator()
        child_mode = not channel_is_nsfw(ctx.channel)
        try:
            await aki.start_game(
                language=language.replace(" ", "_"),
                child_mode=child_mode,
                client_session=self.session,
            )
        except akinator.InvalidLanguageError:
            await ctx.send(
                "Invalid language. Refer here to view valid languages.\n<https://github.com/NinjaSnail1080/akinator.py#functions>"
            )
        except AttributeError as e:
            log.error("An AttributeError occurred: %s", e)
            await ctx.send("An unexpected error occurred while starting the game. Please try again.")
        except Exception as e:
            log.error("An error occurred while starting the Akinator game: %s", e)
            await ctx.send("I encountered an error while connecting to the Akinator servers.")
        else:
            aki_color = discord.Color(0xE8BC90)
            await AkiView(aki, aki_color, author_id=ctx.author.id).start(ctx)
