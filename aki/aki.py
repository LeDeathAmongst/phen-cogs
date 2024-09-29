import logging
import discord
from akinator_python import Akinator, AkinatorError, CantGoBackAnyFurther
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from Star_Utils import Cog
log = logging.getLogger("red.star.aki")

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

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.command(aliases=["akinator"])
    async def aki(self, ctx: commands.Context, language: str = "en", theme: str = "characters"):
        """Start a game of Akinator!"""
        await ctx.typing()
        child_mode = not channel_is_nsfw(ctx.channel)
        try:
            aki = Akinator(language=language, theme=theme, child_mode=child_mode)
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
        self.author_id = author_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your Akinator game.", ephemeral=True
            )
            return False
        await interaction.response.defer()
        return True

    async def send_initial_message(self, ctx: commands.Context, channel: discord.TextChannel) -> discord.Message:
        self.message = await channel.send(embed=self.current_question_embed(), view=self)
        return self.message

    async def start(self, ctx: commands.Context) -> discord.Message:
        return await self.send_initial_message(ctx, ctx.channel)

    async def answer_question(self, answer: str, interaction: discord.Interaction):
        try:
            self.game.post_answer(answer)
            await self.send_current_question(interaction)
        except AkinatorError as e:
            log.error("An error occurred while answering: %s", e)
            await self.win(interaction)

    async def send_current_question(self, interaction: discord.Interaction):
        if self.game.progression < 80:
            await self.edit(interaction)
        else:
            await self.win(interaction)

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
            self.game.go_back()
            await self.send_current_question(interaction)
        except CantGoBackAnyFurther:
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

    def current_question_embed(self):
        e = discord.Embed(
            color=self.color,
            title=f"Question #{self.game.step}",
            description=self.game.question,
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

    async def edit(self, interaction: discord.Interaction):
        await interaction.message.edit(embed=self.current_question_embed(), view=self)

    async def cancel(self, interaction: discord.Interaction, message: str = "Akinator game cancelled."):
        await interaction.message.edit(content=message, embed=None, view=None)
        self.stop()

# To add the cog to your bot
def setup(bot: Red):
    bot.add_cog(Aki(bot))
