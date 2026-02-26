---
title: Traffic Fatalities
queries:
   - fatality: fatality.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
sidebar_position: 1
---

```sql fatality_with_link
select *, '/fatalities/' || DeathCaseID as link
from ${fatality}
```

```sql unique_mode
SELECT 
    replace(MODE, '*', '') AS MODE,
FROM crashes.crashes
GROUP BY 1
```

```sql Impairment
WITH categories AS (
    SELECT * FROM (VALUES 
        ('Yes'),
        ('No'),
        ('Unknown')
    ) AS t(SuspectedImpaired)
),
filtered AS (
    SELECT
        UPPER(substr(SuspectedImpaired, 1, 1)) || LOWER(substr(SuspectedImpaired, 2)) AS SuspectedImpaired,
        COUNT AS Count
    FROM crashes.crashes
    WHERE replace(MODE, '*', '') IN ${inputs.multi_mode_dd.value}
      AND SEVERITY = 'Fatal'
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
)
SELECT
    'Suspected Impairment*' AS Impairment,
    c.SuspectedImpaired,
    COALESCE(SUM(f.Count), 0) AS Count
FROM categories c
LEFT JOIN filtered f
    ON c.SuspectedImpaired = f.SuspectedImpaired
GROUP BY c.SuspectedImpaired
ORDER BY c.SuspectedImpaired;
```

```sql Speeding
WITH categories AS (
    SELECT * FROM (VALUES 
        ('Yes'),
        ('No'),
        ('Unknown')
    ) AS t(SuspectedSpeeding)
),
filtered AS (
    SELECT
        UPPER(substr(SuspectedSpeeding, 1, 1)) || LOWER(substr(SuspectedSpeeding, 2)) AS SuspectedSpeeding,
        COUNT AS Count
    FROM crashes.crashes
    WHERE replace(MODE, '*', '') IN ${inputs.multi_mode_dd.value}
      AND SEVERITY = 'Fatal'
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
)
SELECT
    'Suspected Speeding** ' AS Speeding,
    c.SuspectedSpeeding,
    COALESCE(SUM(f.Count), 0) AS Count
FROM categories c
LEFT JOIN filtered f
    ON c.SuspectedSpeeding = f.SuspectedSpeeding
GROUP BY c.SuspectedSpeeding
ORDER BY c.SuspectedSpeeding;
```

```sql HitAndRun
WITH categories AS (
    SELECT * FROM (VALUES 
        ('Yes'),
        ('No'),
        ('Unknown')
    ) AS t(HitAndRun)
),
filtered AS (
    SELECT
        UPPER(substr(HitAndRun, 1, 1)) || LOWER(substr(HitAndRun, 2)) AS HitAndRun,
        COUNT AS Count
    FROM crashes.crashes
    WHERE replace(MODE, '*', '') IN ${inputs.multi_mode_dd.value}
      AND SEVERITY = 'Fatal'
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
)
SELECT
    'Hit-and-Run                  ' AS HitAndRunLabel,
    c.HitAndRun,
    COALESCE(SUM(f.Count), 0) AS Count
FROM categories c
LEFT JOIN filtered f
    ON c.HitAndRun = f.HitAndRun
GROUP BY c.HitAndRun
ORDER BY c.HitAndRun;
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
        CASE
            -- First week of any year → freeze to last year's final date
            WHEN extract(month FROM current_date) = 1
             AND extract(day FROM current_date) <= 9
            THEN (date_trunc('year', current_date) - INTERVAL '1 day')::DATE
            -- Normal freeze logic: yesterday unless data is already current
            WHEN MAX(LAST_RECORD)::date = (current_date - INTERVAL '1 day')
                THEN MAX(LAST_RECORD)::date
            ELSE MAX(LAST_RECORD)::date + INTERVAL '1 day'
        END AS max_report_date
    FROM crashes.crashes
),
-- Count Fatal crashes in the current year (based on frozen date)
fatal_counts AS (
    SELECT
        SUM(c.COUNT) AS fatal_this_year
    FROM crashes.crashes c
    CROSS JOIN date_range dr
    WHERE c.SEVERITY = 'Fatal'
      AND EXTRACT(YEAR FROM c.REPORTDATE) = EXTRACT(YEAR FROM dr.max_report_date)
),
params AS (
    SELECT
        date_trunc('year', dr.max_report_date) AS current_year_start,
        dr.max_report_date AS current_year_end,
        date_trunc('year', dr.max_report_date - interval '1 year') AS prior_year_start,
        dr.max_report_date - interval '1 year' AS prior_year_end,
        extract(year FROM dr.max_report_date) AS current_year,
        extract(year FROM dr.max_report_date - interval '1 year') AS year_prior,
        -- inFirstWeek OR noFatalThisYear
        CASE
            WHEN (
                -- First week of data: Jan 1–9
                (extract(month FROM current_date) = 1 AND extract(day FROM current_date) <= 9)
                OR
                -- Fallback: no Fatal crashes yet this year
                (SELECT fatal_this_year FROM fatal_counts) = 0
            )
            THEN TRUE
            ELSE FALSE
        END AS is_first_week
    FROM date_range dr
),
yearly_counts AS (
    SELECT
        SUM(CASE WHEN cr.REPORTDATE BETWEEN p.current_year_start AND p.current_year_end
                 THEN cr.COUNT ELSE 0 END) AS current_year_sum,
        SUM(CASE WHEN cr.REPORTDATE BETWEEN p.prior_year_start AND p.prior_year_end
                 THEN cr.COUNT ELSE 0 END) AS prior_year_sum
    FROM crashes.crashes AS cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.prior_year_start
      AND cr.REPORTDATE <= p.current_year_end
)
SELECT
    'Fatal' AS severity,
    yc.current_year_sum,
    yc.prior_year_sum,
    ABS(yc.current_year_sum - yc.prior_year_sum) AS difference,
    CASE WHEN yc.prior_year_sum <> 0
         THEN ((yc.current_year_sum - yc.prior_year_sum)::numeric / yc.prior_year_sum)
         ELSE NULL END AS percentage_change,
    CASE WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'an increase of'
         WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'a decrease of'
         ELSE NULL END AS percentage_change_text,
    CASE WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'more'
         WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'fewer'
         ELSE 'no change' END AS difference_text,
    p.current_year,
    p.year_prior,
    CASE WHEN yc.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN yc.current_year_sum = 1 THEN 'fatality' ELSE 'fatalities' END AS fatality,
    strftime(p.current_year_end, '%m/%d/%y') AS max_report_date_formatted,
    p.is_first_week
FROM yearly_counts yc
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
    DeathCaseID,
    replace(MODE, '*', '') || '-' || CCN || ' ' || DeathCaseID AS mode_ccn,
    CASE
        WHEN CAST(AGE AS INTEGER) = 120 THEN '-'
        ELSE CAST(CAST(AGE AS INTEGER) AS VARCHAR)
    END AS Age,
    '/fatalities/' || DeathCaseID AS link
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

<ul class="markdown">
  {#if yoy_text_fatal[0].is_first_week}
    <li>
      In <Value data={yoy_text_fatal} column="current_year" fmt="####"/> there
      were <Value data={yoy_text_fatal} column="current_year_sum" agg=sum/>
      <Value data={yoy_text_fatal} column="fatality"/>
      among all road users,
      <Value data={yoy_text_fatal} column="difference" agg=sum fmt="####"/>
      <Value data={yoy_text_fatal} column="difference_text"/>
      (<Delta
        data={yoy_text_fatal}
        column="percentage_change"
        fmt="+0%;-0%;0%"
        downIsGood={true}
      />)
      compared to the same period in
      <Value data={yoy_text_fatal} column="year_prior" fmt="####."/>
    </li>
  {:else}
    <li>
      As of
      <Value data={yoy_text_fatal} column="max_report_date_formatted"/> there
      <Value data={yoy_text_fatal} column="has_have"/> been
      <Value data={yoy_text_fatal} column="current_year_sum" agg=sum/>
      <Value data={yoy_text_fatal} column="fatality"/>
      among all road users in
      <Value data={yoy_text_fatal} column="current_year" fmt='####","'/>
      <Value data={yoy_text_fatal} column="difference" agg=sum fmt="####"/>
      <Value data={yoy_text_fatal} column="difference_text"/>
      (<Delta
        data={yoy_text_fatal}
        column="percentage_change"
        fmt="+0%;-0%;0%"
        downIsGood={true}
      />)
      compared to the same period in
      <Value data={yoy_text_fatal} column="year_prior" fmt="####."/>
    </li>
  {/if}
</ul>

<DateRange
  start="2014-01-01"
  end={
    (last_record && last_record[0] && last_record[0].end_date)
      ? (() => {
          const fmt = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'America/New_York'
          });
          // Parse YYYY-MM-DD string explicitly
          const [year, month, day] = last_record[0].end_date.split('-').map(Number);
          const recordDate = new Date(year, month - 1, day);
          // Compute yesterday
          const yesterday = new Date();
          yesterday.setDate(yesterday.getDate() - 1);
          const recordStr = fmt.format(recordDate);
          const yesterdayStr = fmt.format(yesterday);
          if (recordStr === yesterdayStr) {
            // If record date is yesterday, just return it
            return recordStr;
          } else {
            // Otherwise add one day
            const plusOne = new Date(year, month - 1, day + 1);
            return fmt.format(plusOne);
          }
        })()
      : (() => {
          const twoDaysAgo = new Date();
          twoDaysAgo.setDate(twoDaysAgo.getDate() - 2);
          return new Intl.DateTimeFormat('en-CA', {
            timeZone: 'America/New_York'
          }).format(twoDaysAgo);
        })()
  }
  name="date_range"
  presetRanges={[
    'Last 7 Days',
    'Last 30 Days',
    'Last 90 Days',
    'Last 6 Months',
    'Last 12 Months',
    'Month to Today',
    'Last Month',
    'Year to Today',
    'Last Year'
  ]}
  defaultValue={
    (() => {
      const fmt = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'America/New_York'
      });
      // Get today's date in ET as YYYY-MM-DD
      const todayStr = fmt.format(new Date());
      const [year, month, day] = todayStr.split('-').map(Number);
      // First week of the year = Jan 1–9 (ET)
      const inFirstWeek = (month === 1 && day <= 9);
      // Fatal count from fatal count query
      const noFatalThisYear = (has_fatal[0].f_count === 0);
      // If first week OR no fatal data → show Last Year
      // Only show YTD when BOTH are false
      const showLastYear = inFirstWeek || noFatalThisYear;
      return showLastYear ? 'Last Year' : 'Year to Today';
    })()
  }
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
            height=420
            startingZoom=11
        >
            <Points data={inc_map} lat=LATITUDE long=LONGITUDE pointName=MODE value=SEVERITY colorPalette={['#ff5a53']} ignoreZoom=true
            tooltip={[
                {id:'MODE', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
                {id:'DeathCaseID', showColumnName:false, fmt:'id'},
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
        <DataTable data={inc_map} link=link wrapTitles=true rowShading=true search=true rows=5>
            <Column id=REPORTDATE title="Date" fmt='mm/dd/yy hh:mm' wrap=true/>
            <Column id=mode_ccn title="Road User - CCN - Case" wrap=true/>
            <Column id=Age/>
            <Column id=ADDRESS wrap=true/>
        </DataTable>
        <BarChart 
          data={Impairment}
          chartAreaHeight=45
          x=Impairment
          y=Count
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=SuspectedImpaired
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10} 
          seriesOrder={['Yes','No','Unknown']}
          seriesColors={{'Yes': '#f95738','No': '#0d3b66','Unknown': '#faf0ca'}}
        />
        <BarChart 
          data={Speeding}
          chartAreaHeight=30
          x=Speeding
          y=Count
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=SuspectedSpeeding
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10} 
          legend=false
          yAxisLabels=false
          seriesOrder={['Yes','No','Unknown']}
          seriesColors={{'Yes': '#f95738','No': '#0d3b66','Unknown': '#faf0ca'}}
        />
        <BarChart 
          data={HitAndRun}
          chartAreaHeight=30
          x=HitAndRunLabel
          y=Count
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=HitAndRun
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10} 
          legend=false
          yAxisLabels=false
          seriesOrder={['Yes','No','Unknown']}
          seriesColors={{'Yes': '#f95738','No': '#0d3b66','Unknown': '#faf0ca'}}
        />
    </Group>
</Grid>

<Note>
    *The determination of "Suspected Impairment" is preliminary. It may apply to either party involved in a crash. If the crash is handled by USPP, the determination is set as "Unknown". If the crash is a hit-and-run, the determination is also set as "Unknown".
</Note>
<Note>
    **The determination of "Suspected Speeding" is preliminary. It may apply to either party involved in a crash. If the crash is handled by USPP, the determination is set as "Unknown".
</Note>
<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>

<Details title="About this dashboard">

    This dashboard shows traffic fatalities in the District of Columbia and can be filtered from 2017-present. Following a fatal crash, the DDOT team visits the site and, in coordination with The Metropolitan Police Department's (MPD) Major Crash Investigation Unit, determines if there are any short-term measures that DDOT can install to improve safety for all roadway users. Starting in 2021, site visit findings and follow-up can be found in the docked window on the right for each fatality.
    
    Adjust the selection for Road User, Date Range, and Age filters to refine the results in the map nad table. All charts will update to reflect the fatalities affected by the filters. 
    
    Data are updated twice: first, as soon as the Vision Zero Office receives a fatality memo from the Metropolitan Police Department (MPD) and second, after a crash site visit has been completed by DDOT.

</Details>