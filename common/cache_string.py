import json
import logging

cached_strings = {}
logger = logging.getLogger(__name__)


def refresh_cache_strings():
    print("Refreshing...")
    global cached_strings
    with open("common/constants.json") as f:
        cached_strings = json.load(f)


def gettext(name):
    if message := cached_strings.get(name):
        return message
    else:
        logger.info(f"Message key not found for '{name}'")
        return None


refresh_cache_strings()
