---
title: Injuries Heatmap
queries:
   - hex: hex.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 2
---

```sql unique_mode
select 
    MODE
from crashes.crashes
group by 1
```

```sql unique_severity
select 
    SEVERITY
from crashes.crashes
group by 1
```

```sql unique_hex
select 
    GRID_ID
from hexgrid.crash_hexgrid
group by 1
```

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
```

```sql day_time
WITH reference AS (
    SELECT
        dow.day_of_week,
        dow.day_number,
        hr.hour_number
    FROM 
        (VALUES 
            ('Sun', 0), 
            ('Mon', 1), 
            ('Tue', 2), 
            ('Wed', 3), 
            ('Thu', 4), 
            ('Fri', 5), 
            ('Sat', 6)
        ) AS dow(day_of_week, day_number),
        GENERATE_SERIES(0, 23) AS hr(hour_number)
),
count_data AS (
    SELECT
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 'Sun'
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 'Mon'
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 'Tue'
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 'Wed'
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 'Thu'
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 'Fri'
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 'Sat'
        END AS day_of_week,
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 0
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 1
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 2
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 3
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 4
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 5
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 6
        END AS day_number,
        LPAD(CAST(DATE_PART('hour', REPORTDATE) AS VARCHAR), 2, '0') AS hour_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
        AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                            AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
        AND AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                            WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                            THEN 119
                            ELSE ${inputs.max_age.value}
                        END
                    )
    GROUP BY day_of_week, day_number, hour_number
)
SELECT
    r.day_of_week,
    r.day_number,
    LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') AS hour_number,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON r.day_of_week = cd.day_of_week
 AND LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') = cd.hour_number
ORDER BY r.day_number, r.hour_number;
```

```sql time
WITH reference AS (
    SELECT hr.hour_number
    FROM GENERATE_SERIES(0, 23) AS hr(hour_number)
),
count_data AS (
    SELECT
        LPAD(CAST(DATE_PART('hour', REPORTDATE) AS VARCHAR), 2, '0') AS hour_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
        AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                            AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
        AND AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                            WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                            THEN 119
                            ELSE ${inputs.max_age.value}
                        END
                    )
    GROUP BY hour_number
)
SELECT
    'Total' AS Total,
    LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') AS hour_number,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') = cd.hour_number
ORDER BY r.hour_number;
```

```sql day
WITH reference AS (
    SELECT
        dow.day_of_week,
        dow.day_number,
        'Total' AS total
    FROM 
        (VALUES 
            ('Sun', 0), 
            ('Mon', 1), 
            ('Tue', 2), 
            ('Wed', 3), 
            ('Thu', 4), 
            ('Fri', 5), 
            ('Sat', 6)
        ) AS dow(day_of_week, day_number)
),
count_data AS (
    SELECT
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 'Sun'
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 'Mon'
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 'Tue'
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 'Wed'
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 'Thu'
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 'Fri'
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 'Sat'
        END AS day_of_week,
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 0
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 1
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 2
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 3
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 4
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 5
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 6
        END AS day_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
        AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                            AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
        AND AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                            WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                            THEN 119
                            ELSE ${inputs.max_age.value}
                        END
                    )
    GROUP BY day_of_week, day_number
)
SELECT
    r.day_of_week,
    r.day_number,
    r.total,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON r.day_of_week = cd.day_of_week
ORDER BY r.day_number;
```

```sql hex_map
SELECT
    h.GRID_ID,
    COALESCE(SUM(c.COUNT), 0) AS count,
    '/Crash-Injury-Dashboard/hexgrid/' || h.GRID_ID AS link
FROM hexgrid.crash_hexgrid h
LEFT JOIN crashes.crashes c 
    ON h.GRID_ID = c.GRID_ID
    AND c.MODE IN ${inputs.multi_mode_dd.value}
    AND c.SEVERITY IN ${inputs.multi_severity.value}
    AND c.REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
    AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND c.AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                            )
GROUP BY h.GRID_ID;
```

```sql hex_with_link
SELECT 
    h.*,
    COALESCE(i.count, 0) AS count,
    '/Crash-Injury-Dashboard/hexgrid/' || h.GRID_ID AS link
FROM ${hex} AS h
LEFT JOIN (
    SELECT 
        c.GRID_ID,
        SUM(c.COUNT) AS count
    FROM crashes.crashes c
    WHERE 
        c.MODE IN ${inputs.multi_mode_dd.value}
        AND c.SEVERITY IN ${inputs.multi_severity.value}
        AND c.REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
        AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
        AND c.AGE BETWEEN ${inputs.min_age.value}
                            AND (
                                CASE 
                                    WHEN ${inputs.min_age.value} <> 0 
                                    AND ${inputs.max_age.value} = 120
                                    THEN 119
                                    ELSE ${inputs.max_age.value}
                                END
                                )
    GROUP BY c.GRID_ID
) AS i
ON h.GRID_ID = i.GRID_ID;
```

```sql roadsegment_dropdown_a
SELECT DISTINCT roadsegment
FROM intersections.intersections
CROSS JOIN UNNEST(split(INTERSECTIONNAME, ' & ')) AS t(roadsegment);
```

```sql roadsegment_dropdown_b
SELECT DISTINCT t.roadsegment
FROM intersections.intersections
CROSS JOIN UNNEST(split(INTERSECTIONNAME, ' & ')) AS t(roadsegment)
WHERE INTERSECTIONNAME LIKE '%${inputs.roadsegment_a.value}%';
```

```sql intersections_table
SELECT
    INTERSECTIONNAME,
    '/hexgrid/' || GRID_ID AS link,
    split(INTERSECTIONNAME, ' & ') AS ROADSEGMENT
FROM intersections.intersections
WHERE array_position(split(INTERSECTIONNAME, ' & '), '${inputs.roadsegment_a.value}') IS NOT NULL
  AND array_position(split(INTERSECTIONNAME, ' & '), '${inputs.roadsegment_b.value}') IS NOT NULL
GROUP BY INTERSECTIONNAME, GRID_ID
LIMIT 5;
```

```sql mode_severity_selection
WITH
  -- 1. Get the total number of unique modes in the entire table
  total_modes_cte AS (
    SELECT
      COUNT(DISTINCT MODE) AS total_mode_count
    FROM
      crashes.crashes
  ),
  -- 2. Aggregate the modes, applying pluralization before aggregating
  mode_agg_cte AS (
    SELECT
      STRING_AGG(
        DISTINCT CASE
          -- If the mode ends with '*', insert 's' before it
          WHEN MODE LIKE '%*' THEN REPLACE(MODE, '*', 's*')
          -- Otherwise, just append 's'
          ELSE MODE || 's'
        END,
        ', '
        ORDER BY
          MODE ASC
      ) AS mode_list,
      COUNT(DISTINCT MODE) AS mode_count
    FROM
      crashes.crashes
    WHERE
      MODE IN ${inputs.multi_mode_dd.value}
  ),
  -- 3. Aggregate severities based on the INTERSECTION of both inputs
  severity_agg_cte AS (
    SELECT
      STRING_AGG(
        DISTINCT SEVERITY,
        ', '
        ORDER BY
          CASE SEVERITY
            WHEN 'Minor' THEN 1
            WHEN 'Major' THEN 2
            WHEN 'Fatal' THEN 3
          END
      ) AS severity_list,
      COUNT(DISTINCT SEVERITY) AS severity_count
    FROM
      crashes.crashes
    WHERE
      MODE IN ${inputs.multi_mode_dd.value}
      AND SEVERITY IN ${inputs.multi_severity.value}
  )
-- 4. Combine results and apply final formatting logic to each column
SELECT
  CASE
    WHEN mode_count = 0 THEN ' '
    WHEN mode_count = total_mode_count THEN 'All Road Users'
    WHEN mode_count = 1 THEN mode_list
    WHEN mode_count = 2 THEN REPLACE(mode_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(mode_list, ',([^,]+)$', ', and \\1')
  END AS MODE_SELECTION,
  CASE
    WHEN severity_count = 0 THEN ' '
    WHEN severity_count = 1 THEN severity_list
    WHEN severity_count = 2 THEN REPLACE(severity_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(severity_list, ',([^,]+)$', ', and \\1')
  END AS SEVERITY_SELECTION
FROM
  mode_agg_cte,
  severity_agg_cte,
  total_modes_cte;
```

<DateRange
  start="2017-01-01"
  end={
    (last_record && last_record[0] && last_record[0].end_date)
      ? `${last_record[0].end_date}`
      : (() => {
          const twoDaysAgo = new Date(new Date().setDate(new Date().getDate() - 2));
          return new Intl.DateTimeFormat('en-CA', {
            timeZone: 'America/New_York'
          }).format(twoDaysAgo);
        })()
  }
  name="date_range"
  presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year', 'All Time']}
  defaultValue="Year to Today"
  description="By default, there is a two-day lag after the latest update"
/>

<Dropdown
    data={unique_severity} 
    name=multi_severity
    value=SEVERITY
    title="Severity"
    multiple=true
    defaultValue={['Fatal', 'Major']}
/>

<Dropdown
    data={unique_mode} 
    name=multi_mode_dd
    value=MODE
    title="Road User"
    multiple=true
    selectAllByDefault=true
    description="*Only fatal"
/>

<Dropdown 
    data={age_range} 
    name=min_age
    value=age_int
    title="Min Age" 
    defaultValue={0}
/>

<Dropdown 
    data={age_range} 
    name="max_age"
    value=age_int
    title="Max Age"
    order="age_int desc"
    defaultValue={120}
    description='Age 120 serves as a placeholder for missing age values in the records. However, missing values will be automatically excluded from the query if the default 0-120 range is changed by the user. To get a count of missing age values, go to the "Age Distribution" page.'
/>

<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Heatmap of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} Injuries for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
        </div>
        <Note>
            Select a hexagon to zoom in and view more details about the injuries resulting from a crash within it.
        </Note>
        <BaseMap
            height=560
            startingZoom=12
        >
            <Areas data={hex_map} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/crash-hexgrid.geojson' geoId=GRID_ID areaCol=GRID_ID value=count link=link min=0 opacity=0.7 />
            <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00/ ignoreZoom=true 
            tooltip={[
                {id: 'ROUTENAME'}
            ]}
            />
        </BaseMap>
        <Note>
        The purple lines represent DC's High Injury Network  
        </Note>
    </Group>
    <Group>
        <div style="font-size: 14px;">
            <b>{`${mode_severity_selection[0].SEVERITY_SELECTION}`} Injuries for {`${mode_severity_selection[0].MODE_SELECTION}`} by Day of Week & Time of the Day</b>
        </div>
        <Heatmap
        data={day}
        subtitle=" "
        x="day_of_week" xSort="day_number"
        y="total"
        value="count"
        legend={true}
        valueLabels={true}
        mobileValueLabels={true}
        chartAreaHeight={50}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                const dayNames = {
                'Sun': 'Sunday','Mon': 'Monday','Tue': 'Tuesday',
                'Wed': 'Wednesday','Thu': 'Thursday','Fri': 'Friday','Sat': 'Saturday'
                };
                let dayAbbrev, count;
                if (params.value && Array.isArray(params.value)) {
                dayAbbrev = params.value[0];
                count      = params.value[2];
                } else {
                dayAbbrev = params.data.day_of_week;
                count     = params.data.count;
                }
                return `<strong>${dayNames[dayAbbrev]}</strong><br>Count: ${count}`;
            }
            }
        }}
        />
        <Heatmap
        data={day_time}
        subtitle="24-Hour Format"
        x="hour_number" xSort="hour_number"
        y="day_of_week" ySort="day_number"
        value="count"
        legend={true}
        filter={true}
        mobileValueLabels={true}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                const dayNames = {
                'Sun': 'Sunday','Mon': 'Monday','Tue': 'Tuesday',
                'Wed': 'Wednesday','Thu': 'Thursday','Fri': 'Friday','Sat': 'Saturday'
                };
                let hour, dayAbbrev, count;
                if (params.value && Array.isArray(params.value)) {
                hour      = params.value[0];
                dayAbbrev = params.value[1];
                count     = params.value[2];
                } else {
                hour      = params.data.hour_number;
                dayAbbrev = params.data.day_of_week;
                count     = params.data.count;
                }
                return `<strong>${dayNames[dayAbbrev]}</strong><br><strong>${hour} hrs</strong><br>Count: ${count}`;
            }
            }
        }}
        />
        <Heatmap
        data={time}
        subtitle="24-Hour Format"
        x="hour_number" xSort="hour_number"
        y="Total"
        value="count"
        legend={true}
        filter={true}
        chartAreaHeight={50}
        mobileValueLabels={true}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                let hour, count;
                if (params.value && Array.isArray(params.value)) {
                hour  = params.value[0];
                count = params.value[2];
                } else {
                hour  = params.data.hour_number;
                count = params.data.count;
                }
                return `<strong>${hour} hrs</strong><br>Count: ${count}`;
            }
            }
        }}
        />
    </Group>
</Grid>

<Grid cols=2>
    <Group>
        <div>
            <b>Intersection Search:</b>
        </div>
        <Dropdown 
            data={roadsegment_dropdown_a} 
            name=roadsegment_a
            value=roadsegment
            title="Select 1st Road" 
            defaultValue="13TH ST NW"
        />
        <Dropdown 
            data={roadsegment_dropdown_b} 
            name=roadsegment_b
            value=roadsegment
            title="Select 2nd Road" 
            defaultValue="PENNSYLVANIA AVE NW"
        />
        <DataTable data={intersections_table} rowShading=true rows=2 link=link downloadable=false>
                    <Column id=INTERSECTIONNAME title="Go to Selected Intersection:"/>
        </DataTable>
    </Group>
    <Group>
        <DataTable data={hex_with_link} title="Hexagon Ranking of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} Injuries for {`${mode_severity_selection[0].MODE_SELECTION}`}" search=true link=link rows=3 rowShading=true sort="count desc">
            <Column id=GRID_ID title="Hexagon ID"/>
            <Column id=count contentType=colorscale/>
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>