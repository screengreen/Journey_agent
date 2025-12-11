"""Парсеры для веб-сайтов с событиями."""

from src.parsers.websites.afisha import AfishaParser
from src.parsers.websites.eventbrite import EventbriteParser
from src.parsers.websites.timepad import TimepadParser

__all__ = ["AfishaParser", "EventbriteParser", "TimepadParser"]


