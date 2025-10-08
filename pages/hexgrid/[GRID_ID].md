---
queries:
   - hex: hex.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
---

# Selected Hexagon

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
where GRID_ID = '${params.GRID_ID}'
group by 1
```

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
```

```sql table_query
SELECT
    REPORTDATE,
    MODE || '-' || SEVERITY AS mode_severity,
    ADDRESS,
    CASE
        WHEN CAST(AGE AS INTEGER) = 120 THEN '-'
        ELSE CAST(CAST(AGE AS INTEGER) AS VARCHAR)
    END AS Age,
    CCN,
    SUM(COUNT) AS Count
FROM crashes.crashes
WHERE MODE IN ${inputs.multi_mode_dd.value}
AND GRID_ID = '${params.GRID_ID}'
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
GROUP BY
    REPORTDATE,
    MODE,
    SEVERITY,
    ADDRESS,
    CCN,
    AGE;
```

```sql incidents
SELECT
    'CCN-' || CAST(CCN AS VARCHAR) AS CCN,
    MODE,
    SEVERITY,
    ADDRESS,
    REPORTDATE,
    LATITUDE,
    LONGITUDE,
    SUM(COUNT) AS Count
FROM crashes.crashes
WHERE MODE IN ${inputs.multi_mode_dd.value}
AND SEVERITY IN ${inputs.multi_severity.value}
AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
AND AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                            WHEN ${inputs.min_age.value} <> 0 
                            AND ${inputs.max_age.value} = 120
                            THEN 119
                            ELSE ${inputs.max_age.value}
                        END
                        )
GROUP BY
    CCN,
    MODE,
    SEVERITY,
    ADDRESS,
    REPORTDATE,
    LATITUDE,
    LONGITUDE;
```

```sql intersection_list
SELECT INTERSECTIONNAME
FROM intersections.intersections
WHERE GRID_ID = '${params.GRID_ID}'

UNION ALL

SELECT 'There are no intersections within the hexagon'
WHERE NOT EXISTS (
    SELECT 1 
    FROM intersections.intersections 
    WHERE GRID_ID = '${params.GRID_ID}'
);
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

<Grid cols=2>
    <Group>
        <DataTable data={intersection_list}>
                <Column id=INTERSECTIONNAME title='Intersections Within {params.GRID_ID}' wrap=true/>
        </DataTable>
    </Group>
    <Group>
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
            defaultValue={["Major","Fatal"]}
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
    </Group>
</Grid>

<Alert status="info">
The selection for <b>Severity</b> is: <b><Value data={mode_severity_selection} column="SEVERITY_SELECTION"/></b>. The selection for <b>Road User</b> is: <b><Value data={mode_severity_selection} column="MODE_SELECTION"/></b> <Info description="*Fatal only." color="primary" />
</Alert>

### Selected Hexagon

<Grid cols=2>
    <Group>
        <Note>
        Each point on the map represents an injury. Injury incidents can overlap in the same spot.
        </Note>
        <BaseMap
          height=400
          startingZoom=17
        >
          <Points data={incidents} lat=LATITUDE long=LONGITUDE value=SEVERITY pointName=MODE opacity=1 colorPalette={['#ffdf00','#ff9412','#ff5a53']} ignoreZoom=true             
          tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'REPORTDATE', showColumnName:false, fmt:'mm/dd/yy hh:mm'},
                {id:'ADDRESS', showColumnName:false, fmt:'id'},
                {id:'CCN', showColumnName:false, fmt:'CCN'},
                {id:'Count'}
            ]}/>
          <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00/ borderWidth=1.5 ignoreZoom=true
          tooltip={[
                {id: 'ROUTENAME'}
            ]}
          />
          <Areas data={unique_hex} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/crash-hexgrid.geojson' geoId=GRID_ID areaCol=GRID_ID min=0 borderColor=#000000 color=#1C00ff00/>
        </BaseMap>
        <Note>
        The purple lines represent DC's High Injury Network
        </Note>
    </Group>    
    <Group>
        <DataTable data={table_query} sort="REPORTDATE desc" totalRow=true rows=5 title='Injury Table' rowShading=true wrapTitles=true>
          <Column id=REPORTDATE title='Date' fmt='mm/dd/yy hh:mm' totalAgg="Total" wrap=true description="24-Hour Format"/>
          <Column id=Count totalAgg=sum/>
          <Column id=mode_severity title='Road User - Severity' totalAgg="-" wrap=true/>
          <Column id=Age totalAgg="-"/>
          <Column id=ADDRESS title='Apporx Address' wrap=true/>
          <Column id=CCN title="CCN" totalAgg="-"/>
        </DataTable>
        <Alert status="info">
            To navigate to another hexagon, go back to: <b><a href="https://crash-injury-dashboard.evidence.app/hexgrid/">Injuries Heatmap</a></b>.
        </Alert>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>