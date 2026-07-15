---
queries:
   - intersection_keys: intersection_keys.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
---

<script>
  const csv = (v, fallback) => (v ? v.split(',').map(s => s.trim()) : fallback);

  $: qp      = $page.url.searchParams;
  $: dSev    = csv(qp.get('severity'), ['Fatal', 'Major', 'Minor']);
  $: dMode   = csv(qp.get('mode'), null);
  $: dMinAge = qp.get('min_age') ? Number(qp.get('min_age')) : 0;
  $: dMaxAge = qp.get('max_age') ? Number(qp.get('max_age')) : 120;
  $: dStart  = qp.get('start') ?? '2017-01-01';
  $: dEnd    = qp.get('end');

  let isDesktop = false;

  onMount(() => {
    isDesktop = window.innerWidth >= 768;
    const handleResize = () => { isDesktop = window.innerWidth >= 768; };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  });
</script>

# <Value data={intx_info} column=INTERSECTION_NAME/>

```sql unique_mode
select MODE from crashes.crashes group by 1
```

```sql unique_severity
select SEVERITY from crashes.crashes group by 1
```

```sql unique_cy
SELECT DISTINCT CAST(DATE_PART('year', REPORTDATE) AS INTEGER) AS year_integer
FROM crashes.crashes
WHERE DATE_PART('year', REPORTDATE) BETWEEN 2017
    AND (SELECT CAST(DATE_PART('year', MAX(LAST_RECORD)) AS INTEGER) FROM crashes.crashes)
ORDER BY year_integer DESC
```

```sql intx_info
SELECT
    INTERSECTIONKEY,
    canonical_name AS INTERSECTION_NAME,
    LATITUDE,
    LONGITUDE
FROM intersections.intersections_unique
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
```

```sql this_buffer
SELECT
    INTERSECTIONKEY,
    canonical_name AS INTERSECTION_NAME
FROM intersections.intersections_unique
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
```

```sql unique_hin
select GIS_ID, ROUTENAME
from hin.hin
group by all
```

```sql date_label
WITH report_date_range AS (
    SELECT
    CASE
        WHEN '${inputs.date_range.end}'::DATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
    END AS end_date,
    '${inputs.date_range.start}'::DATE AS start_date
)
SELECT
    CASE
        -- Full calendar year -> "YYYY"
        WHEN start_date = DATE_TRUNC('year', start_date)
             AND end_date = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
            THEN EXTRACT(YEAR FROM start_date)::VARCHAR
        -- Current year to date -> "YYYY YTD"
        WHEN start_date = DATE_TRUNC('year', CURRENT_DATE)
             AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
            THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
        WHEN start_date <= '2017-01-01'::DATE
            THEN 'Since 2017'
        ELSE strftime(start_date, '%m/%d/%y') || '-' || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
    END AS label
FROM report_date_range
```

```sql mode_severity_selection
WITH
  total_modes_cte AS (
    SELECT COUNT(DISTINCT MODE) AS total_mode_count FROM crashes.crashes
  ),
  mode_agg_cte AS (
    SELECT
      STRING_AGG(DISTINCT CASE WHEN MODE LIKE '%*' THEN REPLACE(MODE, '*', 's*') ELSE MODE || 's' END, ', ' ORDER BY MODE ASC) AS mode_list,
      COUNT(DISTINCT MODE) AS mode_count
    FROM crashes.crashes
    WHERE MODE IN ${inputs.multi_mode_dd.value}
  ),
  severity_agg_cte AS (
    SELECT
        COUNT(DISTINCT SEVERITY) AS severity_count,
        CASE
        WHEN COUNT(DISTINCT SEVERITY) = 0 THEN ' '
        WHEN BOOL_AND(SEVERITY IN ('Fatal')) THEN 'Fatalities'
        WHEN BOOL_AND(SEVERITY IN ('Major', 'Fatal')) AND COUNT(DISTINCT SEVERITY) = 2 THEN 'Major Injuries and Fatalities'
        WHEN BOOL_AND(SEVERITY IN ('Minor', 'Major')) AND COUNT(DISTINCT SEVERITY) = 2 THEN 'Minor and Major Injuries'
        WHEN BOOL_AND(SEVERITY IN ('Minor', 'Major', 'Fatal')) AND COUNT(DISTINCT SEVERITY) = 3 THEN 'Minor and Major Injuries, Fatalities'
        ELSE STRING_AGG(DISTINCT CASE WHEN SEVERITY = 'Fatal' THEN 'Fatalities' WHEN SEVERITY = 'Major' THEN 'Major Injuries' WHEN SEVERITY = 'Minor' THEN 'Minor Injuries' END, ', '
            ORDER BY CASE SEVERITY WHEN 'Minor' THEN 1 WHEN 'Major' THEN 2 WHEN 'Fatal' THEN 3 END)
        END AS severity_list
    FROM crashes.crashes
    WHERE MODE IN ${inputs.multi_mode_dd.value} AND SEVERITY IN ${inputs.multi_severity.value}
    )
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
FROM mode_agg_cte, severity_agg_cte, total_modes_cte
```

```sql crashes_at
SELECT
    REPORTDATE,
    MODE,
    SEVERITY,
    CASE WHEN TRY_CAST(AGE AS INTEGER) = 120 THEN NULL ELSE TRY_CAST(AGE AS INTEGER) END AS Age,
    CCN,
    ADDRESS,
    LATITUDE,
    LONGITUDE,
    DIST_TO_INTX_FT
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
ORDER BY SEVERITY, REPORTDATE DESC
```

```sql period_comp_severity
WITH 
    report_date_range AS (
        SELECT
        CASE 
            WHEN '${inputs.date_range.end}'::DATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
            ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
        END AS end_date,
        '${inputs.date_range.start}'::DATE AS start_date
    ),
    date_info AS (
        SELECT start_date, end_date,
            CASE
                WHEN start_date = DATE_TRUNC('year', start_date) AND end_date = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM start_date)::VARCHAR
                WHEN start_date = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
                WHEN start_date <= '2017-01-01'::DATE
                    THEN 'Since 2017'
                ELSE strftime(start_date, '%m/%d/%y') || '-' || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS date_range_label
        FROM report_date_range
    ),
    offset_period AS (
        SELECT start_date, end_date,
        CASE 
            WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
            WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
            WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
            WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
            ELSE INTERVAL '1 year'
        END AS interval_offset
        FROM date_info
    ),
    prior_date_info AS (
        SELECT
            (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
            (SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
    ),
    prior_date_label AS (
        SELECT
            CASE
                WHEN prior_start_date = DATE_TRUNC('year', prior_start_date) AND prior_end_date = DATE_TRUNC('year', prior_start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM prior_start_date)::VARCHAR
                WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = (SELECT end_date FROM date_info) - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
                ELSE strftime(prior_start_date, '%m/%d/%y') || '-' || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS prior_date_range_label
        FROM prior_date_info
    ),
    severities AS (
        SELECT DISTINCT SEVERITY
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
    ),
    current_period AS (
        SELECT SEVERITY, SUM("COUNT") AS sum_count
        FROM crashes.crashes
        WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
            AND SEVERITY IN ${inputs.multi_severity.value}
            AND MODE IN ${inputs.multi_mode_dd.value}
            AND REPORTDATE BETWEEN (SELECT start_date FROM date_info) AND (SELECT end_date FROM date_info)
            AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
        GROUP BY SEVERITY
    ),
    prior_period AS (
        SELECT SEVERITY, SUM("COUNT") AS sum_count
        FROM crashes.crashes
        WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
            AND SEVERITY IN ${inputs.multi_severity.value}
            AND MODE IN ${inputs.multi_mode_dd.value}
            AND REPORTDATE BETWEEN (SELECT prior_start_date FROM prior_date_info) AND (SELECT prior_end_date FROM prior_date_info)
            AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
        GROUP BY SEVERITY
    )
SELECT
    s.SEVERITY,
    COALESCE(cp.sum_count, 0) AS current_period_sum,
    COALESCE(pp.sum_count, 0) AS prior_period_sum,
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) != 0 THEN ((COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0)) / COALESCE(pp.sum_count, 0))
        ELSE NULL
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
    CASE s.SEVERITY WHEN 'Fatal' THEN 1 WHEN 'Major' THEN 2 WHEN 'Minor' THEN 3 ELSE 4 END AS sort_order
FROM severities s
LEFT JOIN current_period cp ON s.SEVERITY = cp.SEVERITY
LEFT JOIN prior_period pp ON s.SEVERITY = pp.SEVERITY
ORDER BY sort_order
```

```sql barchart_mode
WITH 
    report_date_range AS (
        SELECT
        CASE 
            WHEN '${inputs.date_range.end}'::DATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
            ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
        END AS end_date,
        '${inputs.date_range.start}'::DATE AS start_date
    ),
    date_info AS (
        SELECT start_date, end_date,
            CASE
                WHEN start_date = DATE_TRUNC('year', start_date) AND end_date = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM start_date)::VARCHAR
                WHEN start_date = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
                WHEN start_date <= '2017-01-01'::DATE
                    THEN 'Since 2017'
                ELSE strftime(start_date, '%m/%d/%y') || '-' || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS date_range_label
        FROM report_date_range
    ),
    offset_period AS (
        SELECT start_date, end_date,
        CASE 
            WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
            WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
            WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
            WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
            ELSE INTERVAL '1 year'
        END AS interval_offset
        FROM date_info
    ),
    prior_date_info AS (
        SELECT
            (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
            (SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
    ),
    prior_date_label AS (
        SELECT
            CASE
                WHEN prior_start_date = DATE_TRUNC('year', prior_start_date) AND prior_end_date = DATE_TRUNC('year', prior_start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM prior_start_date)::VARCHAR
                WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = (SELECT end_date FROM date_info) - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
                ELSE strftime(prior_start_date, '%m/%d/%y') || '-' || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS prior_date_range_label
        FROM prior_date_info
    ),
    modes AS (
        SELECT DISTINCT MODE
        FROM crashes.crashes
        WHERE MODE IN ${inputs.multi_mode_dd.value}
    ),
    current_period AS (
        SELECT MODE, SUM("COUNT") AS sum_count
        FROM crashes.crashes
        WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
            AND SEVERITY IN ${inputs.multi_severity.value}
            AND MODE IN ${inputs.multi_mode_dd.value}
            AND REPORTDATE BETWEEN (SELECT start_date FROM date_info) AND (SELECT end_date FROM date_info)
            AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
        GROUP BY MODE
    ),
    prior_period AS (
        SELECT MODE, SUM("COUNT") AS sum_count
        FROM crashes.crashes
        WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
            AND SEVERITY IN ${inputs.multi_severity.value}
            AND MODE IN ${inputs.multi_mode_dd.value}
            AND REPORTDATE BETWEEN (SELECT prior_start_date FROM prior_date_info) AND (SELECT prior_end_date FROM prior_date_info)
            AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
        GROUP BY MODE
    )
SELECT
    m.MODE,
    'Current Period' AS period,
    COALESCE(cp.sum_count, 0) AS period_sum,
    di.date_range_label AS period_range
FROM modes m
LEFT JOIN current_period cp ON m.MODE = cp.MODE
CROSS JOIN date_info di
UNION ALL
SELECT
    m.MODE,
    'Prior Period' AS period,
    COALESCE(pp.sum_count, 0) AS period_sum,
    pdl.prior_date_range_label AS period_range
FROM modes m
LEFT JOIN prior_period pp ON m.MODE = pp.MODE
CROSS JOIN prior_date_label pdl
ORDER BY MODE, period
```

```sql cy_barchart
-- Applies only the month/day span of date_range_cy across every selected year:
--   'Year to Today' -> 01-01..today   => YTD comparison across years
--   'Last Year'     -> 01-01..12-31   => full calendar year comparison
-- Years are zero-filled. At a single intersection most years have no crashes,
-- so joining straight to crashes would silently drop those years from the axis.
WITH
  report_date_range_cy AS (
    SELECT
      '${inputs.date_range_cy.start}'::DATE AS cy_start_date,
      '${inputs.date_range_cy.end}'::DATE   AS cy_end_date
  ),
  date_info_cy AS (
    SELECT
      cy_start_date,
      cy_end_date,
      strftime(cy_start_date, '%m-%d') AS month_day_start,
      strftime(cy_end_date,   '%m-%d') AS month_day_end
    FROM report_date_range_cy
  ),
  allowed_years AS (
    SELECT DISTINCT CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr
    FROM crashes.crashes
    WHERE CAST(strftime('%Y', REPORTDATE) AS INTEGER) IN ${inputs.multi_cy.value}
  ),
  selected_severities AS (
    SELECT DISTINCT SEVERITY
    FROM crashes.crashes
    WHERE SEVERITY IN ${inputs.multi_severity.value}
  ),
  year_severity_grid AS (
    SELECT ay.yr, s.SEVERITY
    FROM allowed_years ay
    CROSS JOIN selected_severities s
  ),
  counts AS (
    SELECT
      CAST(strftime('%Y', c.REPORTDATE) AS INTEGER) AS yr,
      c.SEVERITY,
      SUM(c."COUNT") AS year_count
    FROM crashes.crashes c
    CROSS JOIN date_info_cy d
    WHERE c.INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
      AND c.REPORTDATE >= CAST(CAST(strftime('%Y', c.REPORTDATE) AS INTEGER) || '-' || d.month_day_start AS DATE)
      AND c.REPORTDATE <  CAST(CAST(strftime('%Y', c.REPORTDATE) AS INTEGER) || '-' || d.month_day_end   AS DATE) + INTERVAL '1 day'
      AND c.SEVERITY IN ${inputs.multi_severity.value}
      AND c.MODE IN ${inputs.multi_mode_dd.value}
      AND c.AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
    GROUP BY 1, 2
  )
SELECT
  g.yr AS Year,
  g.SEVERITY,
  COALESCE(cnt.year_count, 0) AS Count,
  CASE
    WHEN (SELECT month_day_start FROM date_info_cy) = '01-01'
     AND (SELECT month_day_end   FROM date_info_cy) = '12-31'
      THEN 'Calendar Year'
    WHEN (SELECT month_day_start FROM date_info_cy) = '01-01'
      THEN 'Year to Date'
    ELSE REPLACE((SELECT month_day_start FROM date_info_cy), '-', '/') || '-' ||
         REPLACE((SELECT month_day_end   FROM date_info_cy), '-', '/')
  END AS Date_Range
FROM year_severity_grid g
LEFT JOIN counts cnt ON g.yr = cnt.yr AND g.SEVERITY = cnt.SEVERITY
ORDER BY g.yr DESC, g.SEVERITY
```

```sql crashes_fatal
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Fatal'
```

```sql crashes_major
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Major'
```

```sql crashes_minor
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Minor'
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
presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year', 'All Time']}
defaultValue="Year to Today"
description="By default, there is a two-day lag after the latest update"
/>

<Dropdown
data={unique_severity}
name="multi_severity"
value="SEVERITY"
title="Severity"
multiple={true}
defaultValue={dSev}
/>

<Dropdown
    data={unique_mode}
    name=multi_mode_dd
    value=MODE
    title="Road User"
    multiple=true
    defaultValue={dMode ?? undefined}
    selectAllByDefault={dMode === null}
    description="*Only fatal"
/>

<Dropdown
    data={age_range}
    name=min_age
    value=age_int
    title="Min Age"
    defaultValue={dMinAge}
/>

<Dropdown
    data={age_range}
    name="max_age"
    value=age_int
    title="Max Age"
    order="age_int desc"
    defaultValue={dMaxAge}
/>

<Grid cols=2>
    <Group>
        <BaseMap
            height=495
            startingZoom=18
            title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} ({`${date_label[0].label}`})"
        >
        <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
            tooltip={[
                {id: 'ROUTENAME', showColumnName:false}
            ]}
        />
        <Areas data={this_buffer} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/Intersection_Points_buffers.geojson' geoId=INTERSECTIONKEY areaCol=INTERSECTIONKEY color=#1C00ff00 borderColor='#A9A9A9' borderWidth=1
            tooltip={[
                {id:'INTERSECTION_NAME', valueClass:'text-l font-semibold', showColumnName:false}
            ]}
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
        <div style="display:flex; gap:16px; align-items:center; font-size:12px; margin:6px 0 0 4px;">
            {#if crashes_fatal.length > 0}
            <span style="display:flex; align-items:center; gap:5px;">
                <span style="width:11px; height:11px; border-radius:50%; background:#ff5a53; opacity:0.6; display:inline-block;"></span>Fatal
            </span>
            {/if}
            {#if crashes_major.length > 0}
            <span style="display:flex; align-items:center; gap:5px;">
                <span style="width:11px; height:11px; border-radius:50%; background:#ff9412; opacity:0.6; display:inline-block;"></span>Major
            </span>
            {/if}
            {#if crashes_minor.length > 0}
            <span style="display:flex; align-items:center; gap:5px;">
                <span style="width:11px; height:11px; border-radius:50%; background:#ffdf00; opacity:0.6; display:inline-block;"></span>Minor
            </span>
            {/if}
        </div>
        <Note>
            The circle is the intersection's 100 ft buffer. Points are crashes assigned to it, colored by severity. Purple lines are DC's High Injury Network.
        </Note>
        <Details title="Injury Crashes Assigned to This Intersection">
        <DataTable data={crashes_at} rows=10 search=true rowShading=true wrapTitles=true>
                <Column id=REPORTDATE title="Date" fmt='mm/dd/yy hh:mm' wrap=true/>
                <Column id=MODE title="Road User" wrap=true/>
                <Column id=SEVERITY title="Severity"/>
                <Column id=Age/>
                <Column id=CCN title="CCN"/>
                <Column id=ADDRESS title="Address" wrap=true/>
                <Column id=DIST_TO_INTX_FT title="Dist (ft)" fmt='#,##0'/>
            </DataTable>
        </Details>
    </Group>
    <Group>
        <DataTable data={period_comp_severity} rows=all wrapTitles=true rowShading=true totalRow=true title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} ({`${date_label[0].label}`})">
            <Column id=SEVERITY title="Severity" wrap=true totalAgg="Total"/>
            <Column id=current_period_sum title={`${period_comp_severity[0].current_period_range}`} />
            <Column id=prior_period_sum title={`${period_comp_severity[0].prior_period_range}`} />
            <Column id=difference title="Diff" contentType=delta downIsGood=True />
            <Column id=percentage_change fmt='pct0' title="% Diff" />
        </DataTable>
        <div style="font-size: 14px;">
            <b>Percentage Breakdown by Road User</b>
        </div>
        {#if isDesktop}
          <BarChart
            data={barchart_mode}
            chartAreaHeight=80
            x=period_range
            y=period_sum
            xLabelWrap={true}
            swapXY=true
            yFmt=pct0
            series=MODE
            seriesColors={{
              "Driver":        '#2563EB',
              "Passenger":     '#38BDF8',
              "Pedestrian":    '#EC4899',
              "Bicyclist":     '#10B981',
              "Scooterist*":   '#34F5C5',
              "Motorcyclist*": '#D946EF',
              "Other":         '#94A3B8'
            }}
            labels={true}
            type=stacked100
            downloadableData=false
            downloadableImage=false
            leftPadding={10}
            seriesOptions={{
              label: {
                show: true,
                formatter: (params) => {
                  const pct = params.value[0];
                  if (!pct) return '';
                  const row = barchart_mode.find(
                    (r) => r.period_range === params.name && r.MODE === params.seriesName
                  );
                  const cnt = row ? row.period_sum : null;
                  return cnt ? `${cnt} (${Math.round(pct * 100)}%)` : `${Math.round(pct * 100)}%`;
                }
              }
            }}
            echartsOptions={{
              legend: { type: 'plain', show: true, top: 0 },
              grid: { top: 40 }
            }}
          />
          {:else}
            <BarChart
              data={barchart_mode}
              chartAreaHeight=120
              x=period_range
              y=period_sum
              xLabelWrap={true}
              swapXY=true
              yFmt=pct0
              series=MODE
              seriesColors={{
                "Driver":        '#2563EB',
                "Passenger":     '#38BDF8',
                "Pedestrian":    '#EC4899',
                "Bicyclist":     '#10B981',
                "Scooterist*":   '#34F5C5',
                "Motorcyclist*": '#D946EF',
                "Other":         '#94A3B8'
              }}
              labels={true}
              type=stacked100
              downloadableData=false
              downloadableImage=false
              leftPadding={10}
              seriesOptions={{
                label: {
                  show: true,
                  formatter: (params) => {
                    const pct = params.value[0];
                    if (!pct) return '';
                    const row = barchart_mode.find(
                      (r) => r.period_range === params.name && r.MODE === params.seriesName
                    );
                    const cnt = row ? row.period_sum : null;
                    return cnt ? `${cnt} (${Math.round(pct * 100)}%)` : `${Math.round(pct * 100)}%`;
                  }
                }
              }}
              echartsOptions={{
                legend: { type: 'plain', show: true, top: 0 },
                grid: { top: 65 }
              }}
            />
          {/if}
        <div style="font-size: 14px;">
            <b>{cy_barchart[0].Date_Range} Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
        </div>
        <BarChart
        data={cy_barchart}
        subtitle=" "
        chartAreaHeight=165
        x="Year"
        y="Count"
        series="SEVERITY"
        seriesColors={{"Minor": '#ffdf00',"Major": '#ff9412',"Fatal": '#ff5a53'}}
        labels={true}
        xAxisLabels={true}
        xTickMarks={true}
        leftPadding={10}
        rightPadding={30}
        echartsOptions={{
            xAxis: {
            type: 'category',
            axisLabel: {
                rotate: 90
            }
            }
        }}
        />
        <DateRange
            start="2017-01-01"
            end={
                (last_record && last_record[0] && last_record[0].end_date)
                ? `${last_record[0].end_date}`
                : (() => {
                    const twoDaysAgo = new Date(new Date().setDate(new Date().getDate() - 2));
                    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(twoDaysAgo);
                    })()
            }
            name="date_range_cy"
            presetRanges={['Year to Today', 'Last Year']}
            defaultValue='Year to Today'
            description="Year to Today compares the same period across years. Last Year compares full calendar years."
        />
        <Info description=
            "The date picker considers only your selection of the month and day. For year selection use the year dropdown."
        />
        <Dropdown
            data={unique_cy}
            name=multi_cy
            value=year_integer
            title="Select Year"
            multiple=true
            selectAllByDefault=true
        />
    </Group>
</Grid>