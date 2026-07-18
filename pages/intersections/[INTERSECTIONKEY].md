---
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
---

<script>
  // Filters arrive in the query string from the top-10 table on /intersections.
  // Do NOT import page -- Evidence's page template already declares it.
  const csv = (v, fallback) => (v ? v.split(',').map((s) => s.trim()) : fallback);

  $: qp      = $page.url.searchParams;
  $: dSev    = csv(qp.get('severity'), ['Fatal', 'Major', 'Minor']);
  $: dMode   = csv(qp.get('mode'), null);
  $: dMinAge = qp.get('min_age') ? Number(qp.get('min_age')) : 0;
  $: dMaxAge = qp.get('max_age') ? Number(qp.get('max_age')) : 120;
  $: dStart  = qp.get('start') ?? '2017-01-01';
  $: dEnd    = qp.get('end');
</script>

# <Value data={intx_info} column=INTERSECTION_NAME/>

```sql unique_mode
select MODE from crashes.crashes group by 1
```

```sql unique_severity
select SEVERITY from crashes.crashes group by 1
```

```sql unique_hin
select GIS_ID, ROUTENAME from hin.hin group by all
```

```sql intx_info
SELECT INTERSECTIONKEY, canonical_name AS INTERSECTION_NAME
FROM intersections.intersections_unique
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
```

```sql crashes_all
SELECT REPORTDATE, MODE, SEVERITY, CCN, ADDRESS, LATITUDE, LONGITUDE,
    CASE WHEN TRY_CAST(AGE AS INTEGER) = 120 THEN NULL ELSE TRY_CAST(AGE AS INTEGER) END AS Age,
    DIST_TO_INTX_FT
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
ORDER BY SEVERITY, REPORTDATE DESC
```

```sql crashes_fatal
SELECT REPORTDATE, MODE, SEVERITY, CCN, ADDRESS, LATITUDE, LONGITUDE
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY = 'Fatal'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
```

```sql crashes_major
SELECT REPORTDATE, MODE, SEVERITY, CCN, ADDRESS, LATITUDE, LONGITUDE
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY = 'Major'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
```

```sql crashes_minor
SELECT REPORTDATE, MODE, SEVERITY, CCN, ADDRESS, LATITUDE, LONGITUDE
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY = 'Minor'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
```

<DateRange
start={dStart}
end={
    dEnd
    ? dEnd
    : (last_record && last_record[0] && last_record[0].end_date)
      ? `${last_record[0].end_date}`
      : (() => {
        const twoDaysAgo = new Date(new Date().setDate(new Date().getDate() - 2));
        return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(twoDaysAgo);
        })()
}
name="date_range"
presetRanges={['Last 30 Days', 'Last 12 Months', 'Year to Today', 'Last Year', 'All Time']}
defaultValue="Year to Today"
/>

<Dropdown data={unique_severity} name="multi_severity" value="SEVERITY" title="Severity" multiple={true} defaultValue={dSev}/>

<Dropdown data={unique_mode} name=multi_mode_dd value=MODE title="Road User" multiple=true defaultValue={dMode ?? undefined} selectAllByDefault={dMode === null} description="*Only fatal"/>

<Dropdown data={age_range} name=min_age value=age_int title="Min Age" defaultValue={dMinAge}/>

<Dropdown data={age_range} name="max_age" value=age_int title="Max Age" order="age_int desc" defaultValue={dMaxAge}/>

<Grid cols=2>
    <Group>
        <BaseMap height=420 startingZoom=18 title="Crashes at This Intersection">
        <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
            tooltip={[{id: 'ROUTENAME', showColumnName:false}]}
        />
        <Areas data={intx_info} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/Intersection_Points_buffers.geojson' geoId=INTERSECTIONKEY areaCol=INTERSECTIONKEY color=#1C00ff00 borderColor='#A9A9A9' borderWidth=2
            tooltip={[{id:'INTERSECTION_NAME', valueClass:'text-l font-semibold', showColumnName:false}]}
        />
        <Points data={crashes_minor} lat=LATITUDE long=LONGITUDE color='#ffdf00' pointName=MODE opacity=0.6 ignoreZoom=true
            tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'SEVERITY', showColumnName:false, fmt:'id'},
                {id:'CCN', showColumnName:false, fmt:'id'},
                {id:'REPORTDATE', showColumnName:false, fmt:'mm/dd/yy hh:mm'},
                {id:'ADDRESS', showColumnName:false, fmt:'id'}
            ]}
        />
        <Points data={crashes_major} lat=LATITUDE long=LONGITUDE color='#ff9412' pointName=MODE opacity=0.6 ignoreZoom=true
            tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'SEVERITY', showColumnName:false, fmt:'id'},
                {id:'CCN', showColumnName:false, fmt:'id'},
                {id:'REPORTDATE', showColumnName:false, fmt:'mm/dd/yy hh:mm'},
                {id:'ADDRESS', showColumnName:false, fmt:'id'}
            ]}
        />
        <Points data={crashes_fatal} lat=LATITUDE long=LONGITUDE color='#ff5a53' pointName=MODE opacity=0.6 ignoreZoom=true
            tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'SEVERITY', showColumnName:false, fmt:'id'},
                {id:'CCN', showColumnName:false, fmt:'id'},
                {id:'REPORTDATE', showColumnName:false, fmt:'mm/dd/yy hh:mm'},
                {id:'ADDRESS', showColumnName:false, fmt:'id'}
            ]}
        />
        </BaseMap>
        <Note>
            The circle is this intersection's 100 ft buffer. Points are crashes assigned to it, colored by severity. Purple lines are DC's High Injury Network.
        </Note>
    </Group>
    <Group>
        {#if crashes_all.length > 0}
        <DataTable data={crashes_all} rows=12 search=true rowShading=true wrapTitles=true title="Injury Crashes">
            <Column id=REPORTDATE title="Date" fmt='mm/dd/yy hh:mm' wrap=true/>
            <Column id=MODE title="Road User" wrap=true/>
            <Column id=SEVERITY title="Severity"/>
            <Column id=Age/>
            <Column id=CCN title="CCN"/>
            <Column id=DIST_TO_INTX_FT title="Dist (ft)" fmt='#,##0'/>
        </DataTable>
        {:else}
        <Note>
            No injury crashes at this intersection for the selected filters.
        </Note>
        {/if}
    </Group>
</Grid>