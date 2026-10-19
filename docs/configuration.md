# Native configuration walkthrough

Initial setup is unchanged: **Add your vehicle** → optional **Vehicle name**, required **Odometer sensor** → submit. Invalid sources show “Select a numeric cumulative vehicle odometer with km or mi units, not a range or trip sensor.” Calendars/routing are never required here.

**Configure → Vehicle settings** has three menu choices:
- **Vehicle**: edit **Vehicle name**, submit.
- **Calendars**: multi-select **Calendars**, optional **Use Waze for routes**, submit. With routing off this completes immediately. With routing on, a second **Waze region** screen asks **Region**, with any previous selection retained. A missing provider shows “Install Waze Travel Time before enabling routes.” The calendar form explains that locations go to an external service, not event titles.
- **Known locations**: optional exception management. **Add location** asks **Location name in calendar** and **Address or coordinates**. **Edit location** selects an existing name then displays the same editable fields. **Remove location** selects one existing name and submits. There is no JSON/object editor. Invalid addresses show “Enter a full address with street number and city, or valid coordinates.” Duplicate names direct the user to Edit location. Existing mappings from the original release remain compatible.

**Reconfigure** changes the mandatory source. History stays stored, source continuity is checked before accepting replacement data. Unknown or incompatible sources are not silently merged. Removing calendars or changing settings never deletes history. Vehicle removal deletes only Mobility Forecast-owned state.

Dutch translations provide matching menus, fields, privacy notices and errors. Normal users never configure statistical thresholds, cache timers or model weights.
