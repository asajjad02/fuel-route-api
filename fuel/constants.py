"""Tunable values for data loading, routing, quotas and fuel planning."""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MINUTE = 60
DAY = 24 * 60 * MINUTE
# shortcut: a month is a fixed 30-day window, not a calendar month; align with ORS if needed.
MONTH = 30 * DAY

# Vehicle
MAX_RANGE_MILES = 500
MILES_PER_GALLON = 10

# Planning: a station must beat the current price by this much ($/gal) to be worth a detour stop.
# 0 gives the strictly cheapest plan, at the cost of many tiny top-ups.
MIN_PRICE_SAVING = 0.05

# Geometry
EARTH_RADIUS_MILES = 3958.8
MILES_PER_DEGREE_LAT = 69.0
ROUTE_SAMPLE_MILES = 1.0  # the route is resampled to one point per mile before matching
# How far from the route a station may be and still count as on it. A station placed at its
# highway exit is exact, so it gets a tight corridor; a town-centre position is rough.
EXIT_CORRIDOR_MILES = 2.0
TOWN_CORRIDOR_MILES = 5.0
COARSE_SAMPLE_STEP = 25  # every Nth sample, used to discard far-away stations cheaply
STATION_CHUNK_SIZE = 500  # bounds memory of the station x route-sample distance matrix


STATIONS_CSV_PATH = BASE_DIR / 'fuel-prices-for-be-assessment.csv'
STATION_LOCATIONS_CSV = BASE_DIR / 'fuel' / 'data' / 'station_locations.csv'
PLACES_CSV = BASE_DIR / 'fuel' / 'data' / 'places.csv'
OSM_CACHE_DIR = BASE_DIR / 'data' / 'osm'  # raw downloads, kept so a rerun skips them

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
OVERPASS_TIMEOUT_SECONDS = 600
OVERPASS_ATTEMPTS = 6  # the public server is often busy; waits grow 30 s, 60 s, ...
OVERPASS_RETRY_SECONDS = 30
OVERPASS_QUERY = """[out:json][timeout:{timeout}];
area["ISO3166-2"="US-{state}"]->.state;
way[highway~"^(motorway|trunk)$"][ref](area.state)->.highways;
.highways out body qt;
node(w.highways)[highway=motorway_junction][ref];
out qt;
node[place~"^({place_types})$"](area.state);
out qt;"""
US_STATES = (
    'AK AL AR AZ CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE '
    'NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY'
).split()

PLACE_RANKS = (
    'city',
    'town',
    'village',
    'hamlet',
    'suburb',
    'quarter',
    'neighbourhood',
    'locality',
)
PLACE_NAME_TAGS = ('name', 'short_name', 'alt_name', 'official_name')

PLACE_SUFFIX_RE = re.compile(r'\s+(CHARTER\s+)?(TOWNSHIP|BOROUGH)$', re.IGNORECASE)
PLACE_WORDS = {
    'ST': 'SAINT',
    'FT': 'FORT',
    'MT': 'MOUNT',
    'S': 'SOUTH',
    'N': 'NORTH',
    'E': 'EAST',
    'W': 'WEST',
}

EXIT_MAX_MILES = 30.0
EXIT_NUMBER_ONLY_MAX_MILES = 10.0
# When the town is unknown, an exit is trusted only if all its points (one per carriageway)
# lie this close together, i.e. the highway has just one exit with that number in the state.
EXIT_SPREAD_MILES = 2.0

# Station addresses, e.g. "I-44, EXIT 283 & US-69", "US-281 & SR-29", "SR-22/39".
# The same road pattern also reads OpenStreetMap road refs such as "I 44;US 69".
EXIT_RE = re.compile(r'\bEXIT\s*#?\s*(\d+)', re.IGNORECASE)
ROAD_RE = re.compile(
    r'\b(HIGHWAY|ROUTE|HWY|RTE|BUS|[A-Z]{1,2})\s*-?\s*(\d+)((?:[A-Z]*/\d+)*)', re.IGNORECASE
)
ROAD_KINDS = {'I': 'I', 'IH': 'I', 'US': 'US', 'CR': 'COUNTY', 'FM': 'FARM', 'RM': 'FARM'}
ANY_ROAD_KIND = 'ANY'  # "BUS-71" names a number but not the road family
NOT_ROAD_PREFIXES = {'MM', 'MP'}  # mile markers
STATE_ROAD_KIND = 'STATE'  # SR, ST, SH, HWY, "MN-15", ... all mean a state highway

# Location input parsing
LAT_LNG_RE = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$')
CITY_STATE_RE = re.compile(r'^\s*([^,]+?)\s*,\s*([A-Za-z]{2})\s*$')

# A cheap first check on coordinates; the route's country tags give the exact answer.
US_LAT_RANGE = (18.0, 72.0)
US_LON_RANGE = (-180.0, -66.0)

# OpenRouteService (free Standard plan)
ORS_BASE_URL = 'https://api.openrouteservice.org'
ORS_TIMEOUT_SECONDS = 20
ORS_USA_COUNTRY_ID = 214  # ORS's id for the USA in a route's "countryinfo" tags
# (max calls, window in seconds) per endpoint; enforced locally so we fail fast instead of a 429.
ORS_QUOTAS = {
    'directions': ((40, MINUTE), (2000, DAY)),
    'geocode': ((100, MINUTE), (1000, DAY), (3000, MONTH)),
}

# Caching
COORD_PRECISION = 3
TRIP_CACHE_TTL = DAY
GEOCODE_CACHE_TTL = MONTH

# Response
MAP_MAX_POINTS = 2000
