# Variables
import config

import json
import colorlog
import discord
from ics import Event
import requests
from logging import Logger
import typing
import argparse
from os.path import join


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="""
    A Discord bot allowing students to check-in to their classes directly from Discord
    """)
    parser.add_argument("--log-level",
                        default="INFO",
                        type=str,
                        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                        help="the logging verbosity level")
    parser.add_argument("--enable-check-in",
                        action="store_true",
                        nargs="?",
                        help="to enable check-ins")
    args = parser.parse_args()
    return args


def load_students(file: str) -> dict:
    try:
        with open(file, "r", encoding="utf-8") as fd:
            s = json.load(fd)
        return s
    except (IOError, json.JSONDecodeError):
        return dict()


def load_calendars_config(file: str) -> dict:
    try:
        with open(file, "r", encoding="utf-8") as fd:
            s = json.load(fd)
        return s
    except (IOError, json.JSONDecodeError):
        return dict()


def get_student(_id: int, students: dict) -> typing.Union[list, None]:
    return students.get(str(_id), None)


def get_calendar_filename(calendar_id: str) -> str:
    return join(config.CALENDARS_FOLDER, calendar_id + ".ics")


def get_calendar_data_filename(calendar_id: str) -> str:
    return join(config.CALENDARS_FOLDER, calendar_id + ".data.json")


def generate_event_embed(event: Event,
                         check_in_number: typing.Tuple[int, int],
                         calendar_data: dict,
                         finished: bool = False) -> discord.Embed:
    """

    :param event: The event to generate the embed for
    :param check_in_number: A tuple with two elements, the number of check-ins, and the total number of users of the calendar
    :param calendar_data: The data for the calendar
    :param finished: Whether or not the event is finished
    :return: The generated Embed object
    """
    description = config.EMBED_EVENT_DESCRIPTION if not finished else config.EMBED_EVENT_FINISHED_DESCRIPTION
    name = event.name if event.name else "Unknow course"
    location = event.location if event.location else "Unknown location"
    embed = discord.Embed(title=name,
                          description=description,
                          color=calendar_data["embed"]["color"])
    embed.set_thumbnail(url=calendar_data["embed"]["thumbnail"])
    embed.add_field(name="Heure", value=f"De {event.begin.to(config.TIMEZONE).strftime('%Hh%M')}"
                                        f" à {event.end.to(config.TIMEZONE).strftime('%Hh%M')}", inline=True)
    embed.add_field(name="Salle", value=location, inline=True)
    embed.add_field(name="Pointage", value=f"{check_in_number[0]}/{check_in_number[1]}", inline=True)
    embed.set_footer(text="Ensi-pointing par Rom", icon_url="https://camo.githubusercontent.com/"
                                                            "8bcee5987a3ce80d2d466bb1cbe5b5c18b6450f84036d98ef37"
                                                            "854eb120d5601/68747470733a2f2f66696c65732e636174626f"
                                                            "782e6d6f652f71753731656d2e6a7067")
    return embed


def get_courses() -> list:
    try:
        r = requests.get(config.API_COURSES_ENDPOINT)
        r.raise_for_status()
        j = r.json()
        s = j.get("success", False)
        if s:
            return j["courses"]
    except (requests.HTTPError, json.JSONDecodeError):
        pass
    return list()


def filter_current_courses(event: Event, courses: list) -> list:
    current_courses = list()
    for course in courses:
        evt_start = event.begin.to("Europe/Paris").strftime("%H:%M")
        evt_end = event.end.to("Europe/Paris").strftime("%H:%M")
        if course["start"] == evt_start and course["end"] == evt_end:
            current_courses.append(course)
    return current_courses


def check_in(username: str, course_id: int, logger: Logger) -> bool:
    payload = {
        "courseID": str(course_id),
        "username": username
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(config.API_CHECK_IN_ENDPOINT, headers=headers, data=json.dumps(payload))
        logger.debug(f"POST to check_in, status code: {r.status_code}")
        logger.debug(r.text)
        r.raise_for_status()
        j: dict = r.json()
        s = j.get("success", False)
        return s
    except (requests.HTTPError, json.JSONDecodeError):
        pass
    return False


def get_logger(name: str = str(), level: str = "ERROR") -> Logger:
    _handler = colorlog.StreamHandler()
    _handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(levelname)s:%(asctime)s: %(message)s',
        datefmt="%H:%M:%S"))

    logger = colorlog.getLogger(name)
    logger.addHandler(_handler)
    logger.setLevel(level)
    return logger
