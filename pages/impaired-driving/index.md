---
title: Impaired Driving Enforcement (BETA)
queries:
   - last_record: last_record.sql
sidebar_link: false
---

<!--
  Data prerequisites (register both in a `dui` source, like hexgrid.crash_hexgrid):
    dui.hex_static      <- dui_hex_static.parquet
                           GRID_ID, ward, est_kde, est_kde_norm, n_estab_400m,
                           dui_arrests (2021-2025, validation only),
                           hx, hy (State Plane meters), hex_lat, hex_lon
    dui.establishments  <- establishments_weighted.parquet
                           one row per active on-premise alcohol license, with
                           TYPE, nightlife_flag, weight, XCOORD/YCOORD, LATITUDE/LONGITUDE
  Component: components/SelectableTable.svelte needs the `itemLabel` prop
  (backward compatible; defaults to 'intersections').

  Priority index (all knobs live in the dui_hex query):
    Three factors, each scaled 0 to 1 against the top hex:
      crash    = injury points (Fatal 10 / Major 5 / Minor 1 per injured person)
                 in the selected dates and time window
      venues   = distance-decayed weight of late-hour on-premise alcohol venues
                 within 400m (precomputed, static)
      impaired = injury points in crashes where MPD reported an impaired driver
                 (DRIVERSIMPAIRED > 0), all hours, fixed 5-year lookback ending at
                 the latest record (too rare to rank on in a short date range)
    Combined with a weighted geometric mean (0.5 / 0.3 / 0.2) and a 0.1 floor,
    rescaled so the top hex = 100. Multiplying rewards hexes that score on
    several factors; the floor keeps single-factor hexes on the list.

  Selection wiring (mirrors pages/intersections):
    map click   -> inputs.hex_select.GRID_ID -> narrows hex_base (the table's data)
    table click -> inputs.hex_pick (WHERE fragment) -> hex_filtered -> selected_hex
    selected_hex has exactly one row when one hex is in scope -> detail map shows
-->

```sql date_bounds
-- Earliest selectable date and the default start: five years before the latest record.
-- Returned as a 'YYYY-MM-DD' string: DateRange accepts only that format (or a Date
-- object) and silently falls back to today for anything else.
-- The end date comes from the shared queries/last_record.sql, like the other pages.
SELECT strftime(MAX(LAST_RECORD)::DATE - INTERVAL 5 YEAR, '%Y-%m-%d') AS start_5y
FROM crashes.crashes
```

```sql unique_severity
SELECT SEVERITY FROM crashes.crashes GROUP BY 1
```

```sql unique_hin
SELECT GIS_ID, ROUTENAME FROM hin.hin GROUP BY ALL
```

```sql sev_label
SELECT
  CASE
    WHEN COUNT(DISTINCT SEVERITY) = 0 THEN ' '
    WHEN BOOL_AND(SEVERITY = 'Fatal') THEN 'Fatalities'
    WHEN COUNT(DISTINCT SEVERITY) = 1 THEN
        MAX(CASE SEVERITY WHEN 'Major' THEN 'Major Injuries'
                          WHEN 'Minor' THEN 'Minor Injuries' END)
    WHEN BOOL_AND(SEVERITY IN ('Major','Fatal')) AND COUNT(DISTINCT SEVERITY) = 2
        THEN 'Major Injuries and Fatalities'
    ELSE 'Injuries and Fatalities'
  END AS label
FROM crashes.crashes
WHERE SEVERITY IN ${inputs.multi_severity.value}
```

```sql window_label
SELECT CASE '${inputs.window_preset.value}'
    WHEN 'all_hours'    THEN 'All hours'
    WHEN 'late_weekend' THEN 'Weekend late night'
    ELSE 'Late night'
END AS label
```

```sql selected_date_range
WITH report_date_range AS (
    SELECT
      CASE
        WHEN '${inputs.date_range.end}'::DATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
date_info AS (
    SELECT
      CASE
        WHEN start_date = DATE_TRUNC('year', start_date)
         AND end_date   = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
        THEN EXTRACT(YEAR FROM start_date)::VARCHAR
        WHEN start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
        THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
        ELSE strftime(start_date, '%m/%d/%y') || '-' || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS current_period_range
    FROM report_date_range
)
SELECT current_period_range FROM date_info
```

```sql dui_hex
-- Every hex, scored. Feeds the main map. Responds to dates, severity, time window.
WITH crash AS (
    -- Factor 1: late-night injuries (selected dates and time window)
    SELECT
        GRID_ID,
        SUM("COUNT") AS crash_people,
        SUM(CASE SEVERITY WHEN 'Fatal' THEN 10 WHEN 'Major' THEN 5 WHEN 'Minor' THEN 1 ELSE 0 END
            * "COUNT") AS crash_pts
    FROM crashes.crashes
    WHERE SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                         AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
      AND (
        CASE
            WHEN '${inputs.window_preset.value}' = 'all_hours' THEN TRUE
            WHEN '${inputs.window_preset.value}' = 'late_weekend' THEN
                 (DATE_PART('hour', REPORTDATE) IN (22, 23) AND DATE_PART('dow', REPORTDATE) IN (4, 5, 6))
              OR (DATE_PART('hour', REPORTDATE) IN (0, 1, 2, 3) AND DATE_PART('dow', REPORTDATE) IN (5, 6, 0))
            ELSE DATE_PART('hour', REPORTDATE) IN (22, 23, 0, 1, 2, 3)
        END
      )
    GROUP BY GRID_ID
),
impaired AS (
    -- Factor 3: injuries in crashes with an impaired driver (past 5 years, any hour)
    SELECT
        GRID_ID,
        SUM("COUNT") AS imp_people,
        SUM(CASE SEVERITY WHEN 'Fatal' THEN 10 WHEN 'Major' THEN 5 WHEN 'Minor' THEN 1 ELSE 0 END
            * "COUNT") AS imp_pts
    FROM crashes.crashes
    WHERE SEVERITY IN ${inputs.multi_severity.value}
      AND COALESCE(DRIVERSIMPAIRED, 0) > 0
      AND REPORTDATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE - INTERVAL 5 YEAR
    GROUP BY GRID_ID
),
factors AS (
    SELECT
        h.GRID_ID,
        h.ward,
        COALESCE(h.n_estab_400m, 0) AS n_estab,
        COALESCE(h.dui_arrests, 0)  AS dui_arrests,   -- validation only, not in Priority
        COALESCE(c.crash_people, 0) AS crash_people,
        COALESCE(c.crash_pts, 0)    AS crash_pts,
        COALESCE(i.imp_people, 0)   AS imp_people,
        COALESCE(i.imp_pts, 0)      AS imp_pts,
        COALESCE(c.crash_pts / NULLIF(MAX(c.crash_pts) OVER (), 0), 0) AS crash_f,
        COALESCE(h.est_kde_norm, 0)                                    AS venue_f,  -- Factor 2
        COALESCE(i.imp_pts / NULLIF(MAX(i.imp_pts) OVER (), 0), 0)     AS imp_f
    FROM dui.hex_static h
    LEFT JOIN crash c    ON h.GRID_ID = c.GRID_ID
    LEFT JOIN impaired i ON h.GRID_ID = i.GRID_ID
),
scored AS (
    SELECT *,
        POW(crash_f + 0.1, 0.5) * POW(venue_f + 0.1, 0.3) * POW(imp_f + 0.1, 0.2) - 0.1 AS geo
    FROM factors
),
ranked AS (
    SELECT *, ROUND(100 * geo / MAX(geo) OVER (), 0) AS priority
    FROM scored
),
ranked2 AS (
    SELECT *, RANK() OVER (ORDER BY priority DESC) AS city_rank
    FROM ranked
)
SELECT
    GRID_ID,
    ward,
    'Ward ' || ward AS ward_label,
    priority,
    city_rank,
    dui_arrests,   -- validation only; never enters Priority
    crash_people, crash_pts,
    n_estab,
    imp_people, imp_pts
FROM ranked2
```

```sql hex_base
-- The table's data: all hexes with a score, narrowed to one by a map click.
SELECT *
FROM ${dui_hex}
WHERE priority > 0
  AND (CASE
        WHEN '${inputs.hex_select.GRID_ID}' LIKE 'HEX_%'
            THEN GRID_ID = '${inputs.hex_select.GRID_ID}'
        ELSE TRUE
       END)
ORDER BY priority DESC
```

```sql hex_filtered
-- hex_base AND the table row selection (inputs.hex_pick).
SELECT * FROM ${hex_base}
WHERE ${inputs.hex_pick}
```

```sql selected_hex
-- Exactly one row iff the scope has narrowed to a single hex.
SELECT f.*, s.hx, s.hy
FROM (SELECT *, COUNT(*) OVER () AS n FROM ${hex_filtered}) f
JOIN dui.hex_static s USING (GRID_ID)
WHERE f.n = 1
```

```sql sel_breakdown
-- People behind the two injury factors for the selected hex, by severity.
WITH sel AS (SELECT GRID_ID FROM ${selected_hex}),
rows AS (
    SELECT
        'Injury crashes (' || (SELECT label FROM ${window_label}) || ', '
            || (SELECT current_period_range FROM ${selected_date_range}) || ')' AS factor,
        1 AS sort_order,
        SEVERITY, "COUNT"
    FROM crashes.crashes
    WHERE GRID_ID IN (SELECT GRID_ID FROM sel)
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                         AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
      AND (
        CASE
            WHEN '${inputs.window_preset.value}' = 'all_hours' THEN TRUE
            WHEN '${inputs.window_preset.value}' = 'late_weekend' THEN
                 (DATE_PART('hour', REPORTDATE) IN (22, 23) AND DATE_PART('dow', REPORTDATE) IN (4, 5, 6))
              OR (DATE_PART('hour', REPORTDATE) IN (0, 1, 2, 3) AND DATE_PART('dow', REPORTDATE) IN (5, 6, 0))
            ELSE DATE_PART('hour', REPORTDATE) IN (22, 23, 0, 1, 2, 3)
        END
      )
    UNION ALL
    SELECT 'Impaired-driver crashes (all hours, past 5 years)', 2, SEVERITY, "COUNT"
    FROM crashes.crashes
    WHERE GRID_ID IN (SELECT GRID_ID FROM sel)
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND COALESCE(DRIVERSIMPAIRED, 0) > 0
      AND REPORTDATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE - INTERVAL 5 YEAR
)
SELECT
    factor,
    SUM(CASE WHEN SEVERITY = 'Fatal' THEN "COUNT" ELSE 0 END) AS killed,
    SUM(CASE WHEN SEVERITY = 'Major' THEN "COUNT" ELSE 0 END) AS major,
    SUM(CASE WHEN SEVERITY = 'Minor' THEN "COUNT" ELSE 0 END) AS minor,
    SUM(CASE SEVERITY WHEN 'Fatal' THEN 10 WHEN 'Major' THEN 5 WHEN 'Minor' THEN 1 ELSE 0 END * "COUNT") AS points
FROM rows
GROUP BY factor, sort_order
ORDER BY sort_order
```

```sql sel_venues
-- Licensed on-premise alcohol venues within 400 m (about 1,300 ft) of the selected hex.
SELECT
    e.TRADE_NAME,
    e.ADDRESS,
    CASE
        WHEN e.TYPE IN ('Nightclub', 'Club') THEN 'Nightclub'
        WHEN e.TYPE = 'Tavern' THEN 'Bar / tavern'
        WHEN e.nightlife_flag THEN e.TYPE || ' (dancing, cover, or entertainment)'
        ELSE e.TYPE
    END AS venue_kind,
    ROUND(SQRT(POW(e.XCOORD - s.hx, 2) + POW(e.YCOORD - s.hy, 2)) * 3.281, 0) AS dist_ft,
    e.LATITUDE,
    e.LONGITUDE
FROM dui.establishments e
CROSS JOIN ${selected_hex} s
WHERE SQRT(POW(e.XCOORD - s.hx, 2) + POW(e.YCOORD - s.hy, 2)) < 400
ORDER BY e.weight DESC, dist_ft
```

Ranks areas of DC for impaired driving enforcement. A higher **Priority Score** means a stronger case for patrols, checkpoints, or late-night presence.

<Alert status="info">
Select a hexagon on the map or a row in the table to see it up close. Select it again to clear. Use the map or the table, not both: clear one selection before starting a new one in the other.
</Alert>

<DateRange
start={
  (date_bounds && date_bounds[0] && date_bounds[0].start_5y)
  ? `${date_bounds[0].start_5y}`
  : '2021-01-01'
}
end={
  (last_record && last_record[0] && last_record[0].end_date)
  ? `${last_record[0].end_date}`
  : (() => {
      const twoDaysAgo = new Date(new Date().setDate(new Date().getDate() - 2));
      return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(twoDaysAgo);
    })()
}
name="date_range"
presetRanges={['Last 12 Months', 'Year to Today', 'Last Year', 'All Time']}
description="Defaults to the last five years, the longest range available here ('All Time'). Shorter ranges have fewer crashes and less stable rankings. There is a two-day lag after the latest update."
/>

<Dropdown
data={unique_severity}
name="multi_severity"
value="SEVERITY"
title="Severity"
multiple={true}
defaultValue={['Fatal', 'Major', 'Minor']}
/>

<Dropdown name="window_preset" title="Time Window" defaultValue="late_all">
    <DropdownOption value="late_all"     valueLabel="Late night (10pm to 4am), all days"/>
    <DropdownOption value="late_weekend" valueLabel="Late night, weekend (Thu to Sat nights)"/>
    <DropdownOption value="all_hours"    valueLabel="All hours"/>
</Dropdown>

<div class="invert-on-mobile">
<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Impaired Driving Priority: {`${sev_label[0].label}`} ({`${selected_date_range[0].current_period_range}`})</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                Select a hexagon on the map for details. Select it again to clear. Refresh the page to reset.
            </span>
        </div>
        <BaseMap
            height=560
            startingZoom=12
            basemap={`https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`}
            attribution='© <a href="https://carto.com/attributions">CARTO</a>, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        >
            <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
                tooltip={[{id: 'ROUTENAME'}]} />
            <Areas data={dui_hex} name=hex_select geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/crash-hexgrid.geojson' geoId=GRID_ID areaCol=GRID_ID value=priority min=0 opacity=0.7
                tooltip={[
                    {id: 'GRID_ID', valueClass: 'text-l font-semibold', showColumnName: false},
                    {id: 'ward_label', showColumnName: false},
                    {id: 'city_rank', title: 'Rank'},
                    {id: 'priority', title: 'Priority Score (0‑100)'},
                    {id: 'crash_pts', title: 'Injury Crashes (points)'},
                    {id: 'n_estab', title: 'Venues Nearby (count)'},
                    {id: 'imp_pts', title: 'Impaired‑Driver Crashes (points)'},
                    {id: 'dui_arrests', title: "DUI Arrests* ('21‑'25)"}
                ]} />
        </BaseMap>
        <Note>The purple lines represent DC's High Injury Network.</Note>
        <Note>
            The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
        </Note>
    </Group>
    <Group>
        <div style="font-size: 14px; margin-bottom: 4px;">
            <b>Priority Ranking: {`${sev_label[0].label}`} ({`${selected_date_range[0].current_period_range}`})</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                Select a row to see the hexagon up close. Select it again to clear. Select a header to sort.
            </span>
        </div>
        {#if hex_base.length > 0}
        <SelectableTable
            data={hex_base}
            name=hex_pick
            valueCol=GRID_ID
            itemLabel=hexagons
            rows=12
            rowShading=true
            collapseOnSelect=true
            wrapTitles=true
            columns={[
                // Headers use non-breaking hyphens (U+2011) and non-breaking spaces (U+00A0)
                // so a unit like (0-100) never splits or wraps onto its own line.
                { id: 'city_rank',  title: 'Rank', fmt: 'num' },
                { id: 'GRID_ID',    title: 'Hexagon', sub: 'ward_label' },
                { id: 'priority',   title: 'Priority Score (0‑100)', fmt: 'num', colorscale: true, colorMin: 0 },
                { id: 'crash_pts',  title: 'Injury Crashes (points)', fmt: 'num' },
                { id: 'n_estab',    title: 'Venues Nearby (count)', fmt: 'num' },
                { id: 'imp_pts',    title: 'Impaired-Driver Crashes (points)', fmt: 'num' },
                { id: 'dui_arrests', title: "DUI Arrests* ('21‑'25)", fmt: 'num' }
            ]}
            initialSort={{ col: 'priority', dir: 'desc' }}
        />
        <Note>
            Points are not crash counts: 10 per person killed, 5 per serious injury, 1 per minor injury.<br/>
            *DUI Arrests (count), 2021 to 2025: shown for validation only. Not used in the Priority Score.
        </Note>
        {:else}
        <Note>
            No hexagons score for the selected filters. Try a longer date range or the "All hours" time window.
        </Note>
        {/if}

        {#if selected_hex.length === 1}
        <div style="font-size: 14px; margin-top: 12px;">
            <b>{selected_hex[0].GRID_ID} (Ward {selected_hex[0].ward}): Priority {selected_hex[0].priority}, rank {selected_hex[0].city_rank} citywide</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                DUI arrests here, 2021-2025: {selected_hex[0].dui_arrests} (validation only; not part of Priority Score)
            </span>
        </div>
        <BaseMap
            height=320
            startingZoom=17
            basemap={`https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`}
            attribution='© <a href="https://carto.com/attributions">CARTO</a>, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        >
            <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
                tooltip={[{id: 'ROUTENAME', showColumnName: false}]} />
            <Areas data={selected_hex} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/crash-hexgrid.geojson' geoId=GRID_ID areaCol=GRID_ID color=#1C00ff00 borderColor='#dc2626' borderWidth=3
                tooltip={[{id: 'GRID_ID', showColumnName: false}]} />
            {#if sel_venues.length > 0}
            <Points data={sel_venues} lat=LATITUDE long=LONGITUDE color='#b45309' opacity=0.8 ignoreZoom=true legend=false
                tooltip={[
                    {id: 'TRADE_NAME', valueClass: 'text-l font-semibold', showColumnName: false},
                    {id: 'venue_kind', title: 'Type'},
                    {id: 'ADDRESS', showColumnName: false}
                ]} />
            {/if}
        </BaseMap>
        <Note>Red outline: the selected hexagon. Brown dots: licensed alcohol venues nearby (within 1,300 ft).</Note>

        <DataTable data={sel_breakdown} rows=all rowShading=true wrapTitles=true title="People Hurt Behind This Score">
            <Column id=factor title="Factor" wrap=true/>
            <Column id=killed title="Killed"/>
            <Column id=major  title="Seriously injured"/>
            <Column id=minor  title="Minor injury"/>
            <Column id=points title="Points"/>
        </DataTable>

        {#if sel_venues.length > 0}
        <DataTable data={sel_venues} rows=8 search=true rowShading=true wrapTitles=true title="Venues Nearby ({sel_venues.length})">
            <Column id=TRADE_NAME title="Venue" wrap=true/>
            <Column id=venue_kind title="Type" wrap=true/>
            <Column id=ADDRESS    title="Address" wrap=true/>
            <Column id=dist_ft    title="Distance (ft)" fmt='#,##0'/>
        </DataTable>
        {:else}
        <Note>No licensed on-premise alcohol venues nearby (within 1,300 ft).</Note>
        {/if}
        {/if}
    </Group>
</Grid>
</div>

<Details title="How to use this page">

The city is divided into hexagons about 800 feet across, roughly two to three blocks. Each hexagon gets a **Priority Score** from 0 to 100. The top hexagon scores 100 and every other score is relative to it. Priority score is used for ranking, not a crash count or a probability.

Priority score combines three factors:

- **Injury Crashes (points).** People hurt in crashes during the selected dates and time window (10pm to 4am by default), counted as points by severity: **10 per person killed, 5 per person seriously injured, 1 per minor injury.** These are points, not a count of crashes: one death adds 10, and one crash can hurt several people. Most impaired driving crashes happen late at night, so the default window captures them even when the police report does not record impairment.
- **Venues Nearby (count).** The number of bars, nightclubs, taverns, and restaurants with dancing, a cover charge, or entertainment, licensed by ABCA, within about 1,300 feet (400 m) of the hexagon. The score also counts closer venues and bar-type venues more than ordinary restaurants, so two hexagons with the same count can score differently. Liquor stores and grocery stores are not included.
- **Impaired-Driver Crashes (points).** People hurt over the past five years, at any hour, in crashes where the MPD report lists at least one driver as impaired, with the same points per person. Reports undercount impairment, so this factor carries the least weight and serves as supporting evidence.

Hexagons that score on **several factors rank highest**. A hexagon strong on only one factor still appears, lower on the list. Read the three columns together to see why a hexagon ranks where it does:

- **High injury crash points and many venues nearby:** a nightlife area where people are getting hurt. Best fit for saturation patrols and checkpoints, especially around closing time.
- **High injury crash points, few or no venues:** a dangerous road away from nightlife, often a route home. Consider roving patrols during late hours.
- **Many venues, few injury crash points:** dense nightlife without a crash history yet. Consider preventive presence at closing time.

**DUI Arrests**\* (count of MPD arrests for driving while intoxicated, 2021 to 2025, by offense location) appear for **validation** but are **not used in the Priority Score**. The asterisk in the table marks this.

*How to use them.* Arrests are the one source here that the score never sees, so they work as an outside check:

- **Citywide:** high-priority hexagons should also show more DUI arrests than the rest. They do: the top 10% of hexagons average about three times as many arrests as all other scored hexagons. That agreement is evidence the score finds places where impaired driving actually happens.
- **For one hexagon:** read Priority and arrests together. High Priority with many arrests means the data and current enforcement agree. High Priority with few or no arrests means people are getting hurt in conditions linked to impaired driving, but DUI enforcement has not focused there. Those hexagons deserve a closer look.

*Why they are not part of Priority.* An arrest happens only where an officer is present and makes a stop, so arrest counts measure enforcement effort as much as impaired driving. From 2021 to 2025, DUI arrests per person hurt in an impaired-driver crash ranged from about 2.6 in Ward 7 to 5.9 in Ward 4. Including arrests in the score would rank highest the places MPD already patrols, which would bring more patrols there, which would produce more arrests: a loop that measures past enforcement and hides under-served areas. The arrest data also ends in 2025, so it cannot follow the date filter.

</Details>

<Details title="How Priority score is calculated">

**Step 1. Score each factor from 0 to 1.** Divide the hexagon's value by the highest value of any hexagon:

```
Crash score    = hexagon's injury crash points          ÷ highest hexagon's injury crash points
Venue score    = hexagon's weighted venue density       ÷ highest hexagon's weighted venue density
Impaired score = hexagon's impaired-driver crash points ÷ highest hexagon's impaired-driver crash points
```

**Step 2. Combine the three scores.** Each score, plus a floor of 0.1, is raised to the power of its weight, and the results are multiplied:

```
Combined = (Crash score + 0.1)^0.5  ×  (Venue score + 0.1)^0.3  ×  (Impaired score + 0.1)^0.2  −  0.1
```

**Step 3. Rescale to 0 to 100.**

```
Priority = 100 × Combined ÷ highest Combined of any hexagon
```

**What the weights do.** The weights are the exponents 0.5, 0.3, and 0.2, and they add up to 1. A larger exponent gives that factor more pull on the result. Doubling a factor's term multiplies Combined by 2 raised to its weight:

| Factor | Weight | Doubling its term multiplies Combined by |
|---|---|---|
| Injury crashes | 0.5 | 2^0.5 = 1.41 (41% higher) |
| Venues nearby | 0.3 | 2^0.3 = 1.23 (23% higher) |
| Impaired-driver crashes | 0.2 | 2^0.2 = 1.15 (15% higher) |

Injury crashes carry the most weight because they directly measure people hurt. Venues come next as the main independent signal of late-night drinking. Impaired-driver crashes carry the least because police reports undercount impairment.

**Why multiply instead of add.** Compare two hexagons. Hexagon A has a perfect crash score and nothing else (scores 1, 0, 0). Hexagon B is halfway on all three (0.5, 0.5, 0.5). With a weighted sum, both score 0.5 and tie. With the formula above, A gets 0.23 and B gets 0.50, so B ranks clearly higher. Multiplying rewards hexagons where several warning signs line up.

**Why the 0.1 floor.** Without it, a zero on any one factor would make the whole product zero, and a deadly road with no bars nearby would drop off the list. The floor keeps such hexagons ranked, lower than places where signals combine.

**Other definitions.**

- **Injury points:** 10 per person killed, 5 per serious injury, 1 per minor injury, following the DDOT High Injury Network methodology.
- **Weighted venue density:** the sum over venues within 400 m of (type weight × (1 − distance ÷ 400 m)), so a venue next door counts fully and one at 400 m counts zero. Type weights: nightclub or club 1.0, tavern 0.9, arena 0.8, multipurpose 0.7, restaurant 0.4, hotel 0.3, bed and breakfast 0.2. A nightlife endorsement (dancing, cover charge, or entertainment) raises restaurants and multipurpose venues to 0.8, arenas to 0.9, hotels to 0.6, and bed and breakfasts to 0.5.
Data notes:

- The 10pm to 4am window was validated against MPD's impairment flag: injuries in crashes with an impaired driver are about twice as concentrated in that window as injuries overall.
- Venue data comes from ABCA's active license list (on-premise Class C and D). It has no hours of operation, so license type and nightlife endorsements stand in for late-night operation. A venue's presence says nothing about how that business operates; the factor measures where late-night drinking concentrates, not the conduct of any establishment.
- The impaired-driver factor uses a fixed five-year lookback because these crashes are too rare to rank on over a few months.
- DUI arrests come from MPD's Adult Arrests open data (category "Driving/Boating While Intoxicated", boating records excluded), located to the 100 m block of the offense. The validation figure above uses the default view (last five years, 10pm to 4am, all severities): the top 10% of hexagons by Priority average 4.7 DUI arrests in 2021 to 2025, versus 1.4 for the other scored hexagons.

</Details>

<style>
  /* On mobile, put the ranking table above the map (same as the intersections page). */
  @media (max-width: 639px) {
    .invert-on-mobile > :global(.grid) > :global(div:nth-child(1)) { order: 2; }
    .invert-on-mobile > :global(.grid) > :global(div:nth-child(2)) { order: 1; }
  }
</style>
