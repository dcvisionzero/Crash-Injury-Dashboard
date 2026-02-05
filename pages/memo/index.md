---
title: Fatal Crash Memos
queries:
   - fatality: fatality.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_link: false
---

```sql fatality_with_link
select *, '/memo/' || DeathCaseID as link
from ${fatality}
```

```sql unique_mode
SELECT 
    replace(MODE, '*', '') AS MODE,
FROM crashes.crashes
GROUP BY 1
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
    '/memo/' || DeathCaseID AS link
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
    'Last Year',
    'All Time'
  ]}
  defaultValue={'All Time'}
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

<div style="font-size: 14px;">
    <b>Table of Fatal Crash Memos for {`${mode_selection[0].MODE_SELECTION}`}</b>
</div>
<Note class='text-sm'>
    Select a fatal crash memo in the table to see the memo about it and the post-crash follow-up.
</Note>
<DataTable data={inc_map} link=link wrapTitles=true rowShading=true search=true rows=1000>
    <Column id=REPORTDATE title="Date" fmt='mm/dd/yy hh:mm' wrap=true/>
    <Column id=MODE title="Road User" wrap=true/>
    <Column id=CCN title="CCN" wrap=true/>
    <Column id=DeathCaseID title="Case ID" wrap=true/>
    <Column id=Age/>
    <Column id=ADDRESS wrap=true/>
</DataTable>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>

<Details title="About this dashboard">

    This dashboard shows traffic fatalities in the District of Columbia and can be filtered from 2017-present. Following a fatal crash, the DDOT team visits the site and, in coordination with The Metropolitan Police Department's (MPD) Major Crash Investigation Unit, determines if there are any short-term measures that DDOT can install to improve safety for all roadway users. Starting in 2021, site visit findings and follow-up can be found in the docked window on the right for each fatality.
    
    Adjust the selection for Road User, Date Range, and Age filters to refine the results in the map nad table. All charts will update to reflect the fatalities affected by the filters. 
    
    Data are updated twice: first, as soon as the Vision Zero Office receives a fatality memo from the Metropolitan Police Department (MPD) and second, after a crash site visit has been completed by DDOT.

</Details>