# Variables
import config

import json
import colorlog
import discord
from ics import Event
import requests
from logging import Logger
import typing


def load_students(file: str) -> dict:
    try:
        with open(file, "r", encoding="utf-8") as fd:
            s = json.load(fd)
        return s
    except (IOError, json.JSONDecodeError):
        return dict()


def get_student(_id: int, students: dict) -> typing.Union[list, None]:
    return students.get(str(_id), None)


def generate_event_embed(event: Event, check_in_number: typing.Tuple[int, int]) -> discord.Embed:
    """

    :param event:
    :param check_in_number:
    :return:
    """
    embed = discord.Embed(title=event.name,
                          description=config.EMBED_DESCRIPTION,
                          color=config.EMBED_COLOR)
    embed.set_thumbnail(url=config.EMBED_THUMBNAIL)
    embed.add_field(name="Heure", value=f"De {event.begin.to(config.TIMEZONE).strftime('%Hh%M')}"
                                        f" à {event.end.to(config.TIMEZONE).strftime('%Hh%M')}", inline=True)
    embed.add_field(name="Salle", value=event.location, inline=True)
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
