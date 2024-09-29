import logging
import discord
import aiohttp
from akinator_python import Akinator, AkinatorError
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from Star_Utils import Cog, Buttons, Loop

log = logging.getLogger("red.phenom4n4n.aki")

NSFW_WORDS = ("porn", "sex")


def channel_is_nsfw(channel) -> bool:
    return getattr(channel, "nsfw", False)


class Aki(Cog):
    """Play Akinator in Discord!"""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8237578807127857,
            force_registration=True,
        )
        self.session = aiohttp.ClientSession()
        self.active_loops = []

    async def cog_unload(self):
        await self.session.close()
        for loop in self.active_loops:
            loop.stop_all()

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, language: str = "en"):
        """Start a game of Akinator!"""
        await ctx.typing()
        child_mode = not channel_is_nsfw(ctx.channel)
        language = language or "en"  # Default to English if no language is provided
        try:
            aki = Akinator(lang=language, child_mode=child_mode)
            question = aki.start_game()
        except AkinatorError as e:
            await ctx.send(f"An error occurred: {e}")
            return
        except Exception as e:
            log.error("An error occurred while starting the Akinator game: %s", e)
            await ctx.send("I encountered an error while connecting to the Akinator servers.")
            return

        aki_color = discord.Color(0xE8BC90)
        view = AkiView(aki, aki_color, author_id=ctx.author.id)
        await view.start(ctx)


class AkiView(discord.ui.View):
    def __init__(self, game: Akinator, color: discord.Color, *, author_id: int):
        super().__init__(timeout=120)
        self.game = game
        self.color = color
        self.num = 1
        self.author_id = author_id
        self.message = None
        self.add_buttons()

    def add_buttons(self):
        buttons = [
            {"label": "Yes", "style": discord.ButtonStyle.green, "custom_id": "yes"},
            {"label": "No", "style": discord.ButtonStyle.red, "custom_id": "no"},
            {"label": "I don't know", "style": discord.ButtonStyle.blurple, "custom_id": "idk"},
            {"label": "Probably", "style": discord.ButtonStyle.blurple, "custom_id": "probably"},
            {"label": "Probably Not", "style": discord.ButtonStyle.blurple, "custom_id": "probably_not"},
            {"label": "Back", "style": discord.ButtonStyle.gray, "custom_id": "back"},
            {"label": "Win", "style": discord.ButtonStyle.gray, "custom_id": "win"},
            {"label": "Cancel", "style": discord.ButtonStyle.gray, "custom_id": "cancel"},
        ]
        self.buttons_view = Buttons(
            buttons=buttons,
            function=self.button_callback,
            members=[self.author_id]
        )
        self.add_item(self.buttons_view)

    async def button_callback(self, view: Buttons, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        if custom_id == "yes":
            await self.answer_question("y", interaction)
        elif custom_id == "no":
            await self.answer_question("n", interaction)
        elif custom_id == "idk":
            await self.answer_question("idk", interaction)
        elif custom_id == "probably":
            await self.answer_question("p", interaction)
        elif custom_id == "probably_not":
            await self.answer_question("pn", interaction)
        elif custom_id == "back":
            await self.back(interaction)
        elif custom_id == "win":
            await self.win(interaction)
        elif custom_id == "cancel":
            await self.end(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your Akinator game.", ephemeral=True
            )
            return False
        await interaction.response.defer()
        return True

    async def send_initial_message(self, ctx: commands.Context, channel: discord.TextChannel) -> discord.Message:
        question = self.game.question
        self.message = await channel.send(embed=self.current_question_embed(question), view=self)
        return self.message

    async def start(self, ctx: commands.Context) -> discord.Message:
        return await self.send_initial_message(ctx, ctx.channel)

    async def answer_question(self, answer: str, interaction: discord.Interaction):
        self.num += 1
        try:
            self.game.post_answer(answer)
            if self.game.answer_id:
                await self.win(interaction)
                return
            question = self.game.question
            await self.update_message(question)
        except Exception as e:
            log.error("An error occurred while answering: %s", e)
            await self.win(interaction)

    async def back(self, interaction: discord.Interaction):
        try:
            self.game.go_back()
            question = self.game.question
            self.num -= 1
            await self.update_message(question)
        except Exception as e:
            log.error("An error occurred while going back: %s", e)
            await interaction.followup.send(
                "You can't go back on the first question, try a different option instead.",
                ephemeral=True,
            )

    async def update_message(self, question: str):
        """Update the original message with the new question."""
        if self.message:
            try:
                await self.message.edit(embed=self.current_question_embed(question))
            except discord.NotFound:
                log.error("The message to edit was not found.")
            except discord.Forbidden:
                log.error("Editing the message is forbidden.")

    def current_question_embed(self, question: str):
        e = discord.Embed(
            color=self.color,
            title=f"Question #{self.num}",
            description=question,
        )
        if self.game.progression > 0:
            e.set_footer(text=f"{round(self.game.progression, 2)}% guessed")
        return e

    def get_winner_embed(self) -> discord.Embed:
        win_embed = discord.Embed(
            color=self.color,
            title=f"I'm sure it's {self.game.name}!",
            description=self.game.description,
        )
        win_embed.set_image(url=self.game.photo)
        return win_embed

    def get_nsfw_embed(self):
        return discord.Embed(
            color=self.color,
            title="I guessed it, but this result is inappropriate.",
            description="Try again in a NSFW channel.",
        )

    def text_is_nsfw(self, text: str) -> bool:
        if text is None:
            return False
        text = text.lower()
        return any(word in text for word in NSFW_WORDS)

    async def win(self, interaction: discord.Interaction):
        try:
            if not channel_is_nsfw(interaction.channel) and self.text_is_nsfw(self.game.description):
                embed = self.get_nsfw_embed()
            else:
                embed = self.get_winner_embed()
        except Exception as e:
            log.exception("An error occurred while trying to win an Akinator game.", exc_info=e)
            embed = discord.Embed(
                color=self.color,
                title="An error occurred while trying to win the game.",
                description="Try again later.",
            )
        await self.message.edit(embed=embed, view=None)
        self.stop()

    async def end(self, interaction: discord.Interaction):
        await self.message.delete()
        self.stop()
