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
  -- Define the current period based on your inputs
  report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE >= (SELECT CAST(MAX(REPORTDATE) AS DATE) FROM crashes.crashes)::DATE 
          THEN (SELECT MAX(REPORTDATE) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
  ),
  date_info AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN start_date = DATE_TRUNC('year', end_date)
             AND '${inputs.date_range.end}'::DATE = (end_date::DATE - INTERVAL '1 day')
          THEN EXTRACT(YEAR FROM end_date)::VARCHAR || ' YTD'
        WHEN '${inputs.date_range.end}'::DATE > (end_date::DATE - INTERVAL '1 day')
          THEN strftime(start_date, '%m/%d/%y') || '-' || strftime((end_date::DATE - INTERVAL '1 day'), '%m/%d/%y')
        ELSE 
          strftime(start_date, '%m/%d/%y') || '-' || strftime((end_date - INTERVAL '1 day'), '%m/%d/%y')
      END AS current_period_range,
      (end_date - start_date) AS date_range_days
    FROM report_date_range
  ),
  offset_period AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0) -- force error if more than 5 years
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
        WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', (SELECT end_date FROM date_info))
          AND '${inputs.date_range.end}'::DATE = (SELECT CAST(MAX(REPORTDATE) AS DATE) FROM crashes.crashes)::DATE
          THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
        WHEN '${inputs.date_range.end}'::DATE > (SELECT CAST(MAX(REPORTDATE) AS DATE) FROM crashes.crashes)::DATE
          THEN strftime(prior_start_date, '%m/%d/%y') || '-' || strftime((prior_end_date - INTERVAL '1 day'), '%m/%d/%y')
        ELSE 
          strftime(prior_start_date, '%m/%d/%y') || '-' || strftime((prior_end_date - INTERVAL '1 day'), '%m/%d/%y')
      END AS prior_period_range
    FROM prior_date_info
  ),
  -- Define age buckets plus the special "Null" bucket
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
  -- Get the aggregated injuries per bucket for the current period
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
         AND c.MODE IN ${inputs.multi_mode_dd.value}
         AND c.SEVERITY IN ${inputs.multi_severity.value}
         AND c.REPORTDATE >= (SELECT start_date FROM date_info)
         AND c.REPORTDATE <= (SELECT end_date FROM date_info)
         AND c.AGE BETWEEN ${inputs.min_age.value}
                      AND (CASE 
                             WHEN ${inputs.min_age.value} <> 0 
                             AND ${inputs.max_age.value} = 120
                             THEN 119
                             ELSE ${inputs.max_age.value}
                           END)
    GROUP BY ab.bucket_order, ab.bucket_label
  ),
  -- Get the aggregated injuries per bucket for the prior period
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
         AND c.SEVERITY IN ${inputs.multi_severity.value}
         AND c.MODE IN ${inputs.multi_mode_dd.value}
         AND c.REPORTDATE >= ((SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period))
         AND c.REPORTDATE <= ((SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period))
         AND c.AGE BETWEEN ${inputs.min_age.value}
                      AND (CASE 
                             WHEN ${inputs.min_age.value} <> 0 
                             AND ${inputs.max_age.value} = 120
                             THEN 119
                             ELSE ${inputs.max_age.value}
                           END)
    GROUP BY ab.bucket_order, ab.bucket_label
  )
  
-- Combine the results from both periods
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
SELECT
    STRING_AGG(DISTINCT MODE, ', ' ORDER BY MODE ASC) AS MODE_SELECTION,
    STRING_AGG(DISTINCT SEVERITY, ', ' ORDER BY SEVERITY ASC) AS SEVERITY_SELECTION
FROM
    crashes.crashes
WHERE
    MODE IN ${inputs.multi_mode_dd.value}
    AND SEVERITY IN ${inputs.multi_severity.value};
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
  title="Select Time Period"
  name="date_range"
  presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year']}
  defaultValue="Year to Today"
  description="By default, there is a two-day lag after the latest update"
/>

<Dropdown
    data={unique_severity} 
    name=multi_severity
    value=SEVERITY
    title="Select Severity"
    multiple=true
    defaultValue={['Fatal', 'Major']}
/>

<Dropdown
    data={unique_mode} 
    name=multi_mode_dd
    value=MODE
    title="Select Road User"
    multiple=true
    selectAllByDefault=true
    description="*Only fatal"
/>

<Dropdown 
    data={age_range} 
    name=min_age
    value=age_int
    title="Select Min Age" 
    defaultValue={0}
    description='The minumum age for the current selection of filters is {min_max_age[0].unique_min_age}.'
/>

<Dropdown 
    data={age_range} 
    name="max_age"
    value=age_int
    title="Select Max Age"
    order="age_int desc"
    defaultValue={120}
    description='Age 120 serves as a placeholder for missing age values in the records. However, missing values will be automatically excluded from the query if the default 0-120 range is changed by the user. The maximum age for the current selection of filters is {min_max_age[0].unique_max_age}.'
/>

<Alert status="info">
The selection for <b>Severity</b> is: <b><Value data={mode_severity_selection} column="SEVERITY_SELECTION"/></b>. The selection for <b>Road User</b> is: <b><Value data={mode_severity_selection} column="MODE_SELECTION"/></b> <Info description="*Fatal only." color="primary" />
</Alert>

<Grid cols=2>
    <Group>
        <BarChart 
            data={age_severity}
            title="Age Distribution by Severity"
            chartAreaHeight=300
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Injuries" 
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
        <BarChart 
            data={age_mode}
            title="Age Distribution by Road User"
            chartAreaHeight=300
            x="bucket_label" 
            y="Injuries"
            labels={true} 
            yAxisTitle="Injuries" 
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

<BarChart 
    data={age_comparison}
    title="Percentage Breakdown of Injuries by Age Group"
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