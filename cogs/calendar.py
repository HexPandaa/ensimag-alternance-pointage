# Variables
import config

# Custom modules
import tools

import discord
from discord.ext import tasks, commands
import asyncio
import requests
from ics import Calendar, Event
import json
import typing
import logging


class CalendarCog(commands.Cog):
    def __init__(self, bot: commands.Bot, students: dict, logger: logging.Logger = logging.getLogger("Calendar")):
        """

        :param bot: The bot
        :param students: The dictionary mapping the students' discord IDs to their identities
        :param logger: An optional logger
        """
        self.bot = bot
        self.reacted = set()
        self.calendar_lock = asyncio.Lock()
        self.data_lock = asyncio.Lock()

        self.students = students

        self.calendar = Calendar()

        self.logger = logger
        self.last_status = False

        self.last_event = None
        self.load_data()

    def start_loops(self):
        self.update_calendar.start()
        self.check_event.start()

    @tasks.loop(seconds=config.CALENDAR_UPDATE_INTERVAL)
    async def update_calendar(self) -> None:
        """
        The loop that triggers the calendar updates
        :return: None
        """
        self.last_status = await self._update_calendar()

    @tasks.loop(seconds=config.EVENT_CHECK_INTERVAL)
    async def check_event(self) -> None:
        """
        The loop that checks if a new event is happening
        :return: None
        """
        event = await self.get_last_event()
        if event and event.uid != self.last_event:
            # There is a new event
            self.logger.info("New event found")
            await self.send_event(event)
            self.last_event = event.uid
            async with self.data_lock:
                with open(config.DATA_FILE, "w") as fd:
                    json.dump(self.gen_data(), fd)

    @commands.command()
    async def update(self, ctx: commands.Context) -> None:
        """
        The user command to update the calendar
        :param ctx: The context
        :return: None
        """
        self.last_status = self._update_calendar()
        if self.last_status:
            await ctx.send(":white_check_mark: Successfully updated.")
        else:
            await ctx.send(":x: Successfully updated.")

    async def send_event(self, event: Event):
        """

        :param event:
        :return:
        """
        channel = self.bot.get_channel(config.CHANNEL_ID)
        self.logger.debug("Got channel:", channel)
        embed = tools.generate_event_embed(event, (0, len(self.students)))
        bot_message: discord.Message = await channel.send(embed=embed)

        await bot_message.add_reaction(config.REACTION_EMOJI)

        self.reacted = set()  # The users who reacted
        courses = tools.get_courses()
        self.logger.debug(f"Got {len(courses)} course(s): {', '.join([course['name'] for course in courses])}")

        def check(_reaction: discord.Reaction, _user: discord.User):
            return _reaction.message == bot_message and \
                   str(_user.id) in self.students and \
                   str(_reaction.emoji) == config.REACTION_EMOJI

        try:
            while len(self.reacted) != len(self.students):
                reaction, user = await self.bot.wait_for('reaction_add', timeout=config.REACTION_TIMEOUT, check=check)
                task = self.bot.loop.create_task(self.check_in(user, courses, event, bot_message))

        except asyncio.TimeoutError:
            await bot_message.add_reaction(config.CANCELLED_EMOJI)
        else:
            pass

    async def check_in(self,
                       user: discord.User,
                       courses: typing.List[dict],
                       event: Event,
                       bot_message: discord.Message):
        """

        :param user:
        :param courses:
        :param event:
        :param bot_message:
        :return:
        """
        student = tools.get_student(user.id, self.students)
        username, last_name, first_name = student
        self.logger.debug(f"{first_name} {last_name} reacted")
        for course in courses:
            status = tools.check_in(username, course["id"], self.logger)
            if status:
                self.reacted.add(user)
            await self.send_check_in_status(status, course, user)
            await asyncio.sleep(1)
        _embed = tools.generate_event_embed(event, (len(self.reacted), len(self.students)))
        await bot_message.edit(embed=_embed)

    async def send_check_in_status(self, status: bool, course: dict, user: discord.User) -> bool:
        if status:
            await user.send(f":white_check_mark: Pointage pour le cours de {course['name']} réussi !")
            self.logger.debug(f"Successfully checked-in {user.display_name} for course {course['name']}")
        else:
            await user.send(f":x: Erreur lors du pointage pour le cours de {course['name']}.")
            self.logger.error(f"Error checking-in {user.display_name} for course {course['name']}")
        return status

    async def get_last_event(self) -> typing.Union[Event, None]:
        """

        :return:
        """
        async with self.calendar_lock:
            events = list(self.calendar.timeline.now())
        if not events:
            return
        if self.last_event in [e.uid for e in events]:
            return None
        return events[0]

    def gen_data(self) -> dict:
        """

        :return:
        """
        return {
            "last_event": self.last_event
        }

    def load_data(self) -> None:
        """

        :return:
        """
        try:
            with open(config.DATA_FILE) as fd:
                j: dict = json.load(fd)
                self.last_event = j.get("last_event", "")
        except (IOError, json.JSONDecodeError):
            self.last_event = ""

    async def _load_calendar(self) -> None:
        """

        :return:
        """
        try:
            with self.calendar_lock:
                with open(config.CALENDAR_FILE, "r", encoding="utf-8") as fd:
                    self.calendar = Calendar(fd.read())
        except IOError:
            self.calendar = Calendar()

    async def _update_calendar(self) -> bool:
        """

        :return:
        """
        try:
            r = requests.get(config.CALENDAR_URL, headers=config.CALENDAR_HEADERS)
            r.raise_for_status()
            async with self.calendar_lock:
                with open(config.CALENDAR_FILE, "w", encoding="utf-8") as f:
                    f.write(r.text)
                self.calendar = Calendar(r.text)
            if self.logger:
                self.logger.info("Calendar updated")
            return True

        except requests.HTTPError as e:
            print(e)
            if self.logger:
                self.logger.error(f"ERROR: Could not update the calendar")
            return False
