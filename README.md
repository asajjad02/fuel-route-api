# Fuel Stop Planner API

A Django REST API that takes a start and a finish in the USA and returns the cheapest places to buy fuel along the driving route, the total fuel cost, and a map. The vehicle has a 500-mile range and does 10 miles per gallon.

| Atlanta, GA → Phoenix, AZ | |
|---|---|
| Distance | 1,853.3 miles |
| Fuel | 185.33 gallons (miles ÷ 10) |
| Fuel stops | 7, six of them at their exact highway exit |
| Total cost | $535.84 |
| First request | about 1 second, one routing API call |
| Same trip again | about 10 ms, no API call |

## Quick start

Needs Python 3.12+ and a free [OpenRouteService](https://openrouteservice.org/dev/#/signup) API key.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then put your key in ORS_API_KEY
python manage.py migrate
python manage.py load_stations     # loads stations and towns from files in the repo, no network
python manage.py runserver
```

Then open http://127.0.0.1:8000/api/route/map/?start=Atlanta,+GA&finish=Phoenix,+AZ

Optional: `python manage.py test` (55 tests), `pip install ruff && ruff check .`, `python manage.py createsuperuser` to browse stations at `/admin/`.

| Setting in `.env` | Default | Purpose |
|---|---|---|
| `ORS_API_KEY` | required | OpenRouteService key |
| `DJANGO_DEBUG` | `0` | `1` for local development |
| `DJANGO_SECRET_KEY` | dev-only value | Set in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `REDIS_URL` | empty (in-memory cache) | Shared cache when running several workers |
| `API_THROTTLE_RATE` | `20/minute` | Requests per client |

## Using the API

### `POST /api/route/`

`start` and `finish` each take coordinates (`"40.7608,-111.8910"`), a town (`"Tulsa, OK"`) or a street address (`"1060 W Addison St, Chicago, IL"`).

```json
{ "start": "Atlanta, GA", "finish": "Phoenix, AZ" }
```

Response, shortened to one stop:

```json
{
  "start": [33.754, -84.39],
  "finish": [33.448, -112.074],
  "distance_miles": 1853.3,
  "total_gallons": 185.33,
  "total_cost": 535.84,
  "initial_gallons": 0.0,
  "initial_cost": 0.0,
  "fuel_stop_count": 7,
  "fuel_stops": [
    {
      "station": {
        "opis_id": 64683,
        "name": "QUIKTRIP #777",
        "address": "I-20, EXIT 49",
        "city": "Atlanta",
        "state": "GA",
        "latitude": 33.765215,
        "longitude": -84.521735,
        "location_source": "exit"
      },
      "mile": 9.0,
      "offset_miles": 0.5,
      "price_per_gallon": 2.972,
      "gallons": 3.7,
      "cost": 11.0
    }
  ],
  "map": { "type": "FeatureCollection", "features": ["…route line, start, finish and one point per stop…"] },
  "map_url": "http://127.0.0.1:8000/api/route/map/?start=Atlanta%2C+GA&finish=Phoenix%2C+AZ"
}
```

- `mile` is how far along the route the stop is; `offset_miles` is how far the station is from the road.
- `location_source` says how the station was placed: `exit` (its exact highway exit) or `town` (its town centre). See below.
- `initial_gallons` / `initial_cost` cover the drive to the first station, because the tank starts empty. They are included in the totals.

### `GET /api/route/map/?start=…&finish=…`

The same plan on an interactive map. Every JSON response links to it in `map_url`.

### Errors

| Status | When |
|---|---|
| 400 | Missing or blank field, unknown place, start and finish the same, or start or finish outside the USA |
| 422 | No road between the two, or a stretch over 500 miles with no station |
| 429 | Too many requests from one client |
| 502 | The routing service is down or rejects the key |
| 503 | The routing quota is used up (with a `Retry-After` header) |

"Outside the USA" is checked from the route itself: OpenRouteService tags each stretch of road with its country, so Windsor, Ontario is rejected even though it sits next to Detroit, while Detroit to Buffalo is allowed even though the shortest road runs through Canada.

### Postman

Import `postman_collection.json`: 16 requests with 70 checks, covering plans, caching, every error and the map page.

## Where the stations are

The price file has no coordinates, only an address column. Its addresses come in four shapes:

| Address shape | Stations | Example | Placed at |
|---|---|---|---|
| Highway and exit number | 3,720 (56%) | `I-44, EXIT 283 & US-69` | **That exit** on that highway |
| Two roads crossing | 1,491 (22%) | `US-281 & SR-29` | The town centre |
| One road | 1,397 (21%) | `US-30` | The town centre |
| Something else | 18 (0.3%) | `NJTP MM 5 SB`, street addresses | The town centre |

**Result:** 3,444 stations sit at their exact exit, 3,176 at their town centre, and 6 could not be placed (their town wasn't found in OpenStreetMap for that state and their address has no exit).

How exits are matched (`fuel/services/osm.py`):

1. The address is read into roads and an exit number (`fuel/services/addresses.py`): `I-45 & FM 1603, EXIT 238` means exit 238 on I-45.
2. OpenStreetMap marks every highway exit with its number and the highway it is on. The station goes to the exit with that number **on that highway**, nearest its town and within 30 miles (some towns sit well off the interstate).
3. If that interstate has no such exit, or the only one is far from the town, the CSV is treated as wrong and the station stays at its town centre rather than being guessed. For example, `I-35, EXIT 40` for Tonkawa, OK would be about 160 miles from Tonkawa.

A spot check of 12 random exit-placed stations found a real fuel station within 1 mile of every one, often of the same brand (Pilot at Minooka IL, Love's at Albuquerque NM, Kwik Trip at Sturtevant WI).

Because exit positions are exact, a station placed at an exit counts as on the route within 2 miles of the road; a town-centre position is rough, so it gets 5 miles.

The OpenStreetMap data is downloaded once by `python manage.py build_station_locations` and saved to `fuel/data/station_locations.csv` and `fuel/data/places.csv`, which are committed. Setup reads those files, so it never depends on an outside service. `places.csv` also lets a `"City, ST"` input resolve without an API call.

## How a request works

Following `POST /api/route/` through the code:

1. `views.py`: a serializer checks the input, then `plan_trip` does the work.
2. `services/trip.py`: `plan_trip` resolves both places, rounds them to about 100 m and looks for a saved trip. If there is none it runs the next steps and saves the result for a day.
3. `services/locations.py`: coordinates are parsed, a town is looked up in the database, and only a street address calls the geocoder.
4. `services/ors.py`: one call to OpenRouteService returns the road as a list of points and its length in miles.
5. `services/geo.py`: the road is resampled to one point per mile, each point's mile is the running total of [haversine](https://en.wikipedia.org/wiki/Haversine_formula) distances, and stations are kept if they are close enough to the road. A bounding-box query and a coarse pass on every 25th mile skip far-away stations first, so this takes about 20 ms even for a 1,850-mile trip.
6. `services/planner.py`: the greedy planner below picks the stops.
7. `serializers.py`: the result is shaped into JSON with a GeoJSON map.

## The fuel planner

At each station, the planner looks at every station it could reach on a full tank (500 miles). Every case, in `fuel/services/planner.py`:

| Case | What it does | Lines |
|---|---|---|
| No station in reach | The trip is impossible: 422 error | 61–63 |
| A station at least 5¢ cheaper is in reach | Buy just enough to reach the nearest one, skipping pricier stations on the way | 65–67 |
| Nothing cheaper is in reach | This is the best price for the next 500 miles: fill the tank and head to the cheapest station in reach | 68–72 |
| The tank already has fuel | Buy only what is missing, or nothing | 74–75 |
| The finish is in reach | The finish counts as a free station, so buy just enough to finish | 54 |

The tank starts empty, so the drive to the first station is charged at that station's price. Together these make the gallons always equal miles ÷ 10.

### Worked example

A 1,000-mile trip:

| Station | Mile | Price |
|---|---|---|
| A | 0 | $3.00 |
| B | 150 | $3.20 |
| C | 300 | $3.40 |
| D | 450 | $2.80 |
| E | 700 | $3.10 |

| At | Tank on arrival | Case | Buys | Cost |
|---|---|---|---|---|
| A | empty | D is cheaper and in reach: just enough to reach D, skipping B and C | 45 gal | $135.00 |
| D | empty | Nothing cheaper in reach, finish not in reach: fill up, head to E | 50 gal | $140.00 |
| E | 250 miles | Finish in reach: only the 5 gallons still missing | 5 gal | $15.50 |
| | | | **100 gal** | **$290.50** |

This example is a test (`test_readme_example_covers_every_case`).

### Minimum saving

Chasing every cent means tiny top-ups: buying a gallon or two just to reach a station a cent or two cheaper. So a station must be at least `MIN_PRICE_SAVING` cheaper (5 cents, in `fuel/constants.py`) to count as cheaper:

| Minimum saving | Atlanta → Phoenix | Salt Lake City → Kansas City |
|---|---|---|
| 0¢ (strictly cheapest) | 11 stops, $534.27 | 9 stops, $333.04 |
| **5¢ (default)** | **7 stops, $535.84** | **6 stops, $333.39** |
| 10¢ | 6 stops, $542.17 | 5 stops, $334.19 |

Only 0¢ is guaranteed cheapest; on Atlanta → Phoenix, 5¢ costs $1.57 more for four fewer stops.

The planner function is about 45 lines, has no Django code, and runs in O(n·k) for n stations and k stations per tank.

## Caching, quotas and scale

The only shared limit is the free OpenRouteService quota: 40 routes a minute and 2,000 a day; 1,000 geocodes a day and 3,000 a month.

- **Caching** (Django's cache; set `REDIS_URL` so every worker shares it): finished trips for a day, keyed on start and finish rounded to about 100 m; geocoded addresses for 30 days. `"City, ST"` and coordinates never call the API.
- **A local quota counter** checks every window before each call and answers 503 with `Retry-After` instead of calling OpenRouteService once a window is full.
- **Per-client throttling** (20 requests a minute by default) stops one client from using up everyone's quota.

Everything else runs in milliseconds and shares nothing between requests, so more workers means more capacity. Past the free tier, self-hosting the routing engine removes the quota.

## Assumptions

- The tank starts empty; the fuel to reach the first station is charged at that station's price.
- A station 2 or 5 miles off the road costs nothing extra to reach.
- When the CSV lists a station twice, the cheaper price is used.

## Code layout

```
fuel/
  views.py                 two thin views: JSON and map page
  serializers.py           input checks and response shape
  models.py                FuelStation, Place
  constants.py             every tunable value and pattern
  errors.py                errors, each with its HTTP status
  services/
    trip.py                runs the steps below and caches the result
    locations.py           start/finish text -> coordinates
    ors.py                 OpenRouteService client and quota guard
    geo.py                 which stations are on the route, and at what mile
    planner.py             the greedy fuel planner
    addresses.py           reads roads and exit numbers out of an address
    osm.py                 OpenStreetMap exits and towns (setup only)
  management/commands/
    build_station_locations.py   one-time OpenStreetMap build, output committed
    load_stations.py             loads prices, locations and towns into the database
  data/                    station_locations.csv, places.csv
  tests/
```

## Known limitations

- **Stations without an exit number sit at their town centre.** That is 48% of stations. In a large city they share one point, so on a trip that starts in that city they appear at mile 0. The next improvement uses OpenStreetMap road shapes the same way exits are used: crossing-road addresses (22%) placed where the two roads meet, and single-road addresses (21%) on that road nearest their town.
- **Six stations are not placed** (Texarkana TX, Dundee IL, Deerfield MO).
- **Cached trips keep their prices for up to a day** after `load_stations` is re-run.

## Data

- Fuel prices: the assessment's CSV.
- Exits and towns: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL).
- Routes and geocoding: [OpenRouteService](https://openrouteservice.org/).
- Map tiles: © OpenStreetMap contributors, drawn with Leaflet.
