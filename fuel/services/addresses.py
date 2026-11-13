"""Read the roads and exit number out of a station address like "I-44, EXIT 283 & US-69"."""

import re
import unicodedata
from dataclasses import dataclass

from fuel.constants import (
    ANY_ROAD_KIND,
    EXIT_RE,
    NOT_ROAD_PREFIXES,
    PLACE_WORDS,
    ROAD_KINDS,
    ROAD_RE,
    STATE_ROAD_KIND,
)


@dataclass(frozen=True)
class Road:
    kind: str  # 'I', 'US', 'STATE', 'COUNTY', 'FARM' or 'ANY'
    number: str

    def matches(self, other):
        kinds_agree = ANY_ROAD_KIND in (self.kind, other.kind) or self.kind == other.kind
        return self.number == other.number and kinds_agree


@dataclass(frozen=True)
class Address:
    roads: tuple
    exit_number: str | None = None
    exit_road: Road | None = None  # the highway the exit is on


def place_key(name):
    """Comparable town name: "S Coffeyville" and "South Coffeyville" -> SOUTHCOFFEYVILLE."""
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()  # Cañon
    words = re.sub(r'[^A-Z0-9 ]', ' ', ascii_name.upper().replace("'", '')).split()
    return ''.join(PLACE_WORDS.get(word, word) for word in words)


def parse_roads(text):
    """Every road named in `text`, e.g. "SR-22/39" -> (STATE 22, STATE 39)."""
    roads = []
    for match in ROAD_RE.finditer(text):
        prefix = match[1].upper()
        if prefix in NOT_ROAD_PREFIXES:
            continue
        kind = ANY_ROAD_KIND if prefix == 'BUS' else ROAD_KINDS.get(prefix, STATE_ROAD_KIND)
        numbers = [match[2], *re.findall(r'\d+', match[3])]
        roads += [Road(kind, number.lstrip('0') or '0') for number in numbers]
    return tuple(dict.fromkeys(roads))


def parse_address(text):
    exit_match = EXIT_RE.search(text)
    if not exit_match:
        return Address(parse_roads(text))
    # The exit is on a road named before it, an interstate if there is one:
    # "I-45 & FM 1603, EXIT 238" -> I-45.
    roads_before = parse_roads(text[: exit_match.start()])
    interstates = [road for road in roads_before if road.kind == 'I']
    return Address(
        roads=parse_roads(text),
        exit_number=exit_match[1].lstrip('0') or '0',
        exit_road=(interstates or roads_before or [None])[0],
    )
