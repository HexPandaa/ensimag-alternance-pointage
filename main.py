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


@bot.command(name="list")
@commands.check(is_admin)
async def _cmd_list_calendars(ctx: commands.Context):
    message = "\n".join(calCog.calendars)
    await ctx.send(message)


@bot.command(name="debug")
@commands.check(is_admin)
async def _debug(ctx: commands.Context, calendar: str, mode: str = "now"):
    # Check if the calendar exists
    if calendar not in calCog.calendars:
        return await ctx.send(":x: Unknown calendar")

    if mode in ("now", "n"):
        event = list(calCog.calendars[calendar].timeline.now())[0]
    elif mode in ("today", "t"):
        event = list(calCog.calendars[calendar].timeline.today())[0]
    else:
        event = list(calCog.calendars[calendar].timeline.today())[0]

    embed = tools.generate_event_embed(event, (0, len(students)), calCog.calendars_data[calendar])
    bot_message: discord.Message = await ctx.send(embed=embed)
    await bot_message.add_reaction(config.REACTION_EMOJI)

    calCog.reacted[calendar] = set()  # The users who reacted
    courses = tools.get_courses()
    logger.debug(f"Got {len(courses)} course(s): {', '.join([course['name'] for course in courses])}")

    def check(_reaction: discord.Reaction, _user: discord.User):
        return _reaction.message == bot_message and \
               str(_user.id) in students and \
               str(_reaction.emoji) == config.REACTION_EMOJI and \
               _user not in calCog.reacted[calendar]

    try:
        while len(calCog.reacted[calendar]) != len(students):
            reaction, user = await bot.wait_for('reaction_add', timeout=config.REACTION_TIMEOUT, check=check)
            bot.loop.create_task(calCog.check_in(user, courses, event, calendar, bot_message))
    except asyncio.TimeoutError:
        logger.info("Cancelled")
        embed = tools.generate_event_embed(event, (len(calCog.reacted[calendar]), len(students)), calCog.calendars_data[calendar], finished=True)
        await bot_message.edit(embed=embed)
        await bot_message.add_reaction(config.CANCELLED_EMOJI)
    else:
        pass


if __name__ == '__main__':
    args = tools.parse_args()
    logger = tools.get_logger(name="bot", level=args.log_level)
    students = tools.load_students(config.STUDENTS_FILE)
    calendars_config = tools.load_calendars_config(config.CALENDARS_CONFIG_FILE)
    calCog = CalendarCog(bot, students, calendars_config["calendars"], args.enable_check_in, logger=logger)
    bot.add_cog(calCog)
    bot.run(config.BOT_TOKEN)
