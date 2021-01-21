# Bot
BOT_TOKEN = "token_goes_here"
BOT_ADMINS = (
    000000000000000000,  # Someone
    111111111111111111   # Someone else
)

# Events
CHANNEL_ID = 000000000000000000
REACTION_EMOJI = "📌"
CANCELLED_EMOJI = "❌"
REACTION_TIMEOUT = 30 * 60  # 30 minutes

# Calendar
CALENDAR_URL = "https://domain.tld/calendar.ics"
CALENDAR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/87.0.4280.141 Safari/537.36",
    "Content-Type": "application/json"
}

TIMEZONE = "Europe/Paris"
EVENT_CHECK_INTERVAL = 2 * 60  # 2 minutes
CALENDAR_UPDATE_INTERVAL = 12 * 60 * 60  # 12 hours

# API
API_BASE_URL = "https://api.tld/api/"
API_COURSES_ENDPOINT = API_BASE_URL + "courses"
API_CHECK_IN_ENDPOINT = API_BASE_URL + "check-in"

# Files
STUDENTS_FILE = "./students.json"
CALENDAR_FILE = "./calendar.ics"
DATA_FILE = "./data.json"

# Embed
ROLE_MENTION = 000000000000000000
ROLE_MENTION_ENABLE = True
EMBED_EVENT_DESCRIPTION = "N'oubliez pas de pointer [ici](http://domain.tld/path) !\n" \
                    "Ou réagissez avec l'émoji 📌"
EMBED_EVENT_FINISHED_DESCRIPTION = ":x: Le cours est terminé, il n'est plus possible de pointer"
EMBED_COLOR = 0x0079d6
EMBED_THUMBNAIL = "https://domain.tld/image.png"
