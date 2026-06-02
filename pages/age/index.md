---
title: Age Distribution
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
sidebar_position: 9
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

mode_list AS (
    -- Strip parentheses & quotes, split the comma list, then UNNEST
    SELECT
        TRIM(val) AS mode
    FROM UNNEST(
        string_split(
            REPLACE(
                TRIM(BOTH '()' FROM ${inputs.multi_mode_dd.value}),
                '''',''
            ),
            ','
        )
    ) AS t(val)
),

all_combinations AS (
    -- Every bucket × every selected mode
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        ml.mode
    FROM all_buckets ab
    CROSS JOIN mode_list ml
),

binned_raw AS (
    -- Sum injuries per bucket × mode
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        c.MODE         AS mode,
        SUM(c.COUNT)   AS injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c
      ON (
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
        OR (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
     AND c.MODE     IN ${inputs.multi_mode_dd.value}
     AND c.SEVERITY IN ${inputs.multi_severity.value}
     AND c.REPORTDATE BETWEEN '${inputs.date_range.start}'::DATE
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
),

final AS (
    -- Left-join to fill in zeroes for missing bucket × mode combos
    SELECT
        ac.bucket_order,
        ac.bucket_label,
        ac.mode        AS MODE,
        COALESCE(br.injuries, 0) AS Injuries
    FROM all_combinations ac
    LEFT JOIN binned_raw br
      ON ac.bucket_order = br.bucket_order
     AND ac.mode         = br.mode
)

SELECT
    bucket_label,
    MODE,
    Injuries
FROM final
ORDER BY
    bucket_order,
    CASE 
        WHEN MODE = 'Pedestrian'    THEN 1
        WHEN MODE = 'Bicyclist'     THEN 2
        WHEN MODE = 'Passenger'     THEN 3
        WHEN MODE = 'Driver'        THEN 4
        WHEN MODE = 'Other'         THEN 5
        WHEN MODE = 'Scooterist*'   THEN 6         
        WHEN MODE = 'Motorcyclist*' THEN 7        
    END;
```

```sql age_yoy
WITH 
-- 1. Compute the “true” end_date (+1 day) and start_date
report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD)::DATE FROM crashes.crashes)
        THEN (SELECT MAX(LAST_RECORD)::DATE FROM crashes.crashes) + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
date_info AS (
    SELECT
        start_date,
        end_date,
        CASE
            -- Full calendar year → "YYYY"
            WHEN start_date = DATE_TRUNC('year', start_date)
             AND end_date   = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
            THEN EXTRACT(YEAR FROM start_date)::VARCHAR
            -- Current YTD → "YYYY YTD"
            WHEN start_date = DATE_TRUNC('year', CURRENT_DATE)
             AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
            THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
            -- Default formatted range
            ELSE
                strftime(start_date, '%m/%d/%y')
                || '-'
                || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
        END AS current_period_range,
        -- Abbreviated year (YY)
        EXTRACT(YEAR FROM end_date - INTERVAL '1 day') % 100 AS current_year_short
    FROM report_date_range
),
offset_period AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)  -- guard
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
      (SELECT end_date   FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
),
prior_date_label AS (
    SELECT
        CASE
            -- Full calendar year → "YYYY"
            WHEN prior_start_date = DATE_TRUNC('year', prior_start_date)
             AND prior_end_date   = DATE_TRUNC('year', prior_start_date) + INTERVAL '1 year'
            THEN EXTRACT(YEAR FROM prior_start_date)::VARCHAR
            -- Prior YTD → "YYYY YTD"
            WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', CURRENT_DATE)
             AND '${inputs.date_range.end}'::DATE = (SELECT end_date FROM date_info) - INTERVAL '1 day'
            THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
            -- Default formatted range
            ELSE
                strftime(prior_start_date, '%m/%d/%y')
                || '-'
                || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
        END AS prior_period_range,
        -- Abbreviated year (YY)
        EXTRACT(YEAR FROM prior_end_date - INTERVAL '1 day') % 100 AS prior_year_short
    FROM prior_date_info
),
-- Buckets
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
-- Current-period injuries
current_binned_raw AS (
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        SUM(c.COUNT) AS injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c
      ON (
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
        OR (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
     AND c.MODE IN ${inputs.multi_mode_dd.value}
     AND c.SEVERITY IN ${inputs.multi_severity.value}
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
-- Prior-period injuries
prior_binned_raw AS (
    SELECT
        ab.bucket_order,
        ab.bucket_label,
        SUM(c.COUNT) AS injuries
    FROM all_buckets ab
    LEFT JOIN crashes.crashes c
      ON (
           (ab.bucket_label = 'Null' AND CAST(c.AGE AS INTEGER) = ab.lower_bound)
        OR (ab.bucket_label <> 'Null' AND CAST(c.AGE AS INTEGER) BETWEEN ab.lower_bound AND ab.upper_bound)
         )
     AND c.MODE IN ${inputs.multi_mode_dd.value}
     AND c.SEVERITY IN ${inputs.multi_severity.value}
     AND c.REPORTDATE BETWEEN (SELECT prior_start_date FROM prior_date_info)
                          AND (SELECT prior_end_date   FROM prior_date_info)
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
-- Final union wrapped in subquery
SELECT *
FROM (
    SELECT
        bucket_order,
        bucket_label || ' (''' || (SELECT current_year_short FROM date_info) || ')' AS bucket_label,
        COALESCE(injuries, 0) AS Injuries,
        (SELECT current_period_range FROM date_info) AS YTD
    FROM current_binned_raw
    UNION ALL
    SELECT
        bucket_order,
        bucket_label || ' (''' || (SELECT prior_year_short FROM prior_date_label) || ')' AS bucket_label,
        COALESCE(injuries, 0) AS Injuries,
        (SELECT prior_period_range FROM prior_date_label) AS YTD
    FROM prior_binned_raw
) combined
ORDER BY bucket_order, YTD;
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
            <b>Age Breakdown of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {mode_severity_selection[0].MODE_SELECTION} ({age_yoy[1].YTD})</b>
        <BarChart 
            data={age_mode}
            chartAreaHeight=320
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Count" 
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
            <b>Year Over Year Age Breakdown of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {mode_severity_selection[0].MODE_SELECTION}</b>
        </div>
        <BarChart 
            data={age_yoy}
            chartAreaHeight=160
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Count" 
            series=YTD
            seriesOrder={[age_yoy[1].YTD,age_yoy[0].YTD]}
            xAxisLabels={true} 
            xTickMarks={true} 
            leftPadding={10} 
            rightPadding={30}
            sort=false
            swapXY=true
            echartsOptions={{
                tooltip: { show: false }
            }}            
        />
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>

<Details title="About Road Users">

<table border="1" cellspacing="0" cellpadding="8">
    <thead>
      <tr>
        <th>Icon</th>
        <th>Road User</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/driver.png" alt="Driver Icon" width="32"></td>
        <td>Driver</td>
        <td>A person operating a motor vehicle.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/passenger.png" alt="Passenger Icon" width="32"></td>
        <td>Passenger</td>
        <td>A person riding along in a motor vehicle.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/pedestrian.png" alt="Pedestrian Icon" width="32"></td>
        <td>Pedestrian</td>
        <td>A person moving on foot or using a wheelchair..</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/bicyclist.png" alt="Bicyclist Icon" width="32"></td>
        <td>Bicyclist</td>
        <td>A person riding a bicycle or motorized bicycle (e-bike).</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/motorcyclist.png" alt="Motorcyclist Icon" width="32"></td>
        <td>Motorcyclist*</td>
        <td>A person riding a motorcycle or motor‑driven cycle (moped). *Fatal only.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/scooterist.png" alt="Scooterist Icon" width="32"></td>
        <td>Scooterist*</td>
        <td>A person using a standing scooter or personal mobility device. *Fatal only.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/unknown.png" alt="Other Icon" width="32"></td>
        <td>Other**</td>
        <td>Includes users of motrocycles, motor‑driven cycles (mopeds), personal mobility devices (such as standing scooters), and other or unknown classifications. **Major and minor injury only.</td>
      </tr>
    </tbody>
  </table>

</Details>