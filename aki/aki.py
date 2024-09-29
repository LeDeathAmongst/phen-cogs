import logging
import discord
import asyncio

from akinator import Akinator, AkinatorError
from redbot.core import commands
from redbot.core.bot import Red
from Star_Utils import Cog

log = logging.getLogger("red.phenom4n4n.aki")

NSFW_WORDS = ("porn", "sex")

def channel_is_nsfw(channel) -> bool:
    return getattr(channel, "nsfw", False)

class Aki(Cog):
    """Play Akinator in Discord!"""

    def __init__(self, bot: Red) -> None:
        self.bot = bot

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        return

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, theme: str = "characters"):
        """Start a game of Akinator!"""
        try:
            game = Akinator(theme=theme, lang='en', child_mode=True)
            await ctx.typing()
            question = game.start_game()
            aki_color = discord.Color(0xE8BC90)
            view = AkiView(game, aki_color, author_id=ctx.author.id)
            await view.start(ctx, question)
        except AkinatorError as e:
            await ctx.send(f"An error occurred: {str(e)}")
        except Exception as e:
            log.error("An error occurred while starting the Akinator game: %s", e)
            await ctx.send("I encountered an error while connecting to the Akinator servers.")

class AkiView(discord.ui.View):
    def __init__(self, game: Akinator, color: discord.Color, *, author_id: int):
        self.game = game
        self.color = color
        self.num = 1
        self.author_id = author_id
        super().__init__(timeout=120)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your Akinator game.", ephemeral=True
            )
            return False
        await interaction.response.defer()
        return True

    async def send_initial_message(
        self, ctx: commands.Context, channel: discord.TextChannel, question: str
    ) -> discord.Message:
        return await channel.send(embed=self.current_question_embed(question), view=self)

    async def start(self, ctx: commands.Context, question: str) -> discord.Message:
        return await self.send_initial_message(ctx, ctx.channel, question)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question("y", interaction)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question("n", interaction)

    @discord.ui.button(label="I don't know", style=discord.ButtonStyle.blurple)
    async def idk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question("idk", interaction)

    @discord.ui.button(label="Probably", style=discord.ButtonStyle.blurple)
    async def probably(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question("p", interaction)

    @discord.ui.button(label="Probably Not", style=discord.ButtonStyle.blurple)
    async def probably_not(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question("pn", interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            question = self.game.go_back()["question"]
            self.num -= 1
            await self.send_current_question(interaction, question)
        except AkinatorError:
            await interaction.followup.send(
                "You can't go back on the first question, try a different option instead.",
                ephemeral=True,
            )

    @discord.ui.button(label="Win", style=discord.ButtonStyle.gray)
    async def react_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.win(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()

    async def answer_question(self, answer: str, interaction: discord.Interaction):
        self.num += 1
        try:
            progression = self.game.post_answer(answer)
            if "name_proposition" in progression:
                await self.win(interaction)
                return
            question = progression["question"]
            await self.send_current_question(interaction, question)
        except AkinatorError:
            await self.win(interaction)

    async def edit_or_send(self, interaction: discord.Interaction, **kwargs):
        try:
            await interaction.message.edit(**kwargs)
        except discord.NotFound:
            await interaction.followup.send(**kwargs)
        except discord.Forbidden:
            pass

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
        await interaction.message.edit(embed=embed, view=None)
        self.stop()

    async def send_current_question(self, interaction: discord.Interaction, question: str = None):
        if self.game.progression < 80:
            try:
                await self.edit_or_send(interaction, embed=self.current_question_embed(question))
            except discord.HTTPException:
                await self.cancel(interaction)
        else:
            await self.win(interaction)

    async def cancel(
        self, interaction: discord.Interaction, message: str = "Akinator game cancelled."
    ):
        await self.edit_or_send(interaction, content=message, embed=None, view=None)
        self.stop()
