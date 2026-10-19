# Configuration

Initial setup requires only an odometer, optionally a vehicle name. Configure each vehicle separately. Sources must be numeric lifetime mileage in km or mi, not battery range or daily trip distance.

Options rename the vehicle, select multiple calendars, opt into Waze and select its region. Region defaults displayed in the form must be checked by the user; routing is disabled by default. Known locations accepts a mapping from aliases to full addresses (street number plus locality) or latitude,longitude. HA zone names and entity IDs resolve locally.

Reconfigure changes the source while preserving history. Continuity is checked before accepting a different source. Discontinuous counters require correcting the upstream sensor or deliberately starting a new vehicle entry. Statistical constants and polling/cache details are not configurable.

Removing calendars, disabling routing and renaming never delete driving history. Removing the vehicle deletes its own persisted data only.
