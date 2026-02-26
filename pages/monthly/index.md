---
title: Monthly Trend
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
sidebar_position: 8
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

```sql unique_year
SELECT DISTINCT strftime('%Y', REPORTDATE) AS year_string
FROM crashes.crashes
WHERE strftime('%Y', REPORTDATE) BETWEEN '2017' 
    AND (SELECT strftime('%Y', MAX(LAST_RECORD)) FROM crashes.crashes)
ORDER BY year_string DESC;
```

```sql unique_cy
SELECT DISTINCT CAST(DATE_PART('year', REPORTDATE) AS INTEGER) AS year_integer
FROM crashes.crashes
WHERE DATE_PART('year', REPORTDATE) BETWEEN 2017
    AND (SELECT CAST(DATE_PART('year', MAX(LAST_RECORD)) AS INTEGER) FROM crashes.crashes)
    AND DATE_PART('year', REPORTDATE) <> DATE_PART('year', CURRENT_DATE)
ORDER BY year_integer DESC;

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
        COUNT(DISTINCT SEVERITY) AS severity_count,
        CASE
        WHEN COUNT(DISTINCT SEVERITY) = 0 THEN ' '
        WHEN BOOL_AND(SEVERITY IN ('Fatal')) THEN 'Fatalities'
        WHEN BOOL_AND(SEVERITY IN ('Major', 'Fatal')) AND COUNT(DISTINCT SEVERITY) = 2 THEN 'Major Injuries and Fatalities'
        WHEN BOOL_AND(SEVERITY IN ('Minor', 'Major')) AND COUNT(DISTINCT SEVERITY) = 2 THEN 'Minor and Major Injuries'
        WHEN BOOL_AND(SEVERITY IN ('Minor', 'Major', 'Fatal')) AND COUNT(DISTINCT SEVERITY) = 3 THEN 'Minor and Major Injuries, Fatalities'
        ELSE STRING_AGG(
            DISTINCT CASE
            WHEN SEVERITY = 'Fatal' THEN 'Fatalities'
            WHEN SEVERITY = 'Major' THEN 'Major Injuries'
            WHEN SEVERITY = 'Minor' THEN 'Minor Injuries'
            END,
            ', '
            ORDER BY
            CASE SEVERITY
                WHEN 'Minor' THEN 1
                WHEN 'Major' THEN 2
                WHEN 'Fatal' THEN 3
            END
        )
        END AS severity_list
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

```sql ytd_month
WITH 
  report_date_range AS (
    SELECT
      CASE 
          WHEN '${inputs.date_range.end}'::DATE >= 
               (SELECT CAST(MAX(LAST_RECORD) AS DATE) FROM crashes.crashes) 
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)
          -- If user selected a full calendar year, do NOT add a day
          WHEN strftime('${inputs.date_range.end}'::DATE, '%m-%d') = '12-31'
            THEN '${inputs.date_range.end}'::DATE
          ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS current_end_date,
      '${inputs.date_range.start}'::DATE AS current_start_date
  ),
  date_info AS (
    SELECT
      current_start_date AS start_date,
      current_end_date   AS end_date,
      -- Always derive reporting year from user-selected end date
      EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE) AS current_year,
      -- Month-day cutoff depends on full-year vs YTD mode
      CASE 
        WHEN '${inputs.date_range.start}'::DATE = make_date(EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::INT, 1, 1)
         AND '${inputs.date_range.end}'::DATE   = make_date(EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::INT, 12, 31)
        THEN '12-31'
        ELSE strftime(current_end_date, '%m-%d')
      END AS month_day_end,
      CASE 
        WHEN '${inputs.date_range.start}'::DATE = make_date(EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::INT, 1, 1)
         AND '${inputs.date_range.end}'::DATE   = make_date(EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::INT, 12, 31)
        THEN TRUE
        ELSE FALSE
      END AS is_full_year
    FROM report_date_range
  ),
  years AS (
    SELECT gs AS yr, d.current_year
    FROM date_info d, generate_series(current_year - 3, current_year) AS t(gs)
  ),
  months AS (
    SELECT gs AS mo
    FROM generate_series(1, 12) AS t(gs)
  ),
  year_month_grid AS (
    SELECT y.yr, y.current_year, m.mo
    FROM years y
    CROSS JOIN months m
  ),
  monthly_counts AS (
    SELECT
      CAST(strftime('%Y', REPORTDATE) AS BIGINT) AS yr,
      CAST(strftime('%m', REPORTDATE) AS BIGINT) AS mo,
      SUM("COUNT") AS month_count,
      d.current_year
    FROM crashes.crashes, date_info d
    WHERE CAST(strftime('%Y', REPORTDATE) AS BIGINT)
          BETWEEN (current_year - 3) AND current_year
      AND crashes.SEVERITY IN ${inputs.multi_severity.value}
      AND crashes.MODE IN ${inputs.multi_mode_dd.value}
      AND crashes.AGE BETWEEN ${inputs.min_age.value}
                          AND (
                              CASE 
                                  WHEN ${inputs.min_age.value} <> 0 
                                   AND ${inputs.max_age.value} = 120
                                  THEN 119
                                  ELSE ${inputs.max_age.value}
                              END
                          )
      AND (
          d.is_full_year
          OR strftime(REPORTDATE, '%m-%d') <= d.month_day_end
      )
    GROUP BY yr, mo, d.current_year
  ),
  base AS (
    SELECT 
      g.yr AS Year,
      g.mo AS Month,
      strftime(make_date(g.yr, g.mo, 1), '%b') AS Month_Name,
      COALESCE(mc.month_count, 0) AS Count,
      g.current_year
    FROM year_month_grid g
    LEFT JOIN monthly_counts mc
      ON g.yr = mc.yr AND g.mo = mc.mo
  ),
  avg_row AS (
    SELECT
      printf('%02d–%02d Avg', MIN(Year) % 100, MAX(Year) % 100) AS Year,
      Month,
      Month_Name,
      ROUND(AVG(Count),0) AS Count,
      current_year
    FROM base
    WHERE Year BETWEEN current_year - 3 AND current_year - 1
    GROUP BY Month, Month_Name, current_year
  )
SELECT *
FROM (
  SELECT CAST(Year AS VARCHAR) AS Year, Month, Month_Name, Count, current_year
  FROM base
  UNION ALL
  SELECT Year, Month, Month_Name, Count, current_year
  FROM avg_row
)
ORDER BY 
  Month,
  CASE 
    WHEN Year = CAST((current_year - 3) AS VARCHAR) THEN 1
    WHEN Year = CAST((current_year - 2) AS VARCHAR) THEN 2
    WHEN Year = CAST((current_year - 1) AS VARCHAR) THEN 3
    WHEN Year LIKE '% Avg' THEN 4
    WHEN Year = CAST(current_year AS VARCHAR) THEN 5
  END;
```

```sql ytd_month_avg
WITH 
  report_date_range AS (
    SELECT
      CASE 
          WHEN '${inputs.date_range.end}'::DATE >= 
               (SELECT CAST(MAX(LAST_RECORD) AS DATE) FROM crashes.crashes) 
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)
          ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS current_end_date,
      '${inputs.date_range.start}'::DATE AS current_start_date
  ),
  date_info AS (
    SELECT
      current_start_date   AS start_date,
      current_end_date     AS end_date,
      EXTRACT(YEAR FROM current_end_date) AS current_year,
      strftime(current_end_date, '%m-%d') AS month_day_end
    FROM report_date_range
  ),
  monthly_counts AS (
    SELECT
      CAST(strftime('%Y', REPORTDATE) AS BIGINT) AS yr,
      CAST(strftime('%m', REPORTDATE) AS BIGINT) AS mo,
      SUM("COUNT") AS month_count
    FROM crashes.crashes, date_info
    WHERE CAST(strftime('%Y', REPORTDATE) AS BIGINT) BETWEEN (current_year - 4) AND current_year
      AND crashes.SEVERITY IN ${inputs.multi_severity.value}
      AND crashes.MODE IN ${inputs.multi_mode_dd.value}
      AND crashes.AGE BETWEEN ${inputs.min_age.value}
                          AND (
                              CASE 
                                  WHEN ${inputs.min_age.value} <> 0 
                                  AND ${inputs.max_age.value} = 120
                                  THEN 119
                                  ELSE ${inputs.max_age.value}
                              END
                          )
      AND strftime(REPORTDATE, '%m-%d') <= month_day_end
    GROUP BY yr, mo
  ),
  filtered AS (
    SELECT *
    FROM monthly_counts, date_info
    WHERE yr <> current_year
  ),
  avg_by_month AS (
    SELECT
      mo,
      ROUND(AVG(month_count),0) AS Avg_Count,
      MIN(yr) AS min_yr,
      MAX(yr) AS max_yr
    FROM filtered
    GROUP BY mo
  ),
  months AS (
    SELECT gs AS mo
    FROM generate_series(1,12) t(gs)
  )
SELECT
  m.mo AS Month,
  strftime(make_date(2000, m.mo, 1), '%b') AS Month_Name,
  COALESCE(a.Avg_Count, 0) AS Avg_Count,
  printf('%02d–%02d YTD Avg', MIN(a.min_yr) % 100, MAX(a.max_yr) % 100) AS Year_Range_Label
FROM months m
LEFT JOIN avg_by_month a ON m.mo = a.mo
GROUP BY m.mo, a.Avg_Count, a.min_yr, a.max_yr
ORDER BY m.mo;
```

<Dropdown
data={unique_severity}
name="multi_severity"
value="SEVERITY"
title="Severity"
multiple={true}
defaultValue={
    (() => {
    const today = new Date();
    const day = today.getDate();
    const notInFirstWeek = (day > 9);
    const noMajorFatal = (has_fatal[0].f_count === 0 || has_major[0].m_count === 0);
    const shouldIncludeMinor = notInFirstWeek && noMajorFatal;
    return shouldIncludeMinor
      ? ['Fatal', 'Major', 'Minor']
      : ['Fatal', 'Major'];
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
    description="*Only fatal"
/>

<Dropdown 
    data={age_range} 
    name=min_age
    value=age_int
    title=" Min Age" 
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
disableAutoDefault={true}
name="date_range"
presetRanges={['Year to Today', 'Last Year']}
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

<div style="font-size: 14px;">
    <b>Year to Date Monthly Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
</div>

<script>
  const labelConfig = {
    label: {
      show: true,
      formatter: function (params) {
        return params.value[1] === 0 ? '0' : params.value[1];
      }
    }
  };
  const defaultPalette = [
    '#03045E','#4d1070','#0077B6','#00B4d8','#90E0EF'
  ];
</script>

<BarChart 
  data={ytd_month}
  chartAreaHeight={300}
  x="Month"
  y="Count"
  type=grouped
  series=Year
  labels={true}
  seriesorder={ytd_month.Year}
  echartsOptions={{
    color: defaultPalette.slice().reverse(),
    xAxis: {
      type: 'category',
      axisLabel: {
        rotate: 90,
        formatter: function (value) {
          const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
          return months[value - 1];
        }
      }
    },
    series: [
      labelConfig, labelConfig, labelConfig, labelConfig, labelConfig
    ]
  }}
>
</BarChart>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons.
</Note>