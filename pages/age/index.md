---
title: Age Distribution
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
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

```sql min_max_age
SELECT 
    MAX(AGE) AS unique_max_age,
    MIN(AGE) AS unique_min_age
FROM crashes.crashes
WHERE SEVERITY IN ${inputs.multi_severity.value}
  AND MODE IN ${inputs.multi_mode_dd.value}
  AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
      AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
  AND AGE BETWEEN 
      ${inputs.min_age.value}
      AND LEAST(${inputs.max_age.value}, 119);
```

```sql age_severity
WITH buckets(bucket_order, bucket_label, lower_bound, upper_bound) AS (
    VALUES
        (0,    '0-10',   0,   10),
        (11,   '11-20',  11,  20),
        (21,   '21-30',  21,  30),
        (31,   '31-40',  31,  40),
        (41,   '41-50',  41,  50),
        (51,   '51-60',  51,  60),
        (61,   '61-70',  61,  70),
        (71,   '71-80',  71,  80),
        (81,   '> 80',   81,  110)
),
null_bucket AS (
    SELECT 9999 AS bucket_order, 'Null' AS bucket_label, 120 AS lower_bound, 120 AS upper_bound
),
all_buckets AS (
    SELECT * FROM buckets
    UNION ALL
    SELECT * FROM null_bucket
),
binned_data AS (
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        c.SEVERITY,
        COALESCE(SUM(c.COUNT), 0) AS Injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c 
      ON (
            -- For the Null bucket, match records where AGE equals 120 exactly
            (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
            OR
            -- For all other buckets, match where AGE falls between the bucket's lower and upper bounds
            (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
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
    GROUP BY ab.bucket_order, ab.bucket_label, c.SEVERITY
)
SELECT
    bucket_label,
    SEVERITY,
    Injuries
FROM binned_data
WHERE SEVERITY IS NOT NULL
ORDER BY 
    bucket_order,
    CASE 
        WHEN SEVERITY = 'Minor' THEN 1
        WHEN SEVERITY = 'Major' THEN 2
        WHEN SEVERITY = 'Fatal' THEN 3
    END;
```

```sql age_mode
WITH buckets(bucket_order, bucket_label, lower_bound, upper_bound) AS (
    VALUES
        (0,    '0-10',   0,   10),
        (11,   '11-20',  11,  20),
        (21,   '21-30',  21,  30),
        (31,   '31-40',  31,  40),
        (41,   '41-50',  41,  50),
        (51,   '51-60',  51,  60),
        (61,   '61-70',  61,  70),
        (71,   '71-80',  71,  80),
        (81,   '> 80',   81,  110)
),
null_bucket AS (
    SELECT 9999 AS bucket_order, 'Null' AS bucket_label, 120 AS lower_bound, 120 AS upper_bound
),
all_buckets AS (
    SELECT * FROM buckets
    UNION ALL
    SELECT * FROM null_bucket
),
binned_data AS (
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        c.MODE,
        COALESCE(SUM(c.COUNT), 0) AS Injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c 
      ON (
           -- For the Null bucket, match records where AGE equals 120 exactly
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
           OR
           -- For all other buckets, match where AGE falls between the bucket's lower and upper bounds
           (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
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
    GROUP BY ab.bucket_order, ab.bucket_label, c.MODE
)
SELECT
    bucket_label,
    MODE,
    Injuries
FROM binned_data
WHERE MODE IS NOT NULL
ORDER BY 
    bucket_order,
    CASE 
        WHEN MODE = 'Pedestrian' THEN 1
        WHEN MODE = 'Other' THEN 2
        WHEN MODE = 'Bicyclist' THEN 3
        WHEN MODE = 'Scooterist*' THEN 4
        WHEN MODE = 'Motorcyclist*' THEN 5
        WHEN MODE = 'Passenger' THEN 6
        WHEN MODE = 'Driver' THEN 7
        ELSE 8  -- for any other cases, place them last
    END;
```

```sql age_comparison
WITH 
  -- 1. Compute the “true” end_date (+1 day) and start_date
  report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(REPORTDATE)::DATE FROM crashes.crashes)
        THEN (SELECT MAX(REPORTDATE)::DATE FROM crashes.crashes) + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
  ),

  -- 2. Build a single label: YTD only if start=Jan 1 of the year AND end hits max data;
  --    otherwise always “MM/DD/YY–MM/DD/YY”
  date_info AS (
    SELECT
      start_date,
      end_date,
      CASE
        WHEN start_date = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
         AND '${inputs.date_range.end}'::DATE = (SELECT MAX(REPORTDATE)::DATE FROM crashes.crashes)
        THEN EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::VARCHAR || ' YTD'
        ELSE
          strftime(start_date,            '%m/%d/%y')
          || '-' ||
          strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS current_period_range,
      (end_date - start_date) AS date_range_days
    FROM report_date_range
  ),

  -- 3. Figure out your “offset” to compare prior spans
  offset_period AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)  -- guard: >5 yrs
        WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
        WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
        WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
        WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
        ELSE INTERVAL '1 year'
      END AS interval_offset
    FROM date_info
  ),

  -- 4. Deduce the prior span’s start/end
  prior_date_info AS (
    SELECT
      (SELECT start_date      FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
      (SELECT end_date        FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
  ),

  -- 5. Label that prior span with the same “YTD only-if” logic
  prior_date_label AS (
    SELECT
      CASE
        WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', (SELECT end_date FROM date_info))
         AND '${inputs.date_range.end}'::DATE = (SELECT MAX(REPORTDATE)::DATE FROM crashes.crashes)
        THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
        ELSE
          strftime(prior_start_date,         '%m/%d/%y')
          || '-' ||
          strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS prior_period_range
    FROM prior_date_info
  ),

  -- 6. Define your age‐buckets (0–10, 11–20, …, >80, Null)
  buckets(bucket_order, bucket_label, lower_bound, upper_bound) AS (
    VALUES
      (0,    '0-10',   0,   10),
      (11,   '11-20',  11,  20),
      (21,   '21-30',  21,  30),
      (31,   '31-40',  31,  40),
      (41,   '41-50',  41,  50),
      (51,   '51-60',  51,  60),
      (61,   '61-70',  61,  70),
      (71,   '71-80',  71,  80),
      (81,   '> 80',   81,  110)
  ),
  null_bucket AS (
    SELECT 9999 AS bucket_order, 'Null' AS bucket_label, 120 AS lower_bound, 120 AS upper_bound
  ),
  all_buckets AS (
    SELECT * FROM buckets
    UNION ALL
    SELECT * FROM null_bucket
  ),

  -- 7. Aggregate current‐period injuries by bucket
  current_age AS (
    SELECT 
      ab.bucket_order,
      ab.bucket_label,
      COALESCE(SUM(c.COUNT), 0) AS Injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c 
      ON (
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
           OR
           (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
         AND c.MODE       IN ${inputs.multi_mode_dd.value}
         AND c.SEVERITY   IN ${inputs.multi_severity.value}
         AND c.REPORTDATE BETWEEN (SELECT start_date FROM date_info)
                              AND (SELECT end_date   FROM date_info)
         AND c.AGE BETWEEN ${inputs.min_age.value}
                     AND (
                       CASE 
                         WHEN ${inputs.min_age.value} <> 0 
                          AND ${inputs.max_age.value} = 120
                         THEN 119
                         ELSE ${inputs.max_age.value}
                       END
                     )
    GROUP BY ab.bucket_order, ab.bucket_label
  ),

  -- 8. Aggregate prior‐period injuries by bucket
  prior_age AS (
    SELECT 
      ab.bucket_order,
      ab.bucket_label,
      COALESCE(SUM(c.COUNT), 0) AS Injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c 
      ON (
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
           OR
           (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
         AND c.MODE       IN ${inputs.multi_mode_dd.value}
         AND c.SEVERITY   IN ${inputs.multi_severity.value}
         AND c.REPORTDATE BETWEEN (SELECT start_date     FROM date_info) - (SELECT interval_offset FROM offset_period)
                              AND (SELECT end_date       FROM date_info) - (SELECT interval_offset FROM offset_period)
         AND c.AGE BETWEEN ${inputs.min_age.value}
                     AND (
                       CASE 
                         WHEN ${inputs.min_age.value} <> 0 
                          AND ${inputs.max_age.value} = 120
                         THEN 119
                         ELSE ${inputs.max_age.value}
                       END
                     )
    GROUP BY ab.bucket_order, ab.bucket_label
  )

-- 9. Union current/prior, attach the correct period label, and sort
SELECT 
  bucket_label,
  Injuries,
  Period_range
FROM (
  SELECT 
    ca.bucket_order,
    ca.bucket_label,
    ca.Injuries,
    (SELECT current_period_range FROM date_info) AS Period_range
  FROM current_age ca

  UNION ALL

  SELECT 
    pa.bucket_order,
    pa.bucket_label,
    pa.Injuries,
    (SELECT prior_period_range FROM prior_date_label) AS Period_range
  FROM prior_age pa
) AS combined
ORDER BY bucket_order, Period_range;

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
  presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year']}
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
    description='The minumum age for the current selection of filters is {min_max_age[0].unique_min_age}.'
/>

<Dropdown 
    data={age_range} 
    name="max_age"
    value=age_int
    title="Max Age"
    order="age_int desc"
    defaultValue={120}
    description='Age 120 serves as a placeholder for missing age values in the records. However, missing values will be automatically excluded from the query if the default 0-120 range is changed by the user. The maximum age for the current selection of filters is {min_max_age[0].unique_max_age}.'
/>

<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Age Distribution of {mode_severity_selection[0].MODE_SELECTION} by {`${mode_severity_selection[0].SEVERITY_SELECTION}`} Injuries ({age_comparison[1].Period_range})</b>
        </div>
        <BarChart 
            data={age_severity}
            chartAreaHeight=300
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Count" 
            series=SEVERITY
            seriesColors={{"Minor": '#ffdf00',"Major": '#ff9412',"Fatal": '#ff5a53'}}
            xAxisLabels={true} 
            xTickMarks={true} 
            leftPadding={10} 
            rightPadding={30}
            sort=false
            swapXY=true
        />
    </Group>
    <Group>
        <div style="font-size: 14px;">
            <b>Age Distribution of {mode_severity_selection[0].MODE_SELECTION} by {`${mode_severity_selection[0].SEVERITY_SELECTION}`} Injuries ({age_comparison[1].Period_range})</b>
        </div>
        <BarChart 
            data={age_mode}
            chartAreaHeight=300
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Count" 
            series=MODE
            seriesColors={{"Pedestrian": '#00FFD4',"Other": '#06DFC8',"Bicyclist": '#0BBFBC',"Scooterist*": '#119FB0',"Motorcyclist*": '#167FA3',"Passenger": '#1C5F97',"Driver": '#271F7F',"Unknown": '#213F8B'}}
            xAxisLabels={true} 
            xTickMarks={true} 
            leftPadding={10} 
            rightPadding={30}
            sort=false
            swapXY=true
        />
    </Group>
</Grid>

<div style="font-size: 14px;">
    <b>Percentage Breakdown of {mode_severity_selection[0].SEVERITY_SELECTION} Injuries for {mode_severity_selection[0].MODE_SELECTION} by Age Group</b>
</div>
<BarChart 
    data={age_comparison}
    chartAreaHeight=100
    x=Period_range
    y=Injuries
    swapXY=true
    yFmt=pct0
    series=bucket_label
    labels={true}
    type=stacked100
/>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>

<Details title="About Road Users">
<b>Road User</b> type <b>'Other'</b> includes motor-driven cycles (commonly referred to as mopeds and motorcycles), as well as personal mobility devices, such as standing scooters. The term <b>'Scooterist'</b> refers to the user of a standing scooter, while <b>'Motorcyclist'</b> applies to users of motor-driven cycles.
</Details>