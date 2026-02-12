---
title: Multiyear Trend
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 7
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

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
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

```sql ytd_avg
WITH date_range AS (
  SELECT
    '${inputs.date_range.start}'::DATE AS start_date,
    CASE
      WHEN '${inputs.date_range.end}'::DATE >= (SELECT CAST(MAX(LAST_RECORD) AS DATE) FROM crashes.crashes)
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)
      ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
    END AS end_date
),
yearly_counts AS (
  SELECT 
    CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr,
    SUM("COUNT") AS yearly_count
  FROM crashes.crashes, date_range
  WHERE REPORTDATE >= CAST(CAST(strftime('%Y', REPORTDATE) AS TEXT) || '-' || strftime(start_date, '%m-%d') AS DATE)
    AND REPORTDATE < CAST(CAST(strftime('%Y', REPORTDATE) AS TEXT) || '-' || strftime(end_date, '%m-%d') AS DATE) + INTERVAL '1 day'
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
    AND strftime('%Y', REPORTDATE) IN ${inputs.multi_year.value}
  GROUP BY yr
),
filtered_years AS (
  SELECT *
  FROM yearly_counts
  WHERE yr <> CAST(strftime('%Y', current_date) AS INTEGER) -- exclude current year
)
SELECT 
  ROUND(COALESCE(AVG(yearly_count), 0), 0) AS average_count,
  printf('''%02d⁃''%02d YTD Avg',
         MIN(yr) % 100,
         MAX(yr) % 100
  ) AS year_range_label
FROM filtered_years;
```

```sql ytd_table
WITH 
  -- Determine the effective current date range based on input and the maximum available REPORTDATE.
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
  -- Extract month/day details, current year & build a date_range_label following your criteria.
  date_info AS (
    SELECT
      current_start_date   AS start_date,
      current_end_date     AS end_date,

      CASE
        WHEN current_start_date = DATE_TRUNC('year', current_end_date)
            AND '${inputs.date_range.end}'::DATE = current_end_date::DATE
          THEN 'to Date'
        ELSE
          '('
          || strftime(current_start_date, '%m/%d')
          || '-'
          || strftime(current_end_date - INTERVAL '1 day',   '%m/%d')
          || ')'
      END                   AS date_range_label,

      (current_end_date - current_start_date) AS date_range_days,
      strftime(current_start_date, '%m-%d')   AS month_day_start,
      strftime(current_end_date,   '%m-%d')   AS month_day_end,
      EXTRACT(YEAR FROM current_end_date)     AS current_year

    FROM report_date_range
  ),
  -- Build the allowed list of years from the crashes table (as strings) within a lower bound and the max date,
  -- then filter by the multi_year input.
  years AS (
    SELECT CAST(year_string AS INTEGER) AS yr
    FROM (
      SELECT DISTINCT strftime('%Y', REPORTDATE) AS year_string
      FROM crashes.crashes
      WHERE strftime('%Y', REPORTDATE) BETWEEN 
        (
          SELECT MIN(x) 
          FROM (VALUES ${inputs.multi_year.value}) AS t(x)
        )
        AND (SELECT strftime('%Y', MAX(LAST_RECORD)) FROM crashes.crashes)
    ) unique_years
    WHERE year_string IN ${inputs.multi_year.value}
    ORDER BY year_string DESC
  ),
  -- For each year in the allowed list, compute the incident count for the date range derived from date_info.
  yearly_counts AS (
    SELECT 
      y.yr,
      (
        SELECT SUM("COUNT")
        FROM crashes.crashes, date_info d
        WHERE REPORTDATE >= CAST(y.yr || '-' || d.month_day_start AS DATE)
          AND REPORTDATE < CAST(y.yr || '-' || d.month_day_end AS DATE) + INTERVAL '1 day'
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
      ) AS year_count
    FROM years y
  ),
  -- Grab the current year count using the effective current year's period.
  current_year_count AS (
    SELECT year_count AS current_count
    FROM yearly_counts, date_info
    WHERE yr = current_year
  )
  
-- Return the results, including an added column with the formatted date range.
SELECT 
  yc.yr AS Year,
  COALESCE(yc.year_count, 0) AS Count,
  COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0) AS Diff_from_current,
  CASE 
    WHEN COALESCE(yc.year_count, 0) = 0 THEN NULL
    ELSE (COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0)) * 1.0 / yc.year_count
  END AS Percent_Diff_from_current,
  (SELECT date_range_label FROM date_info) AS Date_Range
FROM yearly_counts yc
CROSS JOIN current_year_count cyc
ORDER BY yc.yr DESC;
```

```sql ytd_barchart
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
      CASE
        WHEN current_start_date = DATE_TRUNC('year', current_end_date)
            AND '${inputs.date_range.end}'::DATE = current_end_date::DATE
          THEN 'to Date'
        ELSE
          '('
          || strftime(current_start_date, '%m/%d')
          || '-'
          || strftime(current_end_date - INTERVAL '1 day', '%m/%d')
          || ')'
      END                   AS date_range_label,
      (current_end_date - current_start_date) AS date_range_days,
      strftime(current_start_date, '%m-%d')   AS month_day_start,
      strftime(current_end_date,   '%m-%d')   AS month_day_end,
      EXTRACT(YEAR FROM current_end_date)     AS current_year
    FROM report_date_range
  ),
  years AS (
    SELECT CAST(year_string AS INTEGER) AS yr
    FROM (
      SELECT DISTINCT strftime('%Y', REPORTDATE) AS year_string
      FROM crashes.crashes
      WHERE strftime('%Y', REPORTDATE) BETWEEN 
        (
          SELECT MIN(x) 
          FROM (VALUES ${inputs.multi_year.value}) AS t(x)
        )
        AND (SELECT strftime('%Y', MAX(LAST_RECORD)) FROM crashes.crashes)
    ) unique_years
    WHERE year_string IN ${inputs.multi_year.value}
    ORDER BY year_string DESC
  ),
  -- Now include severity in the grouping
  yearly_counts AS (
    SELECT 
      y.yr,
      c.SEVERITY,
      SUM(c."COUNT") AS year_count
    FROM years y
    CROSS JOIN date_info d
    JOIN crashes.crashes c
      ON c.REPORTDATE >= CAST(y.yr || '-' || d.month_day_start AS DATE)
     AND c.REPORTDATE <  CAST(y.yr || '-' || d.month_day_end   AS DATE) + INTERVAL '1 day'
     AND c.SEVERITY IN ${inputs.multi_severity.value}
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
  yc.yr AS Year,
  yc.SEVERITY,
  COALESCE(yc.year_count, 0) AS Count,
  COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0) AS Diff_from_current,
  CASE 
    WHEN COALESCE(yc.year_count, 0) = 0 THEN NULL
    ELSE (COALESCE(cyc.current_count, 0) - COALESCE(yc.year_count, 0)) * 1.0 / yc.year_count
  END AS Percent_Diff_from_current,
  (SELECT date_range_label FROM date_info) AS Date_Range
FROM yearly_counts yc
LEFT JOIN current_year_count cyc
  ON yc.SEVERITY = cyc.SEVERITY
 AND cyc.yr = (SELECT current_year FROM date_info)
ORDER BY yc.yr DESC, yc.SEVERITY;
```

```sql cy_avg
WITH
  report_date_range_cy AS (
    SELECT
      '${inputs.date_range_cy.start}'::DATE AS cy_start_date,
      '${inputs.date_range_cy.end}'::DATE AS cy_end_date
  ),
  date_info_cy AS (
    SELECT
      cy_start_date,
      cy_end_date,
      EXTRACT(MONTH FROM cy_start_date) AS start_month,
      EXTRACT(DAY FROM cy_start_date) AS start_day,
      EXTRACT(MONTH FROM cy_end_date) AS end_month,
      EXTRACT(DAY FROM cy_end_date) AS end_day
    FROM report_date_range_cy
  ),
  allowed_years AS (
    SELECT DISTINCT CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr
    FROM crashes.crashes
    WHERE CAST(strftime('%Y', REPORTDATE) AS INTEGER) IN ${inputs.multi_cy.value}
  ),
  yearly_counts AS (
    SELECT
      ay.yr,
      (
        SELECT SUM("COUNT")
        FROM crashes.crashes c,
             date_info_cy d
        WHERE
          c.REPORTDATE >= make_date(ay.yr, d.start_month, d.start_day)
          AND c.REPORTDATE < make_date(ay.yr, d.end_month, d.end_day) + INTERVAL '1 day'
          AND c.SEVERITY IN ${inputs.multi_severity.value}
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
      ) AS year_count
    FROM allowed_years ay
  )
SELECT
  ROUND(COALESCE(AVG(year_count), 0), 0) AS average_count
FROM yearly_counts;
```

```sql cy_table
WITH
  report_date_range_cy AS (
    SELECT
      '${inputs.date_range_cy.start}'::DATE AS cy_start_date,
      '${inputs.date_range_cy.end}'::DATE  AS cy_end_date
  ),
  date_info_cy AS (
    SELECT
      cy_start_date,
      cy_end_date,
      EXTRACT(MONTH FROM cy_start_date) AS start_month,
      EXTRACT(DAY FROM cy_start_date) AS start_day,
      EXTRACT(MONTH FROM cy_end_date) AS end_month,
      EXTRACT(DAY FROM cy_end_date) AS end_day,
      EXTRACT(YEAR FROM cy_end_date) AS cy_year
    FROM report_date_range_cy
  ),
  allowed_years AS (
    SELECT DISTINCT CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr
    FROM crashes.crashes
    WHERE CAST(strftime('%Y', REPORTDATE) AS INTEGER) IN ${inputs.multi_cy.value}
  ),
  yearly_counts AS (
    SELECT
      ay.yr,
      (
        SELECT SUM("COUNT")
        FROM crashes.crashes c,
             date_info_cy d
        WHERE
          c.REPORTDATE >= make_date(ay.yr, d.start_month, d.start_day) AND
          c.REPORTDATE < make_date(ay.yr, d.end_month, d.end_day) + INTERVAL '1 day' 
          AND c.SEVERITY IN ${inputs.multi_severity.value} 
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
      ) AS year_count,
      (SELECT cy_start_date FROM date_info_cy) AS cy_start_date,
      (SELECT cy_end_date FROM date_info_cy) AS cy_end_date
    FROM allowed_years ay
  )
SELECT
  yc.yr AS Year,
  COALESCE(yc.year_count, 0) AS Count,
  CASE
    WHEN LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC) IS NULL THEN 0
    ELSE LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC) - COALESCE(yc.year_count, 0)
  END AS Diff_from_previous,
  CASE
    WHEN LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC) IS NULL
         OR LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC) = 0 THEN 0
    ELSE (LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC) - COALESCE(yc.year_count, 0)) * 1.0
         / LAG(COALESCE(yc.year_count, 0)) OVER (ORDER BY yc.yr DESC)
  END AS Percent_Diff_from_previous,
  strftime('%m/%d', yc.cy_start_date) || '-' || strftime('%m/%d', yc.cy_end_date) AS Date_Range
FROM yearly_counts yc
ORDER BY yc.yr DESC;
```

```sql cy_barchart
WITH
  report_date_range_cy AS (
    SELECT
      '${inputs.date_range_cy.start}'::DATE AS cy_start_date,
      '${inputs.date_range_cy.end}'::DATE  AS cy_end_date
  ),
  date_info_cy AS (
    SELECT
      cy_start_date,
      cy_end_date,
      EXTRACT(MONTH FROM cy_start_date) AS start_month,
      EXTRACT(DAY FROM cy_start_date) AS start_day,
      EXTRACT(MONTH FROM cy_end_date) AS end_month,
      EXTRACT(DAY FROM cy_end_date) AS end_day,
      EXTRACT(YEAR FROM cy_end_date) AS cy_year
    FROM report_date_range_cy
  ),
  allowed_years AS (
    SELECT DISTINCT CAST(strftime('%Y', REPORTDATE) AS INTEGER) AS yr
    FROM crashes.crashes
    WHERE CAST(strftime('%Y', REPORTDATE) AS INTEGER) IN ${inputs.multi_cy.value}
  ),
  yearly_counts AS (
    SELECT
      ay.yr,
      c.SEVERITY,
      SUM(c."COUNT") AS year_count,
      (SELECT cy_start_date FROM date_info_cy) AS cy_start_date,
      (SELECT cy_end_date FROM date_info_cy) AS cy_end_date
    FROM allowed_years ay
    CROSS JOIN date_info_cy d
    JOIN crashes.crashes c
      ON c.REPORTDATE >= make_date(ay.yr, d.start_month, d.start_day)
     AND c.REPORTDATE <  make_date(ay.yr, d.end_month, d.end_day) + INTERVAL '1 day'
     AND c.SEVERITY IN ${inputs.multi_severity.value}
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
    GROUP BY ay.yr, c.SEVERITY
  )
SELECT
  yc.yr AS Year,
  yc.SEVERITY,
  COALESCE(yc.year_count, 0) AS Count,
  CASE
    WHEN LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC) IS NULL THEN 0
    ELSE LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC) - COALESCE(yc.year_count, 0)
  END AS Diff_from_previous,
  CASE
    WHEN LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC) IS NULL
         OR LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC) = 0 THEN 0
    ELSE (LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC) - COALESCE(yc.year_count, 0)) * 1.0
         / LAG(COALESCE(yc.year_count, 0)) OVER (PARTITION BY yc.SEVERITY ORDER BY yc.yr DESC)
  END AS Percent_Diff_from_previous,
  strftime('%m/%d', yc.cy_start_date) || '-' || strftime('%m/%d', yc.cy_end_date) AS Date_Range
FROM yearly_counts yc
ORDER BY yc.yr DESC, yc.SEVERITY;
```

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
presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year']}
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
            <b>Year {ytd_table[0].Date_Range} Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
        </div>
        <BarChart 
          data={ytd_barchart}
          subtitle=" "
          chartAreaHeight=225 
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
        >
          <ReferenceLine data={ytd_avg} y="average_count" label={`${ytd_avg[0].year_range_label}`}/>
        </BarChart>
    </Group>
    <Group>
        <DataTable data={ytd_table} wrapTitles=true rowShading=true title="{ytd_table[0].Year} {ytd_table[0].Date_Range} vs Prior Years {ytd_table[0].Date_Range} Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}">
            <Column id=Year wrap=true/>
            <Column id=Count/>
            <Column id=Diff_from_current contentType=delta downIsGood=True title=" {ytd_table[0].Year} Diff"/>
            <Column id=Percent_Diff_from_current fmt='pct0' title="{ytd_table[0].Year} % Diff"/> 
        </DataTable>
    </Group>
</Grid>

<DateRange
start={
  (() => {
    // Create a date for January 1st of the current year
    const currentYearStart = new Date(new Date().getFullYear(), 0, 1);
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/New_York'
    }).format(currentYearStart);
  })()
}
end={
      (() => {
        const currentYearEnd = new Date(new Date().getFullYear(), 11, 31);
        return new Intl.DateTimeFormat('en-CA', {
          timeZone: 'America/New_York'
        }).format(currentYearEnd);
      })()
    }
  name="date_range_cy"
  presetRanges={['Last Year']}
  defaultValue='Last Year'
  description="Date range set to the entirety of the previous year"
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

<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Calendar Year ({cy_table[0].Date_Range}) Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
        </div>
        <BarChart 
          data={cy_barchart}
          subtitle=" "
          chartAreaHeight=202
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
        >
          <ReferenceLine data={cy_avg} y="average_count" label="Average"/>
        </BarChart>
    </Group>
    <Group>
        <DataTable data={cy_table} wrapTitles=true rowShading=true title="Calendar  Year ({cy_table[0].Date_Range}) Over Year Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`}">
            <Column id=Year wrap=true/>
            <Column id=Count/>
            <Column id=Diff_from_previous contentType=delta downIsGood=True title="Prior Year Diff"/>
            <Column id=Percent_Diff_from_previous fmt='pct0' title="Prior Year % Diff"/> 
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons.
</Note>