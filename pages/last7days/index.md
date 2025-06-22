---
title: Last 7 Days
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 6
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

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
```

```sql unique_dc
select 
    CITY_NAME
from dc_boundary.dc_boundary
group by 1
```

```sql inc_map
WITH latest AS (
    SELECT 
        MAX(REPORTDATE) AS raw_end_date,
        date_trunc('day', MAX(REPORTDATE)) AS end_date
    FROM crashes.crashes
),
date_range AS (
    SELECT 
    (end_date - INTERVAL '6 day') AS start_date,
    end_date,
    (end_date + INTERVAL '1 day') AS end_date_exclusive
    FROM latest
),
dates AS (
    SELECT day 
    FROM date_range,
        generate_series(start_date, end_date, INTERVAL '1 day') AS t(day)
),
filtered_crashes AS (
    SELECT 
        c.*,
        date_trunc('day', c.REPORTDATE) AS crash_day
    FROM crashes.crashes c
    JOIN date_range d
    ON c.REPORTDATE >= d.start_date 
        AND c.REPORTDATE < d.end_date_exclusive
    WHERE c.MODE IN ${inputs.multi_mode_dd.value}
    AND c.SEVERITY IN ${inputs.multi_severity.value}
    AND c.AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                            )
)
SELECT 
    d.day,
    COALESCE(fc.REPORTDATE, d.day) AS REPORTDATE,
    STRFTIME('%m/%d %a', d.day) AS WEEKDAY,
    COALESCE(fc.LATITUDE, 0) AS LATITUDE,
    COALESCE(fc.LONGITUDE, 0) AS LONGITUDE,
    SUBSTRING(fc.MODE, 1, 3) || '-' || SUBSTRING(fc.SEVERITY, 1) AS MODESEV,
    fc.ADDRESS,
    fc.GRID_ID,
    CASE
        WHEN CAST(fc.AGE AS INTEGER) = 120 THEN '-'
        ELSE CAST(CAST(fc.AGE AS INTEGER) AS VARCHAR)
    END AS AGE,
    COALESCE(fc.COUNT, 0) AS COUNT
FROM dates d
LEFT JOIN filtered_crashes fc
    ON fc.crash_day = d.day
ORDER BY d.day DESC;
```

```sql mode_severity_selection
SELECT
    STRING_AGG(DISTINCT MODE, ', ' ORDER BY MODE ASC) AS MODE_SELECTION,
    STRING_AGG(DISTINCT SEVERITY, ', ' ORDER BY SEVERITY ASC) AS SEVERITY_SELECTION
FROM
    crashes.crashes
WHERE
    MODE IN ${inputs.multi_mode_dd.value}
    AND SEVERITY IN ${inputs.multi_severity.value};
```

The last 7 days with available data range from <Value data={inc_map} column="WEEKDAY" agg="min"/> to <Value data={inc_map} column="WEEKDAY" agg="max" />

<Dropdown
    data={unique_severity} 
    name=multi_severity
    value=SEVERITY
    title="Select Severity"
    multiple=true
    defaultValue={["Major","Fatal"]}
/>

<Dropdown
    data={unique_mode} 
    name=multi_mode_dd
    value=MODE
    title="Select Road User"
    multiple=true
    selectAllByDefault=true
    description="*Only fatal"
/>

<Dropdown 
    data={age_range} 
    name=min_age
    value=age_int
    title="Select Min Age" 
    defaultValue={0}
/>

<Dropdown 
    data={age_range} 
    name="max_age"
    value=age_int
    title="Select Max Age"
    order="age_int desc"
    defaultValue={120}
    description='Age 120 serves as a placeholder for missing age values in the records. However, missing values will be automatically excluded from the query if the default 0-120 range is changed by the user. To get a count of missing age values, go to the "Age Distribution" page.'
/>

<Alert status="info">
The selection for <b>Severity</b> is: <b><Value data={mode_severity_selection} column="SEVERITY_SELECTION"/></b>. The selection for <b>Road User</b> is: <b><Value data={mode_severity_selection} column="MODE_SELECTION"/></b> <Info description="*Fatal only." color="primary" />
</Alert>

<Grid cols=2>
    <Group>
        <Note>
            Each point on the map represents an injury. Injury incidents can overlap in the same spot.
        </Note>
        <BaseMap
            height=450
            startingZoom=11
        >
            <Points data={inc_map} lat=LATITUDE long=LONGITUDE pointName=MODE value=WEEKDAY ignoreZoom=true colorPalette={['#595cff','#6b76ff','#7d90ff','#90aaff','#a2c4ff','#b4deff','#c6f8ff']}
            tooltip={[
                {id:'MODESEV', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'day', showColumnName:false, fmt:'mm/dd/yy'},
                {id:'ADDRESS', showColumnName:false, fmt:'id'}
            ]}
            />
            <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00/ ignoreZoom=true borderWidth=1.2
            tooltip={[
                {id: 'ROUTENAME'}
            ]}
            />
            <Areas data={unique_dc} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/dc_boundary.geojson' geoId=CITY_NAME areaCol=CITY_NAME opacity=0.5 borderColor=#000000 color=#1C00ff00/ 
            />
        </BaseMap>
        <Note>
            The purple lines represent DC's High Injury Network
        </Note>
    </Group>
    <Group>
        <DataTable data={inc_map} wrapTitles=true rowShading=true groupBy=WEEKDAY subtotals=true sort="WEEKDAY desc" totalRow=true accordionRowColor="#D3D3D3">
            <Column id=REPORTDATE title="Date" fmt='hh:mm' wrap=true totalAgg="Total"/>
            <Column id=MODESEV title="Road User - Sev" wrap=true/>
            <Column id=AGE title="Age" wrap=true totalAgg="-"/>
            <Column id=ADDRESS title="Approx Address" wrap=true/>
            <Column id=COUNT title="#" wrap=true/>
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>