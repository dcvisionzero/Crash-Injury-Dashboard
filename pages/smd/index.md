---
title: Injuries by SMD
queries:
   - smd_link: smd_link.sql
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 5
---

Single Memeber Districts (SMDs)

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

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
```

```sql unique_smd
select 
    SMD
from smd.smd_2023
group by 1
```

```sql period_comp_smd
WITH 
    report_date_range AS (
        SELECT
        CASE 
            WHEN '${inputs.date_range.end}'::DATE 
                >= (SELECT MAX(REPORTDATE) FROM crashes.crashes)::DATE
            THEN (SELECT MAX(REPORTDATE) FROM crashes.crashes)::DATE + INTERVAL '1 day'
            ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
        END   AS end_date,
        '${inputs.date_range.start}'::DATE AS start_date
    ),
    date_info AS (
        SELECT
        start_date,
        end_date,
        CASE
            WHEN start_date = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
            AND '${inputs.date_range.end}'::DATE = (SELECT MAX(REPORTDATE) FROM crashes.crashes)::DATE
            THEN EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::VARCHAR || ' YTD'
            ELSE
            strftime(start_date, '%m/%d/%y')
            || '-'
            || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
        END AS date_range_label,
        (end_date - start_date) AS date_range_days
        FROM report_date_range
    ),
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
    unique_smd AS (
        SELECT 
            SMD 
        FROM 
            smd.smd_2023 
        GROUP BY 
            SMD
    ),
    current_period AS (
        SELECT 
            crashes.SMD, 
            SUM(crashes.COUNT) AS sum_count
        FROM 
            crashes.crashes 
        JOIN 
            unique_smd ua 
            ON crashes.SMD = ua.SMD
        WHERE 
            crashes.SEVERITY IN ${inputs.multi_severity.value} 
            AND crashes.MODE IN ${inputs.multi_mode_dd.value}
            AND crashes.REPORTDATE BETWEEN (SELECT start_date FROM date_info)
            AND (SELECT end_date FROM date_info)
            AND crashes.AGE BETWEEN ${inputs.min_age.value}
                                AND (
                                    CASE 
                                        WHEN ${inputs.min_age.value} <> 0 
                                        AND ${inputs.max_age.value} = 120
                                        THEN 119
                                        ELSE ${inputs.max_age.value}
                                    END
                                    )
        GROUP BY 
            crashes.SMD
    ), 
    prior_period AS (
        SELECT 
            crashes.SMD, 
            SUM(crashes.COUNT) AS sum_count
        FROM 
            crashes.crashes 
        JOIN 
            unique_smd ua 
            ON crashes.SMD = ua.SMD
        WHERE 
            crashes.SEVERITY IN ${inputs.multi_severity.value} 
            AND crashes.MODE IN ${inputs.multi_mode_dd.value}
            AND crashes.REPORTDATE BETWEEN (
                    (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period)
                ) AND (
                    (SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period)
                )
            AND crashes.AGE BETWEEN ${inputs.min_age.value}
                                AND (
                                    CASE 
                                        WHEN ${inputs.min_age.value} <> 0 
                                        AND ${inputs.max_age.value} = 120
                                        THEN 119
                                        ELSE ${inputs.max_age.value}
                                    END
                                    )
        GROUP BY 
            crashes.SMD
    ),
    prior_date_info AS (
        SELECT
            (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
            (SELECT end_date   FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
    ),
    prior_date_label AS (
        SELECT
        CASE
            WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
            AND '${inputs.date_range.end}'::DATE = (SELECT MAX(REPORTDATE) FROM crashes.crashes)::DATE
            THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
            ELSE
            strftime(prior_start_date,   '%m/%d/%y')
            || '-'
            || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
        END AS prior_date_range_label
        FROM prior_date_info
    )
SELECT 
    mas.SMD,
    '/SMD/' || mas.SMD AS link,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    COALESCE(pp.sum_count, 0) AS prior_period_sum, 
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE 
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) != 0 THEN 
            ((COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0)) / COALESCE(pp.sum_count, 0))
        WHEN COALESCE(pp.sum_count, 0) != 0 AND COALESCE(cp.sum_count, 0) = 0 THEN -1
        ELSE NULL 
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range
FROM 
    unique_smd mas
LEFT JOIN 
    current_period cp ON mas.SMD = cp.SMD
LEFT JOIN 
    prior_period pp ON mas.SMD = pp.SMD;
```

```sql smd_map
SELECT
    a.SMD,
    COALESCE(SUM(c.COUNT), 0) AS count,
    '/SMD/' || a.SMD AS link
FROM smd.smd_2023 a
LEFT JOIN crashes.crashes c 
    ON a.SMD = c.SMD
    AND c.MODE IN ${inputs.multi_mode_dd.value}
    AND c.SEVERITY IN ${inputs.multi_severity.value}
    AND c.REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
    AND (('${inputs.date_range.end}'::DATE)+ INTERVAL '1 day')
    AND c.AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                            )
GROUP BY
    a.SMD
ORDER BY
    a.SMD;
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
            <b>{mode_severity_selection[0].SEVERITY_SELECTION} for {mode_severity_selection[0].MODE_SELECTION} by SMD ({period_comp_smd[0].current_period_range})</b>
        </div>
        <Note>
            Select an SMD to zoom in and see details about crash-related injuries within that SMD.
        </Note>
        <BaseMap
          height=450
          startingZoom=11
        >
        <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00 ignoreZoom=true
            tooltip={[
                {id: 'ROUTENAME'}
            ]}
        />
        <Areas data={smd_map} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/smd_2023.geojson' geoId=SMD areaCol=SMD value=count link=link min=0 opacity=0.7 borderWidth=1 borderColor='#A9A9A9'/>
        </BaseMap>
        <Note>
            The purple lines represent DC's High Injury Network
        </Note>
    </Group>    
    <Group>
        <DataTable data={period_comp_smd} sort="current_period_sum desc" title="Year Over Year Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by SMD" search=true wrapTitles=true rowShading=true link=link>
            <Column id=SMD title="SMD"/>
            <Column id=current_period_sum title={`${period_comp_smd[0].current_period_range}`} />
            <Column id=prior_period_sum title={`${period_comp_smd[0].prior_period_range}`}  />
            <Column id=difference title="Diff" contentType=delta downIsGood=True />
            <Column id=percentage_change fmt='pct0' title="% Diff"/> 
        </DataTable>
        <Note>
            The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons. The maximum comparison period is 5 years.
        </Note>
    </Group>
</Grid>