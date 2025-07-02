---
title: Traffic Fatalities
queries:
   - fatality: fatality.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 1
---

<Details title="About this dashboard">

    This dashboard shows traffic fatalities in the District of Columbia and can be filtered from 2017-present. Following a fatal crash, the DDOT team visits the site and, in coordination with The Metropolitan Police Department's (MPD) Major Crash Investigation Unit, determines if there are any short-term measures that DDOT can install to improve safety for all roadway users. Starting in 2021, site visit findings and follow-up can be found in the docked window on the right for each fatality.
    
    Adjust the selection for Road User, Date Range, and Age filters to refine the results in the map nad table. All charts will update to reflect the fatalities affected by the filters. 
    
    Data are updated twice: first, as soon as the Vision Zero Office receives a fatality memo from the Metropolitan Police Department (MPD) and second, after a crash site visit has been completed by DDOT.

</Details>

```sql fatality_with_link
select *, '/fatalities/' || OBJECTID as link
from ${fatality}
```

```sql unique_mode
SELECT 
    replace(MODE, '*', '') AS MODE,
FROM crashes.crashes
GROUP BY 1
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

```sql yoy_text_fatal
WITH date_range AS (
    SELECT
        MAX(REPORTDATE)::DATE + INTERVAL '1 day' AS max_report_date
    FROM
        crashes.crashes
),
params AS (
    SELECT
        date_trunc('year', dr.max_report_date) AS current_year_start,
        dr.max_report_date AS current_year_end,
        date_trunc('year', dr.max_report_date - interval '1 year') AS prior_year_start,
        dr.max_report_date - interval '1 year' AS prior_year_end,
        extract(year FROM dr.max_report_date) AS current_year,
        extract(year FROM dr.max_report_date - interval '1 year') AS year_prior
    FROM
        date_range dr
),
yearly_counts AS (
    SELECT
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.current_year_start AND p.current_year_end
            THEN cr.COUNT ELSE 0 END) AS current_year_sum,
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.prior_year_start AND p.prior_year_end
            THEN cr.COUNT ELSE 0 END) AS prior_year_sum
    FROM
        crashes.crashes AS cr
        CROSS JOIN params p
    WHERE
        cr.SEVERITY = 'Fatal'
        AND cr.REPORTDATE >= p.prior_year_start -- More efficient date filtering
        AND cr.REPORTDATE <= p.current_year_end
)
SELECT
    'Fatal' AS severity,
    yc.current_year_sum,
    yc.prior_year_sum,
    ABS(yc.current_year_sum - yc.prior_year_sum) AS difference,
    CASE
        WHEN yc.prior_year_sum <> 0
        THEN ((yc.current_year_sum - yc.prior_year_sum)::numeric / yc.prior_year_sum)
        ELSE NULL
    END AS percentage_change,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'an increase of'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'a decrease of'
        ELSE NULL
    END AS percentage_change_text,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'more'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'fewer'
        ELSE 'no change'
    END AS difference_text,
    p.current_year,
    p.year_prior,
    CASE WHEN yc.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN yc.current_year_sum = 1 THEN 'fatality' ELSE 'fatalities' END AS fatality
FROM
    yearly_counts yc
    CROSS JOIN params p;
```

```sql inc_map
SELECT
    REPORTDATE,
    LATITUDE,
    LONGITUDE,
    replace(MODE, '*', '') AS MODE,
    SEVERITY,
    ADDRESS,
    CCN,
    replace(MODE, '*', '') || ' - ' || CCN AS mode_ccn,
    CASE
        WHEN CAST(AGE AS INTEGER) = 120 THEN '-'
        ELSE CAST(CAST(AGE AS INTEGER) AS VARCHAR)
    END AS Age,
    '/fatalities/' || OBJECTID AS link
FROM crashes.crashes
WHERE replace(MODE, '*', '') IN ${inputs.multi_mode_dd.value}
AND SEVERITY = 'Fatal'
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
GROUP BY all;
```

```sql mode_selection
WITH
  -- 0. Normalize mode values by removing '*' suffix
  clean_modes AS (
    SELECT
      REPLACE(MODE, '*', '') AS mode_clean
    FROM crashes.crashes
  ),

  -- 1. Count distinct cleaned modes in the entire table
  total_modes_cte AS (
    SELECT
      COUNT(DISTINCT mode_clean) AS total_mode_count
    FROM clean_modes
  ),

  -- 2. Aggregate the cleaned modes, always appending 's'
  mode_agg_cte AS (
    SELECT
      STRING_AGG(
        DISTINCT mode_clean || 's',
        ', '
        ORDER BY mode_clean
      ) AS mode_list,
      COUNT(DISTINCT mode_clean) AS mode_count
    FROM clean_modes
    WHERE mode_clean IN ${inputs.multi_mode_dd.value}
  )

-- 3. Final formatting logic
SELECT
  CASE
    WHEN mode_count = 0 THEN ' '
    WHEN mode_count = total_mode_count THEN 'All Road Users'
    WHEN mode_count = 1 THEN mode_list
    WHEN mode_count = 2 THEN REPLACE(mode_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(mode_list, ',([^,]+)$', ', and \\1')
  END AS MODE_SELECTION
FROM
  mode_agg_cte,
  total_modes_cte;
```

As of <Value data={last_record} column="latest_record"/> there <Value data={yoy_text_fatal} column="has_have"/> been <Value data={yoy_text_fatal} column="current_year_sum" agg=sum/> <Value data={yoy_text_fatal} column="fatality"/> among all road users in <Value data={yoy_text_fatal} column="current_year" fmt='####","'/>   <Value data={yoy_text_fatal} column="difference" agg=sum fmt='####' /> <Value data={yoy_text_fatal} column="difference_text"/> (<Delta data={yoy_text_fatal} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the same period in <Value data={yoy_text_fatal} column="year_prior" fmt="####."/>

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
  presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year']}
  defaultValue="Year to Today"
  description="By default, there is a two-day lag after the latest update"
/>

<Dropdown
    data={unique_mode} 
    name=multi_mode_dd
    value=MODE
    title="Road User"
    multiple=true
    selectAllByDefault=true
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
            <b>Map of Fatalities for {`${mode_selection[0].MODE_SELECTION}`}</b>
        </div>
        <Note>
            Each point on the map represents an fatality. Fatality incidents can overlap in the same spot.
        </Note>
        <BaseMap
            height=450
            startingZoom=11
        >
            <Points data={inc_map} lat=LATITUDE long=LONGITUDE pointName=MODE value=SEVERITY colorPalette={['#ff5a53']} ignoreZoom=true
            tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'CCN',showColumnName:false, fmt:'id'},
                {id:'REPORTDATE', showColumnName:false, fmt:'mm/dd/yy hh:mm'},
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
        <div style="font-size: 14px;">
            <b>Table of Fatalities for {`${mode_selection[0].MODE_SELECTION}`}</b>
        </div>
        <Note class='text-sm'>
            Select a fatality in the table to see more details about it and the post-crash follow-up.
        </Note>
        <DataTable data={inc_map} link=link wrapTitles=true rowShading=true search=true rows=8>
            <Column id=REPORTDATE title="Date" fmt='mm/dd/yy hh:mm' wrap=true/>
            <Column id=mode_ccn title="Road User - CCN" wrap=true/>
            <Column id=Age/>
            <Column id=ADDRESS wrap=true/>
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>
