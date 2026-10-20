# Calendar routing

## Setup

Install Home Assistant's Waze Travel Time integration and confirm its
`waze_travel_time.get_travel_times` action exists. In vehicle options choose
**Calendars and routes**, select calendars, enable routing and choose a region.
Selecting calendars without routing does not produce route distances.

## Waze

Region identifiers remain `eu`, `us`, `na`, `il`, `au`; choose the region supported
by your Waze installation. Routes use metric distances and are not live navigation.
Locations are transmitted to Waze, not appointment titles or descriptions.

## Known locations

Home uses HA's configured home location. HA zones and explicit known-location aliases
can resolve calendar destinations. Map a label such as Office to a full address or
latitude,longitude under **Known locations**. Unknown venue names are not guessed.
Equivalent case/spacing can reuse a route; different house numbers are distinct.

## Appointment interpretation

Recognized physical appointments form a chronological home → destination → destination
→ home chain. Locationless/unrecognized and clearly virtual events are skipped; this
is not proof of no travel. Missing locations can be resolved with a zone or alias.
Malformed individual rows are counted and skipped; an invalid calendar response or
missing calendar is a retrieval failure.

All-day and overnight appointments cannot provide a reliable concrete itinerary.
Overlapping physical visits and impossible travel times keep the affected day
incomplete. Historical mileage remains available; only complete plans supply overlays.
A calendar cannot establish which vehicle was actually used.

## Nested appointments

**Ignore nested appointments** is off by default. It ignores appointments completely
contained within a longer valid physical appointment. Enable it only when those
sub-events represent the same visit, not separate journeys. Genuine separate journeys
can also be excluded. Partial overlaps and equal-duration events remain conflicts.

## Caching and progress

Successful directed Waze routes are cached per vehicle for seven days (512 entries).
Region and endpoint order matter. Failures never become zero-distance routes.
Bounded workers prioritize earlier days; completed days remain usable while pending
work resumes. Temporary failures have bounded retries, not an unlimited request loop.
Agenda verification normally runs every thirty minutes. Manual Sync requests a
bounded pass, not an entire forced recrawl.

## Restart restoration

Complete compatible distance overlays restore pending verification. Freshness is two
hours; provisional retention is up to 24 hours since verification. Failed verification
can retain labeled stale/provisional data within that limit. Authoritative cancellation
removes an overlay immediately; older/untrusted records fall back to history.
Restored numeric distances never supply trusted EV stop timing until reconstructed.

Mileage readiness and calendar completeness differ: `ready` does not guarantee that
all appointments were routed. Check `calendar_status`, pending/incomplete counts and
last-success/failure attributes. See [status troubleshooting](troubleshooting.md).

## Privacy

Waze receives route origins/destinations. Titles/descriptions are not persisted by
Mobility Forecast. Known locations, mileage and distances remain sensitive in HA
backups even where identifiers are hashed. Public charging consent is separate;
see [EV providers](ev-charging.md#providers-and-privacy).
