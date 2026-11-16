---
title: Impaired Driving Enforcement (BETA)
queries:
   - last_record: last_record.sql
sidebar_link: false
---

<!--
  Data prerequisites:
    crashes.crashes      needs the backend columns from assign_police_areas_and_locations():
                         LOCATION_ID, LOCATION_NAME, LOCATION_TYPE, LOCATION_PSA,
                         LOCATION_DISTRICT, LOCATION_FLAG
    dui.locations        <- dui_locations_static.parquet (scripts/build_dui_locations_static.py)
                         LOCATION_ID, LOCATION_TYPE, ROAD_CLASS, LATITUDE, LONGITUDE,
                         x, y (State Plane meters), est_kde_norm, n_estab_400m,
                         dui_arrests (2021-2025, validation only)
    dui.establishments   <- establishments_weighted.parquet
    static/Roadway_Block_Segments.geojson   block lines for the detail map (from the backend)
    static/Intersection_Points_buffers.geojson   intersection radius (already used by Intersections)

  A location is an intersection (crash within 100 ft) or a block segment (nearest
  block within 200 ft; blocks over 1,000 ft split into ~500 ft pieces). Each
  location belongs to one PSA and district: where most of its injured people
  were hurt. Locations with no crash in the selected filters are not shown.

  Priority Score (all knobs live in the dui_loc query):
    Three factors, each scaled 0 to 1 against the top location citywide:
      crash    = injury points (Fatal 10 / Major 5 / Minor 1 per injured person)
                 in the selected dates and time window
      venues   = distance-decayed weight of late-hour on-premise alcohol venues
                 within 400 m (precomputed, static)
      impaired = injury points in crashes where MPD reported an impaired driver
                 (DRIVERSIMPAIRED > 0), all hours, fixed 5-year lookback ending at
                 the latest record (too rare to rank on in a short date range)
    Combined with a weighted geometric mean (0.5 / 0.3 / 0.2) and a 0.1 floor,
    rescaled so the top location citywide = 100. The District and PSA filters
    narrow the list but do not rescale it, so scores and ranks stay citywide.

  Selection wiring (mirrors pages/intersections):
    map click   -> inputs.loc_select.LOCATION_ID -> narrows loc_base (the table's data)
    table click -> inputs.loc_pick (WHERE fragment) -> loc_filtered -> selected_loc
    selected_loc has exactly one row when one location is in scope -> detail shows
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

```sql districts
SELECT LOCATION_DISTRICT AS district
FROM crashes.crashes
WHERE LOCATION_DISTRICT IS NOT NULL
GROUP BY 1
ORDER BY 1
```

```sql psas
-- PSAs in the selected district (all PSAs when no district is selected)
SELECT LOCATION_PSA AS psa, 'PSA ' || LOCATION_PSA AS psa_label
FROM crashes.crashes
WHERE LOCATION_PSA IS NOT NULL
  AND LOCATION_DISTRICT LIKE '${inputs.district.value}'
GROUP BY 1, 2
ORDER BY 1
```

```sql top_label
-- "Top 500" / "Top 100" / "All" for the map and table titles
SELECT CASE '${inputs.top_n.value}'
    WHEN 'all' THEN 'All'
    ELSE 'Top ' || '${inputs.top_n.value}'
END AS label
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

```sql dui_loc
-- Every location with an injury crash in the filters, scored citywide.
WITH loc_raw AS (
    -- Name, type, PSA, district, and flag: fixed per location (full history)
    SELECT
        LOCATION_ID,
        -- Street types abbreviated (same list as pages/last7days, no state
        -- abbreviations). Whole words only: the name is padded with spaces so
        -- ' STREET ' never matches inside a word. The block range is kept here.
        TRIM(
          REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
          REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            ' ' || ANY_VALUE(LOCATION_NAME) || ' ',
            ' STREET ', ' ST '), ' AVENUE ', ' AVE '), ' ROAD ', ' RD '),
            ' PLACE ', ' PL '), ' COURT ', ' CT '), ' CIRCLE ', ' CIR '),
            ' BOULEVARD ', ' BLVD '), ' DRIVE ', ' DR '), ' TERRACE ', ' TER '),
            ' PARKWAY ', ' PKWY '), ' EXPRESSWAY ', ' EXPY '), ' LANE ', ' LN ')
        )                            AS full_name,
        ANY_VALUE(LOCATION_TYPE)     AS location_type,
        ANY_VALUE(LOCATION_PSA)      AS psa,
        ANY_VALUE(LOCATION_DISTRICT) AS district,
        ANY_VALUE(LOCATION_FLAG)     AS location_flag
    FROM crashes.crashes
    WHERE LOCATION_ID IS NOT NULL
    GROUP BY LOCATION_ID
),
loc_short AS (
    -- MPD style keeps only the start of the block range:
    -- "1 - 99 BLOCK OF M ST NE" -> "1 BLOCK OF M ST NE". The optional space also
    -- repairs DDOT names missing one ("700 - 899 BLOCK OFALLEN ...").
    SELECT *, REGEXP_REPLACE(full_name, ' - [0-9]+ BLOCK OF ?', ' BLOCK OF ') AS short_name
    FROM loc_raw
),
loc_attr AS (
    -- Two different blocks can start at the same number ("1500 - 1599" and
    -- "1500 - 1514 BLOCK OF KENILWORTH AVE NE"); those keep the full range.
    SELECT * EXCLUDE (full_name, short_name),
        CASE WHEN location_type = 'Block'
                  AND COUNT(*) OVER (PARTITION BY short_name) > 1
             THEN REGEXP_REPLACE(full_name, ' BLOCK OF ?', ' BLOCK OF ')
             ELSE short_name END AS location_name
    FROM loc_short
),
crash AS (
    -- Factor 1: injury points in the selected dates and time window
    SELECT
        LOCATION_ID,
        SUM("COUNT") AS crash_people,
        SUM(CASE SEVERITY WHEN 'Fatal' THEN 10 WHEN 'Major' THEN 5 WHEN 'Minor' THEN 1 ELSE 0 END
            * "COUNT") AS crash_pts
    FROM crashes.crashes
    WHERE LOCATION_ID IS NOT NULL
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
    GROUP BY LOCATION_ID
),
impaired AS (
    -- Factor 3: injury points in impaired-driver crashes (past 5 years, any hour)
    SELECT
        LOCATION_ID,
        SUM("COUNT") AS imp_people,
        SUM(CASE SEVERITY WHEN 'Fatal' THEN 10 WHEN 'Major' THEN 5 WHEN 'Minor' THEN 1 ELSE 0 END
            * "COUNT") AS imp_pts
    FROM crashes.crashes
    WHERE LOCATION_ID IS NOT NULL
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND COALESCE(DRIVERSIMPAIRED, 0) > 0
      AND REPORTDATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE - INTERVAL 5 YEAR
    GROUP BY LOCATION_ID
),
factors AS (
    SELECT
        a.*,
        s.ROAD_CLASS                AS road_class,
        s.LATITUDE, s.LONGITUDE,
        COALESCE(s.n_estab_400m, 0) AS n_estab,
        COALESCE(s.dui_arrests, 0)  AS dui_arrests,   -- validation only, not in Priority
        COALESCE(c.crash_people, 0) AS crash_people,
        COALESCE(c.crash_pts, 0)    AS crash_pts,
        COALESCE(i.imp_people, 0)   AS imp_people,
        COALESCE(i.imp_pts, 0)      AS imp_pts,
        COALESCE(c.crash_pts / NULLIF(MAX(c.crash_pts) OVER (), 0), 0) AS crash_f,
        COALESCE(s.est_kde_norm, 0)                                    AS venue_f,  -- Factor 2
        COALESCE(i.imp_pts / NULLIF(MAX(i.imp_pts) OVER (), 0), 0)     AS imp_f
    FROM loc_attr a
    JOIN dui.locations s USING (LOCATION_ID)
    LEFT JOIN crash c    USING (LOCATION_ID)
    LEFT JOIN impaired i USING (LOCATION_ID)
    WHERE COALESCE(c.crash_pts, 0) > 0 OR COALESCE(i.imp_pts, 0) > 0
),
scored AS (
    SELECT *,
        POW(crash_f + 0.1, 0.5) * POW(venue_f + 0.1, 0.3) * POW(imp_f + 0.1, 0.2) - 0.1 AS geo
    FROM factors
),
ranked AS (
    SELECT *,
        ROUND(100 * geo / MAX(geo) OVER (), 0) AS priority,
        RANK() OVER (ORDER BY geo DESC)        AS city_rank
    FROM scored
)
SELECT
    LOCATION_ID,
    location_name,
    location_type,
    road_class,
    district,
    psa,
    'PSA ' || psa || COALESCE(' · ' || location_flag, '') AS loc_sub,   -- line under the name
    location_flag,
    priority,
    city_rank,
    crash_people, crash_pts,
    n_estab,
    imp_people, imp_pts,
    dui_arrests,   -- validation only; never enters Priority
    LATITUDE, LONGITUDE
FROM ranked
WHERE district LIKE '${inputs.district.value}'
  -- a PSA left over from another district is ignored rather than emptying the page
  AND (psa LIKE '${inputs.psa.value}'
       OR '${inputs.psa.value}' NOT IN (SELECT psa FROM ${psas}))
-- Show the top N locations of the current District/PSA view (ranks stay citywide)
QUALIFY ROW_NUMBER() OVER (ORDER BY city_rank, LOCATION_ID)
        <= CASE WHEN '${inputs.top_n.value}' = 'all' THEN 1000000
                ELSE CAST('${inputs.top_n.value}' AS INTEGER) END
```

```sql loc_map
-- Map points drawn lowest score first, so the highest-priority points end up on top.
SELECT * FROM ${dui_loc}
ORDER BY priority ASC, city_rank DESC
```

```sql loc_base
-- The table's data, narrowed to one location by a map click.
SELECT *
FROM ${dui_loc}
WHERE (CASE
        WHEN length('${inputs.loc_select.LOCATION_ID}') >= 32
            THEN LOCATION_ID = '${inputs.loc_select.LOCATION_ID}'
        ELSE TRUE
       END)
ORDER BY priority DESC, city_rank
```

```sql loc_filtered
-- loc_base AND the table row selection (inputs.loc_pick).
SELECT * FROM ${loc_base}
WHERE ${inputs.loc_pick}
```

```sql selected_loc
-- Exactly one row iff the scope has narrowed to a single location.
-- INTERSECTIONKEY / SEGMENT_ID key the detail map's outline layers.
SELECT f.*, s.x, s.y,
    CASE WHEN f.location_type = 'Intersection' THEN f.LOCATION_ID END AS INTERSECTIONKEY,
    CASE WHEN f.location_type = 'Block'        THEN f.LOCATION_ID END AS SEGMENT_ID
FROM (SELECT *, COUNT(*) OVER () AS n FROM ${loc_filtered}) f
JOIN dui.locations s USING (LOCATION_ID)
WHERE f.n = 1
```

```sql sel_breakdown
-- People behind the two injury factors for the selected location, by severity.
WITH sel AS (SELECT LOCATION_ID FROM ${selected_loc}),
rows AS (
    SELECT
        'Injury crashes (' || (SELECT label FROM ${window_label}) || ', '
            || (SELECT current_period_range FROM ${selected_date_range}) || ')' AS factor,
        1 AS sort_order,
        SEVERITY, "COUNT"
    FROM crashes.crashes
    WHERE LOCATION_ID IN (SELECT LOCATION_ID FROM sel)
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
    WHERE LOCATION_ID IN (SELECT LOCATION_ID FROM sel)
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

```sql sel_psas
-- PSAs of the crashes counted at the selected location (shown when there is more than one)
SELECT string_agg(DISTINCT 'PSA ' || PSA, ', ' ORDER BY 'PSA ' || PSA) AS psas,
       COUNT(DISTINCT PSA) AS n_psa
FROM crashes.crashes
WHERE LOCATION_ID IN (SELECT LOCATION_ID FROM ${selected_loc})
```

```sql sel_venues
-- Licensed on-premise alcohol venues within 400 m (about 1,300 ft) of the selected location.
SELECT
    e.TRADE_NAME,
    e.ADDRESS,
    CASE
        WHEN e.TYPE IN ('Nightclub', 'Club') THEN 'Nightclub'
        WHEN e.TYPE = 'Tavern' THEN 'Bar / tavern'
        WHEN e.nightlife_flag THEN e.TYPE || ' (dancing, cover, or entertainment)'
        ELSE e.TYPE
    END AS venue_kind,
    ROUND(SQRT(POW(e.XCOORD - s.x, 2) + POW(e.YCOORD - s.y, 2)) * 3.281, 0) AS dist_ft,
    e.LATITUDE,
    e.LONGITUDE
FROM dui.establishments e
CROSS JOIN ${selected_loc} s
WHERE SQRT(POW(e.XCOORD - s.x, 2) + POW(e.YCOORD - s.y, 2)) < 400
ORDER BY e.weight DESC, dist_ft
```

Ranks intersections and blocks in DC for impaired driving enforcement. A higher **Priority Score** means a stronger case for patrols, checkpoints, or late-night presence.

<Alert status="info">
Select a location on the map or a row in the table to see it up close. Select it again to clear. Use the map or the table, not both: clear one selection before starting a new one in the other.
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

<Dropdown data={districts} name="district" value="district" title="Police District" defaultValue="%">
    <DropdownOption value="%" valueLabel="All Districts"/>
</Dropdown>

<Dropdown name="top_n" title="Locations" defaultValue="500">
    <DropdownOption value="100" valueLabel="Top 100"/>
    <DropdownOption value="500" valueLabel="Top 500"/>
    <DropdownOption value="all" valueLabel="All"/>
</Dropdown>

<Dropdown data={psas} name="psa" value="psa" label="psa_label" title="PSA" defaultValue="%">
    <DropdownOption value="%" valueLabel="All PSAs"/>
</Dropdown>

<div class="invert-on-mobile">
<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>{`${top_label[0].label}`} Impaired Driving Priority Locations ({`${selected_date_range[0].current_period_range}`})</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                Select a location on the map for details. Select it again to clear. Refresh the page to reset.
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
            <Points data={loc_map} name=loc_select lat=LATITUDE long=LONGITUDE value=priority min=0 opacity=0.8 ignoreZoom=false
                tooltip={[
                    {id: 'location_name', valueClass: 'text-l font-semibold', showColumnName: false},
                    {id: 'loc_sub', showColumnName: false},
                    {id: 'city_rank', title: 'Rank'},
                    {id: 'priority', title: 'Priority Score (0‑100)'},
                    {id: 'crash_pts', title: 'Injury Crashes (points)'},
                    {id: 'n_estab', title: 'Venues Nearby (count)'},
                    {id: 'imp_pts', title: 'Impaired‑Driver Crashes (points)'},
                    {id: 'dui_arrests', title: "DUI Arrests* ('21‑'25)"}
                ]} />
        </BaseMap>
        <Note>Each dot is an intersection or a block. The purple lines represent DC's High Injury Network.</Note>
        <Note>
            The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
        </Note>
    </Group>
    <Group>
        <div style="font-size: 14px; margin-bottom: 4px;">
            <b>{`${top_label[0].label}`} Impaired Driving Locations Ranked by Priority ({`${selected_date_range[0].current_period_range}`})</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                Select a row to see the location up close. Select it again to clear. Select a header to sort.
            </span>
        </div>
        {#if loc_base.length > 0}
        <SelectableTable
            data={loc_base}
            name=loc_pick
            valueCol=LOCATION_ID
            itemLabel=locations
            rows=12
            rowShading=true
            collapseOnSelect=true
            wrapTitles=true
            columns={[
                // Headers use non-breaking hyphens (U+2011) and non-breaking spaces (U+00A0)
                // so a unit like (0-100) never splits or wraps onto its own line.
                { id: 'city_rank',     title: 'Rank', fmt: 'num' },
                { id: 'location_name', title: 'Location', sub: 'loc_sub' },
                { id: 'priority',      title: 'Priority Score (0‑100)', fmt: 'num', colorscale: true, colorMin: 0 },
                { id: 'crash_pts',     title: 'Injury Crashes (points)', fmt: 'num' },
                { id: 'n_estab',       title: 'Venues Nearby (count)', fmt: 'num' },
                { id: 'imp_pts',       title: 'Impaired‑Driver Crashes (points)', fmt: 'num' },
                { id: 'dui_arrests',   title: "DUI Arrests* ('21‑'25)", fmt: 'num' }
            ]}
            initialSort={{ col: 'priority', dir: 'desc' }}
        />
        <Note>
            Rank and Priority Score are citywide; the Locations, District, and PSA filters narrow the list without rescaling it.<br/>
            Points are not crash counts: 10 per person killed, 5 per serious injury, 1 per minor injury.<br/>
            *DUI Arrests (count) within 1,300 ft, 2021 to 2025: shown for validation only. Not used in the Priority Score.
        </Note>
        {:else}
        <Note>
            No locations score for the selected filters. Try a longer date range, the "All hours" time window, or another district or PSA.
        </Note>
        {/if}

        {#if selected_loc.length === 1}
        <div style="font-size: 14px; margin-top: 12px;">
            <b>{selected_loc[0].location_name}</b>
            <span style="display:block; font-size: 12px; color: #6c757d;">
                {selected_loc[0].location_type}{selected_loc[0].road_class ? ` (${selected_loc[0].road_class})` : ''} · {selected_loc[0].district} · PSA {selected_loc[0].psa} · Priority Score {selected_loc[0].priority}, rank {selected_loc[0].city_rank} citywide
            </span>
            {#if sel_psas.length > 0 && sel_psas[0].n_psa > 1}
            <span style="display:block; font-size: 12px; color: #6c757d;">
                Its crashes fall in {sel_psas[0].psas}; it is listed under PSA {selected_loc[0].psa}, where most people were hurt.
            </span>
            {/if}
            <span style="display:block; font-size: 12px; color: #6c757d;">
                DUI arrests within 1,300 ft, 2021-2025: {selected_loc[0].dui_arrests} (validation only; not part of the Priority Score)
            </span>
        </div>
        {#if selected_loc[0].location_flag}
        <Alert status="warning">
            <b>{selected_loc[0].location_flag}.</b> Many crashes counted here sit on a single point that MPD's geocoding used as a default location before its October 2026 fix. Those crashes may have happened elsewhere along the road, so this location's score may be inflated.
        </Alert>
        {/if}
        <BaseMap
            height=320
            startingZoom=17
            basemap={`https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`}
            attribution='© <a href="https://carto.com/attributions">CARTO</a>, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        >
            <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
                tooltip={[{id: 'ROUTENAME', showColumnName: false}]} />
            {#if selected_loc[0].location_type === 'Intersection'}
            <Areas data={selected_loc} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/Intersection_Points_buffers.geojson' geoId=INTERSECTIONKEY areaCol=INTERSECTIONKEY color=#1C00ff00 borderColor='#dc2626' borderWidth=3 ignoreZoom=false
                tooltip={[{id: 'location_name', showColumnName: false}]} />
            {:else}
            <Areas data={selected_loc} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/Roadway_Block_Segments.geojson' geoId=SEGMENT_ID areaCol=SEGMENT_ID color=#1C00ff00 borderColor='#dc2626' borderWidth=5 ignoreZoom=false
                tooltip={[{id: 'location_name', showColumnName: false}]} />
            {/if}
            {#if sel_venues.length > 0}
            <Points data={sel_venues} lat=LATITUDE long=LONGITUDE color='#b45309' opacity=0.8 ignoreZoom=true legend=false
                tooltip={[
                    {id: 'TRADE_NAME', valueClass: 'text-l font-semibold', showColumnName: false},
                    {id: 'venue_kind', title: 'Type'},
                    {id: 'ADDRESS', showColumnName: false}
                ]} />
            {/if}
        </BaseMap>
        <Note>
            Red outline: {selected_loc[0].location_type === 'Intersection' ? 'the 100 ft radius around the intersection' : 'the block'}. Brown dots: licensed alcohol venues nearby (within 1,300 ft).
        </Note>

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

Each location is an **intersection** or a **block**, named the way MPD reports crashes. A crash within 100 feet of an intersection counts at that intersection; otherwise it counts on the nearest block within 200 feet. Blocks longer than 1,000 feet (mostly freeways and parkways) are split into pieces of about 500 feet, each named after its nearest intersection. Each location belongs to one PSA and police district: where most of its injured people were hurt.

Each location gets a **Priority Score** from 0 to 100. The top location citywide scores 100 and every other score is relative to it. The Priority Score is for ranking; it is not a crash count or a probability. The **Locations** filter limits the map and table to the top 100 or 500 locations of the current view (500 by default) or shows all of them; the Locations, District, and PSA filters narrow the list but keep the citywide scores and ranks.

The Priority Score combines three factors:

- **Injury Crashes (points).** People hurt in crashes at the location during the selected dates and time window (10pm to 4am by default), counted as points by severity: **10 per person killed, 5 per person seriously injured, 1 per minor injury.** These are points, not a count of crashes: one death adds 10, and one crash can hurt several people. Most impaired driving crashes happen late at night, so the default window captures them even when the police report does not record impairment.
- **Venues Nearby (count).** The number of bars, nightclubs, taverns, and restaurants with dancing, a cover charge, or entertainment, licensed by ABCA, within about 1,300 feet (400 m) of the location. The score also counts closer venues and bar-type venues more than ordinary restaurants, so two locations with the same count can score differently. Liquor stores and grocery stores are not included.
- **Impaired-Driver Crashes (points).** People hurt at the location over the past five years, at any hour, in crashes where the MPD report lists at least one driver as impaired, with the same points per person. Reports undercount impairment, so this factor carries the least weight and serves as supporting evidence.

Locations that score on **several factors rank highest**. A location strong on only one factor still appears, lower on the list. Read the three columns together to see why a location ranks where it does:

- **High injury crash points and many venues nearby:** a nightlife area where people are getting hurt. Best fit for saturation patrols and checkpoints, especially around closing time.
- **High injury crash points, few or no venues:** a dangerous road away from nightlife, often a route home. Consider roving patrols during late hours.
- **Many venues, few injury crash points:** dense nightlife without a crash history yet. Consider preventive presence at closing time.

**Location errors.** Before October 2026, MPD's geocoding placed some crashes it could not locate on a few default points, such as Eastern Ave NE & Southern Ave NE, Constitution Ave NE, and points along I-395, I-295, and I-695. A location where at least a quarter of the people hurt sit on one of these points is marked **Known location error** (a confirmed default point) or **Possible location error** (a point that collects an unusual number of crashes). These locations stay in the ranking, but their scores may be inflated by crashes that happened elsewhere.

**DUI Arrests**\* (count of MPD arrests for driving while intoxicated within 1,300 feet, 2021 to 2025, by offense location) appear for **validation** but are **not used in the Priority Score**. The asterisk in the table marks this.

*How to use them.* Arrests are the one source here that the score never sees, so they work as an outside check:

- **Citywide:** high-priority locations should also show more DUI arrests nearby than the rest. They do: the top 10% of locations average about twice as many arrests nearby as all other listed locations. That agreement is evidence the score finds places where impaired driving actually happens.
- **For one location:** read Priority Score and arrests together. A high score with many arrests means the data and current enforcement agree. A high score with few or no arrests means people are getting hurt in conditions linked to impaired driving, but DUI enforcement has not focused there. Those locations deserve a closer look.

*Why they are not part of the Priority Score.* An arrest happens only where an officer is present and makes a stop, so arrest counts measure enforcement effort as much as impaired driving. From 2021 to 2025, DUI arrests per person hurt in an impaired-driver crash ranged from about 2.4 in the Sixth District to 5.2 in the Fourth District. The Sixth District had 20% of the city's impaired-driver injuries but 12% of its DUI arrests. Including arrests in the score would rank highest the places MPD already patrols, which would bring more patrols there, which would produce more arrests: a loop that measures past enforcement and hides under-served areas. The arrest data also ends in 2025, so it cannot follow the date filter.

</Details>

<Details title="How Priority score is calculated">

**Step 1. Score each factor from 0 to 1.** Divide the location's value by the highest value of any location citywide:

```
Crash score    = location's injury crash points          ÷ highest location's injury crash points
Venue score    = location's weighted venue density       ÷ highest location's weighted venue density
Impaired score = location's impaired-driver crash points ÷ highest location's impaired-driver crash points
```

**Step 2. Combine the three scores.** Each score, plus a floor of 0.1, is raised to the power of its weight, and the results are multiplied:

```
Combined = (Crash score + 0.1)^0.5  ×  (Venue score + 0.1)^0.3  ×  (Impaired score + 0.1)^0.2  −  0.1
```

**Step 3. Rescale to 0 to 100.**

```
Priority = 100 × Combined ÷ highest Combined of any location
```

**What the weights do.** The weights are the exponents 0.5, 0.3, and 0.2, and they add up to 1. A larger exponent gives that factor more pull on the result. Doubling a factor's term multiplies Combined by 2 raised to its weight:

| Factor | Weight | Doubling its term multiplies Combined by |
|---|---|---|
| Injury crashes | 0.5 | 2^0.5 = 1.41 (41% higher) |
| Venues nearby | 0.3 | 2^0.3 = 1.23 (23% higher) |
| Impaired-driver crashes | 0.2 | 2^0.2 = 1.15 (15% higher) |

Injury crashes carry the most weight because they directly measure people hurt. Venues come next as the main independent signal of late-night drinking. Impaired-driver crashes carry the least because police reports undercount impairment.

**Why multiply instead of add.** Compare two locations. Location A has a perfect crash score and nothing else (scores 1, 0, 0). Location B is halfway on all three (0.5, 0.5, 0.5). With a weighted sum, both score 0.5 and tie. With the formula above, A gets 0.23 and B gets 0.50, so B ranks clearly higher. Multiplying rewards locations where several warning signs line up.

**Why the 0.1 floor.** Without it, a zero on any one factor would make the whole product zero, and a deadly road with no bars nearby would drop off the list. The floor keeps such locations ranked, lower than places where signals combine.

**Other definitions.**

- **Injury points:** 10 per person killed, 5 per serious injury, 1 per minor injury, following the DDOT High Injury Network methodology.
- **Weighted venue density:** the sum over venues within 400 m of (type weight × (1 − distance ÷ 400 m)), so a venue next door counts fully and one at 400 m counts zero. Type weights: nightclub or club 1.0, tavern 0.9, arena 0.8, multipurpose 0.7, restaurant 0.4, hotel 0.3, bed and breakfast 0.2. A nightlife endorsement (dancing, cover charge, or entertainment) raises restaurants and multipurpose venues to 0.8, arenas to 0.9, hotels to 0.6, and bed and breakfasts to 0.5.

Data notes:

- The 10pm to 4am window was validated against MPD's impairment flag: injuries in crashes with an impaired driver are about twice as concentrated in that window as injuries overall.
- Venue data comes from ABCA's active license list (on-premise Class C and D). It has no hours of operation, so license type and nightlife endorsements stand in for late-night operation. A venue's presence says nothing about how that business operates; the factor measures where late-night drinking concentrates, not the conduct of any establishment.
- The impaired-driver factor uses a fixed five-year lookback because these crashes are too rare to rank on over a few months.
- About 3% of injured people are in crashes more than 200 feet from any intersection or block (ramps, parking lots, off-network spots); they are not assigned to a location.
- DUI arrests come from MPD's Adult Arrests open data (category "Driving/Boating While Intoxicated", boating records excluded), located to the 100 m block of the offense. The validation figure above uses the default view (last five years, 10pm to 4am, all severities): the top 10% of locations average 38 DUI arrests nearby in 2021 to 2025, versus 20 for the other listed locations.

</Details>

<style>
  /* On mobile, put the ranking table above the map (same as the intersections page). */
  @media (max-width: 639px) {
    .invert-on-mobile > :global(.grid) > :global(div:nth-child(1)) { order: 2; }
    .invert-on-mobile > :global(.grid) > :global(div:nth-child(2)) { order: 1; }
  }
</style>
