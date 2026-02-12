---
title: Traffic Fatalities
queries:
   - fatality: fatality.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_link: false
---
{#if hin_rate[0].is_first_week}
  <span style="font-size: 1.4rem; font-weight: 700;">
    <Value data={hin_rate} column="period"/> Year-End
  </span>
{:else}
{/if}

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

```sql unique_year
SELECT DISTINCT strftime('%Y', REPORTDATE) AS year_string
FROM crashes.crashes
WHERE strftime('%Y', REPORTDATE) BETWEEN '2014' 
    AND (SELECT strftime('%Y', MAX(LAST_RECORD)) FROM crashes.crashes)
ORDER BY year_string DESC;
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

```sql hin_rate
WITH 
-- 0) Flatten HIN tier columns into one
crashes_with_tiers AS (
  SELECT REPORTDATE, SEVERITY, replace(MODE, '*', '') AS MODE, AGE, COUNT, HIN_TIER_A AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_A IS NOT NULL
  UNION ALL
  SELECT REPORTDATE, SEVERITY, replace(MODE, '*', '') AS MODE, AGE, COUNT, HIN_TIER_B AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_B IS NOT NULL
  UNION ALL
  SELECT REPORTDATE, SEVERITY, replace(MODE, '*', '') AS MODE, AGE, COUNT, HIN_TIER_C AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_C IS NOT NULL
),
-- 1) Determine the current period bounds
report_date_range AS (
  SELECT
    ('${inputs.date_range.end}'::DATE + INTERVAL '1 day') AS end_date,
    '${inputs.date_range.start}'::DATE AS start_date
),
-- 2) Choose prior-window offset based on span length
offset_period AS (
  SELECT
    rdr.start_date,
    rdr.end_date,
    CASE 
      WHEN rdr.end_date > rdr.start_date + INTERVAL '5 year' THEN (SELECT 1/0)
      WHEN rdr.end_date > rdr.start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
      WHEN rdr.end_date > rdr.start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
      WHEN rdr.end_date > rdr.start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
      WHEN rdr.end_date > rdr.start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
      ELSE INTERVAL '1 year'
    END AS interval_offset
  FROM report_date_range AS rdr
),
-- 3) Define windows
current_window AS (
  SELECT start_date, end_date
  FROM report_date_range
),
prior_window AS (
  SELECT
    rdr.start_date - op.interval_offset AS start_date,
    rdr.end_date   - op.interval_offset AS end_date
  FROM report_date_range AS rdr
  CROSS JOIN offset_period AS op
),
-- 4) Labels for current and prior windows
date_info AS (
  SELECT
    start_date,
    end_date,
    CASE
      WHEN start_date = DATE_TRUNC('year', start_date)
       AND end_date   = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
      THEN EXTRACT(YEAR FROM start_date)::VARCHAR
      WHEN start_date = DATE_TRUNC('year', CURRENT_DATE)
       AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
      THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
      ELSE
        strftime(start_date, '%m/%d/%y')
        || '-'
        || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
    END AS date_range_label,
    (end_date - start_date) AS date_range_days
  FROM report_date_range
),
prior_date_info AS (
  SELECT
    (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
    (SELECT end_date   FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
),
prior_date_label AS (
  SELECT
    CASE
      WHEN prior_start_date = DATE_TRUNC('year', prior_start_date)
       AND prior_end_date   = DATE_TRUNC('year', prior_start_date) + INTERVAL '1 year'
      THEN EXTRACT(YEAR FROM prior_start_date)::VARCHAR
      WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', CURRENT_DATE)
       AND '${inputs.date_range.end}'::DATE = (SELECT end_date FROM date_info) - INTERVAL '1 day'
      THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
      ELSE
        strftime(prior_start_date,   '%m/%d/%y')
        || '-'
        || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
    END AS prior_date_range_label
  FROM prior_date_info
),
-- 5) Centralize age bounds
age_bounds AS (
  SELECT
    ${inputs.min_age.value}::INTEGER AS min_age,
    CASE 
      WHEN ${inputs.min_age.value} <> 0
       AND ${inputs.max_age.value} = 120
      THEN 119
      ELSE ${inputs.max_age.value}
    END::INTEGER AS max_age
),
-- 6) Summaries for current and prior
current_hin AS (
  SELECT SUM(COUNT) AS injuries_in_hin
  FROM crashes_with_tiers
  WHERE
    SEVERITY = 'Fatal'
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM current_window)
    AND (SELECT end_date   FROM current_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
current_total AS (
  SELECT SUM(COUNT) AS total_injuries
  FROM (
    SELECT REPORTDATE, SEVERITY, replace(MODE, '*', '') AS MODE, AGE, COUNT
    FROM crashes.crashes
  ) t
  WHERE
    SEVERITY = 'Fatal'
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM current_window)
    AND (SELECT end_date   FROM current_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
prior_hin AS (
  SELECT SUM(COUNT) AS injuries_in_hin_prior
  FROM crashes_with_tiers
  WHERE
    SEVERITY = 'Fatal'
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM prior_window)
    AND (SELECT end_date   FROM prior_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
prior_total AS (
  SELECT SUM(COUNT) AS total_injuries_prior
  FROM (
    SELECT REPORTDATE, SEVERITY, replace(MODE, '*', '') AS MODE, AGE, COUNT
    FROM crashes.crashes
  ) t
  WHERE
    SEVERITY = 'Fatal'
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM prior_window)
    AND (SELECT end_date   FROM prior_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
-- 7) Add first-week flag
first_week_flag AS (
  SELECT
    CASE
      WHEN extract(month FROM current_date) = 1
       AND extract(day   FROM current_date) <= 7
      THEN TRUE
      ELSE FALSE
    END AS is_first_week
)
-- 8) Final output
SELECT
  1 AS period_sort,
  (SELECT date_range_label FROM date_info) AS period,
  ch.injuries_in_hin,
  ct.total_injuries,
  CASE 
    WHEN ct.total_injuries = 0 THEN NULL
    ELSE ch.injuries_in_hin * 1.0 / ct.total_injuries
  END AS proportion_hin,
  (SELECT is_first_week FROM first_week_flag) AS is_first_week
FROM current_hin AS ch
CROSS JOIN current_total AS ct
UNION ALL
SELECT
  2 AS period_sort,
  (SELECT prior_date_range_label FROM prior_date_label) AS period,
  ph.injuries_in_hin_prior      AS injuries_in_hin,
  pt.total_injuries_prior       AS total_injuries,
  CASE 
    WHEN pt.total_injuries_prior = 0 THEN NULL
    ELSE ph.injuries_in_hin_prior * 1.0 / pt.total_injuries_prior
  END AS proportion_hin,
  (SELECT is_first_week FROM first_week_flag) AS is_first_week
FROM prior_hin AS ph
CROSS JOIN prior_total AS pt
ORDER BY period_sort;
```

```sql ytd_avg
WITH 
  -- Raw input range (end_date is exclusive)
  date_range AS (
    SELECT
      '${inputs.date_range.start}'::DATE AS start_date,
      ('${inputs.date_range.end}'::DATE + INTERVAL '1 day') AS end_date
  ),
  -- Compute inclusive end date + current_year
  date_info AS (
    SELECT
      start_date,
      end_date,
      (end_date - INTERVAL '1 day') AS inclusive_end_date,
      EXTRACT(YEAR FROM end_date - INTERVAL '1 day') AS current_year,
      strftime(start_date, '%m-%d') AS month_day_start,
      strftime(end_date - INTERVAL '1 day', '%m-%d') AS month_day_end
    FROM date_range
  ),
  -- Dataset min/max years
  crash_years AS (
    SELECT
      CAST(strftime('%Y', MIN(REPORTDATE)) AS INTEGER) AS min_year,
      CAST(strftime('%Y', MAX(LAST_RECORD)) AS INTEGER) AS max_year
    FROM crashes.crashes
  ),
  -- Yearly counts using the month-day window
  yearly_counts AS (
    SELECT 
      CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr,
      SUM("COUNT") AS yearly_count
    FROM (
      SELECT REPORTDATE,
             SEVERITY,
             replace(MODE, '*', '') AS MODE,
             AGE,
             COUNT
      FROM crashes.crashes
    ) c
    CROSS JOIN date_info d
    CROSS JOIN crash_years cy
    WHERE 
      -- Apply the same month-day window per year
      c.REPORTDATE >= CAST(CAST(strftime('%Y', c.REPORTDATE) AS TEXT) || '-' || d.month_day_start AS DATE)
      AND c.REPORTDATE <  CAST(CAST(strftime('%Y', c.REPORTDATE) AS TEXT) || '-' || d.month_day_end   AS DATE) + INTERVAL '1 day'
      AND c.SEVERITY = 'Fatal'
      AND c.MODE IN ${inputs.multi_mode_dd.value}
      AND c.AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                          WHEN ${inputs.min_age.value} <> 0 
                           AND ${inputs.max_age.value} = 120
                          THEN 119
                          ELSE ${inputs.max_age.value}
                        END
                    )
      -- Cap years at LEAST(max_year, current_year)
      AND CAST(strftime('%Y', c.REPORTDATE) AS INTEGER)
          BETWEEN (
            SELECT MIN(x) FROM (VALUES ${inputs.multi_year.value}) AS t(x)
          )
          AND LEAST(cy.max_year, d.current_year)
      -- Still respect multi_year input
      AND strftime('%Y', c.REPORTDATE) IN ${inputs.multi_year.value}
    GROUP BY yr
  ),
  -- Exclude the "current year" from the average
  filtered_years AS (
    SELECT *
    FROM yearly_counts, date_info
    WHERE yr <> current_year
  )
SELECT 
  ROUND(COALESCE(AVG(yearly_count), 0), 0) AS average_count,
  CASE
    -- Full calendar year → remove YTD
    WHEN ANY_VALUE(date_info.start_date) = DATE_TRUNC('year', ANY_VALUE(date_info.start_date))
     AND ANY_VALUE(date_info.end_date)   = DATE_TRUNC('year', ANY_VALUE(date_info.start_date)) + INTERVAL '1 year'
    THEN printf('''%02d⁃''%02d Avg',
                MIN(yr) % 100,
                MAX(yr) % 100)
    -- Otherwise → keep YTD
    ELSE printf('''%02d⁃''%02d YTD Avg',
                MIN(yr) % 100,
                MAX(yr) % 100)
  END AS year_range_label
FROM filtered_years
CROSS JOIN date_info;
```

```sql ytd_barchart
WITH 
  -- Raw input range, as inclusive dates
  report_date_range AS (
    SELECT
      -- exclusive upper bound (used for BETWEEN logic)
      ('${inputs.date_range.end}'::DATE + INTERVAL '1 day') AS current_end_date,
      '${inputs.date_range.start}'::DATE AS current_start_date
  ),
  -- Get min/max data years
  crash_years AS (
    SELECT
      CAST(strftime('%Y', MIN(REPORTDATE)) AS INTEGER) AS min_year,
      CAST(strftime('%Y', MAX(LAST_RECORD)) AS INTEGER) AS max_year
    FROM crashes.crashes
  ),
  date_info AS (
    SELECT
      current_start_date   AS start_date,
      current_end_date     AS end_date,  -- exclusive
      -- Use the INCLUSIVE end date for all "year" and label logic
      (current_end_date - INTERVAL '1 day')               AS inclusive_end_date,
      EXTRACT(YEAR FROM current_end_date - INTERVAL '1 day') AS current_year,
      CASE
        WHEN current_start_date = DATE_TRUNC('year', current_end_date - INTERVAL '1 day')
             AND '${inputs.date_range.end}'::DATE = (current_end_date - INTERVAL '1 day')::DATE
          THEN 'to Date'
        ELSE
          '('
          || strftime(current_start_date, '%m/%d')
          || '-'
          || strftime(current_end_date - INTERVAL '1 day', '%m/%d')
          || ')'
      END                   AS date_range_label,
      (current_end_date - current_start_date) AS date_range_days,
      strftime(current_start_date,                  '%m-%d') AS month_day_start,
      strftime(current_end_date - INTERVAL '1 day', '%m-%d') AS month_day_end
    FROM report_date_range
  ),
  years AS (
    SELECT CAST(year_string AS INTEGER) AS yr
    FROM (
      SELECT DISTINCT
        strftime('%Y', REPORTDATE) AS year_string
      FROM crashes.crashes c
      CROSS JOIN date_info d
      CROSS JOIN crash_years cy
      WHERE
        strftime('%Y', REPORTDATE) BETWEEN 
          (SELECT MIN(x) FROM (VALUES ${inputs.multi_year.value}) AS t(x))
          AND CAST(LEAST(cy.max_year, d.current_year) AS VARCHAR)
    ) unique_years
    WHERE year_string IN ${inputs.multi_year.value}
    ORDER BY year_string DESC
  ),
  -- Normalize MODE before grouping
  yearly_counts AS (
    SELECT 
      y.yr,
      c.SEVERITY,
      SUM(c."COUNT") AS year_count
    FROM years y
    CROSS JOIN date_info d
    JOIN (
      SELECT REPORTDATE,
             SEVERITY,
             replace(MODE, '*', '') AS MODE,
             AGE,
             COUNT
      FROM crashes.crashes
    ) c
      ON c.REPORTDATE >= CAST(y.yr || '-' || d.month_day_start AS DATE)
     AND c.REPORTDATE <  CAST(y.yr || '-' || d.month_day_end   AS DATE) + INTERVAL '1 day'
     AND c.SEVERITY = 'Fatal'
     AND c.MODE IN ${inputs.multi_mode_dd.value}
     AND c.AGE BETWEEN ${inputs.min_age.value}
                   AND (
                        CASE 
                          WHEN ${inputs.min_age.value} <> 0 
                           AND ${inputs.max_age.value} = 120
                          THEN 119
                          ELSE ${inputs.max_age.value}
                        END
                       )
    GROUP BY y.yr, c.SEVERITY
  ),
  current_year_count AS (
    SELECT yr, SEVERITY, year_count AS current_count
    FROM yearly_counts, date_info
    WHERE yr = current_year
  )
SELECT 
  y.yr AS Year,
  yc.SEVERITY,
  COALESCE(yc.year_count, 0) AS Count,
  COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0) AS Diff_from_current,
  CASE 
    WHEN COALESCE(yc.year_count, 0) = 0 THEN NULL
    ELSE (COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0)) * 1.0 / yc.year_count
  END AS Percent_Diff_from_current,
  (SELECT date_range_label FROM date_info) AS Date_Range
FROM years y
LEFT JOIN yearly_counts yc
  ON y.yr = yc.yr
LEFT JOIN current_year_count cyc
  ON y.yr = cyc.yr
ORDER BY y.yr DESC, yc.SEVERITY;
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
      return inFirstWeek ? 'Last Year' : 'Year to Today';
    })()
  }
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

<Dropdown
    data={unique_year} 
    name=multi_year
    value=year_string
    title="Year"
    multiple=true
    selectAllByDefault=true
/>        

<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Map of Fatalities for {`${mode_selection[0].MODE_SELECTION}`} ({`${hin_rate[0].period}`})</b>
        </div>
        <Note>
            Each point on the map represents an fatality. Fatality incidents can overlap in the same spot.
        </Note>
        <BaseMap
            height=380
            startingZoom=11
        >
            <Points data={inc_map} lat=LATITUDE long=LONGITUDE pointName=MODE value=SEVERITY colorPalette={['#ff5a53']} ignoreZoom=true link=link
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
        <DataTable data={hin_rate} wrapTitles=true rowShading=true title="Fatalities for {`${mode_selection[0].MODE_SELECTION}`} in HIN vs All Roads in DC">
            <Column id=period />
            <Column id=injuries_in_hin title="In HIN"/>
            <Column id=total_injuries title="Overall" />
            <Column id=proportion_hin title="% in HIN" fmt='pct0' />
        </DataTable>
    </Group>
    <Group>
        <div style="font-size: 14px;">
            <b>Contributing Factors in Fatalities for {`${mode_selection[0].MODE_SELECTION}`} ({`${hin_rate[0].period}`})</b>
        </div>
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
        <div style="font-size: 14px;">
            <b>Year Over Year Comparison of Fatalities for {`${mode_selection[0].MODE_SELECTION}`}</b>
        </div>
        <BarChart 
          data={ytd_barchart}
          subtitle=" "
          chartAreaHeight=150 
          x="Year" 
          y="Count" 
          colorPalette={['#ff5a53']}
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
        >
          <ReferenceLine data={ytd_avg} y="average_count" label={`${ytd_avg[0].year_range_label}`}/>
        </BarChart> 
        <Note>
            *The determination of "Suspected Impairment" is preliminary. It may apply to either party involved in a crash. If the crash is handled by USPP, the determination is set as "Unknown". If the crash is a hit-and-run, the determination is also set as "Unknown".
        </Note>
        <Note>
            **The determination of "Suspected Speeding" is preliminary. It may apply to either party involved in a crash. If the crash is handled by USPP, the determination is set as "Unknown".
        </Note>
        <Note>
            The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
        </Note>       
    </Group>
</Grid>


