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
from arrow import now

from typing import List, Dict


class CalendarCog(commands.Cog):
    def __init__(self, bot: commands.Bot, students: dict, calendars: List[Dict], check_in: bool = False, logger: logging.Logger = logging.getLogger("Calendar")):
        """

        :param bot: The bot
        :param students: The dictionary mapping the students' discord IDs to their identities
        :param calendars: The list of the configuration of all calendars
        :param check_in: Whether or not to enable check-ins
        :param logger: An optional logger
        """
        self.bot = bot
        self.reacted: dict[str, set] = {cal["id"]: set() for cal in calendars}
        self.calendar_lock = asyncio.Lock()
        self.data_lock = asyncio.Lock()

        self.students = students

        # self.calendars_data = calendars
        self.calendars_data = {cal["id"]: cal for cal in calendars}
        # Dict of empty calendars for now, mapped by their id in the config file
        self.calendars: dict[str, Calendar] = {cal["id"]: Calendar() for cal in calendars}

        self.enable_check_ins = check_in
        self.logger = logger

        self.last_statuses: dict[str, bool] = {cal["id"]: False for cal in calendars}

        # calendar_id : event_id
        self.last_events: dict[str, str] = {cal["id"]: None for cal in calendars}
        self.load_data()

    def start_loops(self):
        self.update_calendars.start()
        self.check_events.start()

    @tasks.loop(seconds=config.CALENDAR_UPDATE_INTERVAL)
    async def update_calendars(self) -> None:
        """
        The loop that triggers the calendars updates
        :return: None
        """
        self.last_statuses = await self._update_calendars()

    @tasks.loop(seconds=config.EVENT_CHECK_INTERVAL)
    async def check_events(self) -> None:
        """
        The loop that checks if a new event is happening
        :return: None
        """
        for cal_id in self.calendars:
            event = await self.get_last_event(cal_id)
            if event and event.uid != self.last_events[cal_id]:
                # There is a new event
                self.logger.info(f"New event found for calendar {cal_id}")
                await self.send_event(cal_id, event)

    @commands.command()
    async def update(self, ctx: commands.Context) -> None:
        """
        The user command to update the calendars
        :param ctx: The context
        :return: None
        """
        self.last_statuses = await self._update_calendars()
        message = ":bell: **Update status:**\n"
        for _id, status in self.last_statuses.items():
            message += ":white_check_mark: " if status else ":x: "
            message += _id
            message += "\n"
        await ctx.send(message)

    async def send_event(self, calendar_id: str, event: Event):
        """
        Sends the event from the specified calendar to the corresponding channel and mention if enabled
        :param calendar_id: The id of the calendar the event is part of
        :param event: The calendar event
        :return:
        """
        # Update the last event
        self.last_events[calendar_id] = event.uid
        async with self.data_lock:
            data_file = tools.get_calendar_data_filename(calendar_id)
            with open(data_file, "w") as fd:
                json.dump(self.gen_data(calendar_id), fd)

        cal_data = self.calendars_data[calendar_id]

        # Getting the channel to send the event to
        channel: discord.TextChannel = self.bot.get_channel(config.CHANNEL_ID)
        self.logger.debug(f"Got channel: {channel.name}")

        # Getting the role to mention if enabled in the config
        role: typing.Union[discord.Role, None] = None
        if config.ROLE_MENTION_ENABLE:
            role = channel.guild.get_role(config.ROLE_MENTION)

        # Generating the base embed
        embed = tools.generate_event_embed(event, (0, len(self.students)))
        content = role.mention if role else ""
        bot_message: discord.Message = await channel.send(content=content, embed=embed)

        if self.enable_check_ins:
            await bot_message.add_reaction(config.REACTION_EMOJI)

        self.reacted[calendar_id] = set()  # The users who reacted
        courses = tools.get_courses()
        self.logger.debug(f"Got {len(courses)} course(s): {', '.join([course['name'] for course in courses])}")
        # Only check-in for the current courses (hopefully there's only one)
        courses = tools.filter_current_courses(event, courses)
        self.logger.debug(f"Filtered courses, remaining course(s): {', '.join([course['name'] for course in courses])}")

        def check(_reaction: discord.Reaction, _user: discord.User):
            return _reaction.message == bot_message and \
                   str(_user.id) in self.students and \
                   str(_reaction.emoji) == config.REACTION_EMOJI and \
                   _user not in self.reacted

        try:
            while len(self.reacted[calendar_id]) != len(self.students):
                timeout = event.end.shift(minutes=+15) - now(config.TIMEZONE)
                timeout = timeout.seconds
                timeout = timeout if timeout > 1 else 1
                reaction, user = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)
                if self.enable_check_ins:
                    self.bot.loop.create_task(self.check_in(user, courses, event, calendar_id, bot_message, content))

        except asyncio.TimeoutError:
            embed = tools.generate_event_embed(event, (len(self.reacted), len(self.students)), finished=True)
            await bot_message.edit(content=content, embed=embed)
            await bot_message.add_reaction(config.CANCELLED_EMOJI)
        else:
            pass

    async def check_in(self,
                       user: discord.User,
                       courses: typing.List[dict],
                       event: Event,
                       bot_message: discord.Message,
                       bot_message_content: str = ""):
        """

        :param user:
        :param courses:
        :param event:
        :param bot_message:
        :param bot_message_content:
        :return:
        """
        student = tools.get_student(user.id, self.students)
        username, last_name, first_name = student
        self.logger.debug(f"{first_name} {last_name} reacted")
        for course in courses:
            status = tools.check_in(username, course["id"], self.logger)
            if status:
                self.reacted[calendar_id].add(user)
            await self.send_check_in_status(status, course, user)
            await asyncio.sleep(1)
        _embed = tools.generate_event_embed(event, (len(self.reacted), len(self.students)))
        await bot_message.edit(content=bot_message_content, embed=_embed)

    async def send_check_in_status(self, status: bool, course: dict, user: discord.User) -> bool:
        if status:
            self.logger.debug(f"Successfully checked-in {user.display_name} for course {course['name']}")
            try:
                await user.send(f":white_check_mark: Pointage pour le cours de {course['name']} "
                                f"de {course['start']} à {course['end']} réussi !")
            except discord.errors.Forbidden:  # User's DMs are closed
                self.logger.debug(f"Couldn't send status DM to {user.display_name}")
        else:
            self.logger.error(f"Error checking-in {user.display_name} for course {course['name']}")
            try:
                await user.send(f":x: Erreur lors du pointage pour le cours de {course['name']} de {course['start']} à {course['end']}.")
            except discord.errors.Forbidden:  # User's DMs are closed
                self.logger.debug(f"Couldn't send status DM to {user.display_name}")
        return status

    async def get_last_event(self, calendar_id: str) -> typing.Union[Event, None]:
        """
        Gets the last event of the specified calendar
        :param calendar_id: The id of the calendar for which to get the last event
        :return: The current new event for the specified calendar, None if already set or if there is none
        """
        async with self.calendar_lock:
            # Get all the events currently happening
            events = list(self.calendars[calendar_id].timeline.now())
        if not events:
            return
        # If the last event is already is already correctly set (doesn't handle overlapping of two or more events)
        if self.last_events[calendar_id] in [e.uid for e in events]:
            return None
        return events[0]

    def gen_data(self, calendar_id: str) -> dict:
        """
        Generate the dict (and thus JSON) that will store the state of a particular calendar
        :param calendar_id: The id of the calendar for which to generate the data
        :return:
        """
        return {
            "last_event": self.last_events[calendar_id]
        }

    def load_data(self) -> None:
        """
        Loads the last events for all calendars from their data files, if they don't exist, set en empty string as the event
        :return:
        """
        for cal_id in self.calendars_data:
            cal_data_file = tools.get_calendar_data_filename(cal_id)
            try:
                with open(cal_data_file) as fd:
                    j: dict = json.load(fd)
                    self.last_events[cal_id] = j.get("last_event", "")
            except (IOError, json.JSONDecodeError):
                self.last_events[cal_id] = ""

    async def _load_calendars(self) -> None:
        """
        Loads all the calendars from their files, if they are not available, load an empty calendar
        :return:
        """
        for cal_id in self.calendars_data:
            cal_file = tools.get_calendar_filename(cal_id)
            try:
                with self.calendar_lock:
                    with open(cal_file, "r", encoding="utf-8") as fd:
                        self.calendars[cal_id] = Calendar(fd.read())
            except IOError:
                self.calendars[cal_id] = Calendar()

    async def _update_calendars(self) -> dict[str, bool]:
        """
        Update all the calendars and return whether or not they were successfully updated
        :return:
        """
        statuses = dict()

        for cal_id in self.calendars_data:
            cal_url = self.calendars_data[cal_id]["url"]
            cal_filename = tools.get_calendar_filename(cal_id)
            try:
                r = requests.get(cal_url, headers=config.CALENDAR_HEADERS)
                r.raise_for_status()
                async with self.calendar_lock:
                    with open(cal_filename, "w", encoding="utf-8") as f:
                        f.write(r.text)
                    self.calendars[cal_id] = Calendar(r.text)
                if self.logger:
                    self.logger.info(f"Calendar {cal_id} updated")
                statuses[cal_id] = True

            except requests.HTTPError as e:
                print(e)
                if self.logger:
                    self.logger.error(f"ERROR: Could not update the calendar {cal_id}")
                statuses[cal_id] = False

        return statuses
