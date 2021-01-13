#!/usr/bin/env python3

# Variables
import config

# Custom modules
import tools
from cogs.calendar import CalendarCog

import discord
from discord.ext import commands
import asyncio


bot = commands.Bot(command_prefix="!")


async def is_admin(ctx):
    return ctx.author.id in config.BOT_ADMINS


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    calCog.start_loops()


@bot.command(name="debug")
@commands.check(is_admin)
async def _debug(ctx: commands.Context, mode: str = "now"):
    if mode in ("now", "n"):
        event = list(calCog.calendar.timeline.now())[0]
    elif mode in ("today", "t"):
        event = list(calCog.calendar.timeline.today())[0]
    else:
        event = list(calCog.calendar.timeline.today())[0]

    embed = tools.generate_event_embed(event, (0, len(students)))
    bot_message: discord.Message = await ctx.send(embed=embed)
    await bot_message.add_reaction(config.REACTION_EMOJI)

    calCog.reacted = set()  # The users who reacted
    courses = tools.get_courses()
    logger.debug(f"Got {len(courses)} course(s): {', '.join([course['name'] for course in courses])}")

    def check(_reaction: discord.Reaction, _user: discord.User):
        return _reaction.message == bot_message and \
               str(_user.id) in students and \
               str(_reaction.emoji) == config.REACTION_EMOJI and \
               _user not in calCog.reacted

    try:
        while len(calCog.reacted) != len(students):
            reaction, user = await bot.wait_for('reaction_add', timeout=config.REACTION_TIMEOUT, check=check)
            bot.loop.create_task(calCog.check_in(user, courses, event, bot_message))
    except asyncio.TimeoutError:
        logger.info("Cancelled")
        embed = tools.generate_event_embed(event, (len(calCog.reacted), len(students)), finished=True)
        await bot_message.edit(embed=embed)
        await bot_message.add_reaction(config.CANCELLED_EMOJI)
    else:
        pass


if __name__ == '__main__':
    logger = tools.get_logger(name="bot", level="DEBUG")
    students = tools.load_students(config.STUDENTS_FILE)
    calCog = CalendarCog(bot, students, logger=logger)
    bot.add_cog(calCog)
    bot.run(config.BOT_TOKEN)
