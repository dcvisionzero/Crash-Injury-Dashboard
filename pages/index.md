---
title: DC Vision Zero Traffic Fatalities and Injuries
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
---

<Tabs>
<Tab label="{`${yoy_text_fatal_3ytd[0].current_year_label}`} vs {`${yoy_text_fatal_3ytd[0].prior_period_label}`}">

    - As of <Value data={yoy_text_fatal_3ytd} column="max_report_date_formatted"/> there <Value data={yoy_text_fatal_3ytd} column="has_have"/> been <Value data={yoy_text_fatal_3ytd} column="current_year_sum" agg=sum/> <Value data={yoy_text_fatal_3ytd} column="fatality"/> among all road users in <Value data={yoy_text_fatal_3ytd} column="current_year" fmt='####","'/>   <Value data={yoy_text_fatal_3ytd} column="difference" agg=sum fmt='####.0' /> <Value data={yoy_text_fatal_3ytd} column="difference_text"/> (<Delta data={yoy_text_fatal_3ytd} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the last three-years-to-date average.
    - As of <Value data={yoy_text_major_injury_3ytd} column="max_report_date_formatted"/> there <Value data={yoy_text_major_injury_3ytd} column="has_have"/> been <Value data={yoy_text_major_injury_3ytd} column="current_year_sum" agg=sum/> <Value data={yoy_text_major_injury_3ytd} column="major_injury"/> among all road users in <Value data={yoy_text_major_injury_3ytd} column="current_year" fmt='####","'/>   <Value data={yoy_text_major_injury_3ytd} column="difference" agg=sum fmt='####.0' /> <Value data={yoy_text_major_injury_3ytd} column="difference_text"/> (<Delta data={yoy_text_major_injury_3ytd} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the last three-years-to-date average.

</Tab>
<Tab label="{`${yoy_text_fatal_3ytd[0].current_year_label}`} vs {`${yoy_text_fatal_3ytd[0].last_year_label}`} YTD">

    - As of <Value data={yoy_text_fatal} column="max_report_date_formatted"/> there <Value data={yoy_text_fatal} column="has_have"/> been <Value data={yoy_text_fatal} column="current_year_sum" agg=sum/> <Value data={yoy_text_fatal} column="fatality"/> among all road users in <Value data={yoy_text_fatal} column="current_year" fmt='####","'/>   <Value data={yoy_text_fatal} column="difference" agg=sum fmt='####' /> <Value data={yoy_text_fatal} column="difference_text"/> (<Delta data={yoy_text_fatal} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the same period in <Value data={yoy_text_fatal} column="year_prior" fmt="####."/>
    - As of <Value data={yoy_text_major_injury} column="max_report_date_formatted"/> there <Value data={yoy_text_major_injury} column="has_have"/> been <Value data={yoy_text_major_injury} column="current_year_sum" agg=sum/> <Value data={yoy_text_major_injury} column="major_injury"/> among all road users in <Value data={yoy_text_major_injury} column="current_year" fmt='####","'/>   <Value data={yoy_text_major_injury} column="difference" agg=sum fmt='####' /> <Value data={yoy_text_major_injury} column="difference_text"/> (<Delta data={yoy_text_major_injury} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the same period in <Value data={yoy_text_major_injury} column="year_prior" fmt="####."/>

</Tab>
</Tabs>

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

```sql period_comp_mode
WITH 
  report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END   AS end_date,
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
  modes_and_severities AS (
    SELECT DISTINCT MODE
    FROM crashes.crashes
  ),
  current_period AS (
    SELECT 
      MODE,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE BETWEEN
          (SELECT start_date FROM date_info)
        AND
          (SELECT end_date   FROM date_info)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
  ),
  prior_period AS (
    SELECT 
      MODE,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE BETWEEN
          (SELECT start_date     FROM date_info) - (SELECT interval_offset FROM offset_period)
        AND
          (SELECT end_date       FROM date_info) - (SELECT interval_offset FROM offset_period)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
  ),
  total_counts AS (
    SELECT
      SUM(cp.sum_count) AS total_current_period,
      SUM(pp.sum_count) AS total_prior_period
    FROM current_period cp
    FULL JOIN prior_period   pp USING (MODE)
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
      END AS prior_date_range_label
    FROM prior_date_info
  )
SELECT
  mas.MODE,
  CASE
    WHEN mas.MODE = 'Driver'       THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/driver.png'
    WHEN mas.MODE = 'Passenger'    THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/passenger.png'
    WHEN mas.MODE = 'Pedestrian'   THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/pedestrian.png'
    WHEN mas.MODE = 'Bicyclist'    THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/bicyclist.png'
    WHEN mas.MODE = 'Motorcyclist*' THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/motorcyclist.png'
    WHEN mas.MODE = 'Scooterist*'  THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/scooterist.png'
    WHEN mas.MODE IN ('Unknown','Other')
                                   THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/unknown.png'
    ELSE NULL
  END AS ICON,
  COALESCE(cp.sum_count, 0) AS current_period_sum,
  COALESCE(pp.sum_count, 0) AS prior_period_sum,
  COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
  CASE
    WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
    WHEN COALESCE(pp.sum_count, 0) != 0 THEN
      (COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0))
      / COALESCE(pp.sum_count, 0)
    ELSE NULL
  END AS percentage_change,
  (SELECT date_range_label       FROM date_info)        AS current_period_range,
  (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
  (total_current_period - total_prior_period)
    / NULLIF(total_prior_period, 0) AS total_percentage_change,
  COALESCE(cp.sum_count, 0)
    / NULLIF(total_current_period, 0) AS current_mode_percentage,
  COALESCE(pp.sum_count, 0)
    / NULLIF(total_prior_period, 0) AS prior_mode_percentage
FROM modes_and_severities mas
LEFT JOIN current_period cp USING (MODE)
LEFT JOIN prior_period   pp USING (MODE),
     total_counts;
```

```sql barchart_mode
WITH 
    report_date_range AS (
        SELECT
            CASE 
                WHEN '${inputs.date_range.end}'::DATE 
                    >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
                THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
                ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
            END   AS end_date,
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
            END AS date_range_label,
            (end_date - start_date) AS date_range_days
        FROM report_date_range
    ),
    offset_period AS (
        SELECT
            start_date,
            end_date,
            CASE 
                WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)
                WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
                WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
                WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
                WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
                ELSE INTERVAL '1 year'
            END AS interval_offset
        FROM date_info
    ),
    modes_and_severities AS (
        SELECT DISTINCT MODE
        FROM crashes.crashes
    ),
    current_period AS (
        SELECT 
            MODE,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE >= (SELECT start_date FROM date_info)
            AND REPORTDATE <= (SELECT end_date FROM date_info)
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY MODE
    ),
    prior_period AS (
        SELECT 
            MODE,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE >= ((SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period))
            AND REPORTDATE <= ((SELECT end_date   FROM date_info) - (SELECT interval_offset FROM offset_period))
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY MODE
    ),
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM current_period cp
        FULL JOIN prior_period pp ON cp.MODE = pp.MODE
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
            END AS prior_date_range_label
        FROM prior_date_info
    )
SELECT
    mas.MODE,
    'Current Period' AS period,
    COALESCE(cp.sum_count, 0) AS period_sum,
    di.date_range_label AS period_range
FROM modes_and_severities mas
LEFT JOIN current_period cp ON mas.MODE = cp.MODE
CROSS JOIN date_info di
UNION ALL
SELECT
    mas.MODE,
    'Prior Period' AS period,
    COALESCE(pp.sum_count, 0) AS period_sum,
    pdl.prior_date_range_label AS period_range
FROM modes_and_severities mas
LEFT JOIN prior_period pp ON mas.MODE = pp.MODE
CROSS JOIN prior_date_label pdl
ORDER BY mas.MODE, period;
```

```sql barchart_mode_3ytd
WITH 
-- Normalize the user-provided dates to an exclusive end_date (half-open window)
report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END   AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
-- Validation flag: 1 = valid, 0 = invalid
validate_range AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '1 year' THEN 0 -- exceeds 1 year span
        WHEN EXTRACT(YEAR FROM start_date) <> EXTRACT(YEAR FROM end_date - INTERVAL '1 day')
          THEN 0 -- crosses calendar years
        ELSE 1 -- valid
      END AS is_valid
    FROM report_date_range
),
-- Date info, labels, and validity joined in
date_info AS (
    SELECT
      r.start_date,
      r.end_date,
      CASE
        -- Full calendar year → 'YY
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)
        -- YTD → 'YY YTD
        WHEN r.start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = r.end_date - INTERVAL '1 day'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM (r.end_date - INTERVAL '1 day')) AS VARCHAR), 2) || ' YTD'
        -- Otherwise → mm/dd/yy–mm/dd/yy
        ELSE
          strftime(r.start_date, '%m/%d/%y')
          || '-' ||
          strftime(r.end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS date_range_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)      AS current_year_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) - 1 AS VARCHAR), 2)  AS prior_year_label,
      (r.end_date - r.start_date) AS date_range_days,
      v.is_valid,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN 1 ELSE 0
      END AS is_full_year
    FROM report_date_range r
    JOIN validate_range v ON 1=1
),
modes_and_severities AS (
    SELECT DISTINCT MODE
    FROM crashes.crashes
),
-- Current period sum by mode (half-open interval)
current_period AS (
    SELECT 
      MODE,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= (SELECT start_date FROM date_info)
      AND REPORTDATE <  (SELECT end_date   FROM date_info)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
),
-- Three prior 1-year slices (T-1, T-2, T-3)
prior_years AS (
    SELECT MODE, SUM(COUNT) AS sum_count, 1 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '1 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '1 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
    UNION ALL
    SELECT MODE, SUM(COUNT) AS sum_count, 2 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '2 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '2 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
    UNION ALL
    SELECT MODE, SUM(COUNT) AS sum_count, 3 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '3 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '3 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
),
-- Average across T-1, T-2, T-3
prior_avg AS (
    SELECT
      MODE,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN (
             COALESCE(MAX(CASE WHEN yr_offset=1 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=2 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=3 THEN sum_count END),0)
           ) / 3.0
           ELSE NULL
      END AS avg_sum_count
    FROM prior_years
    GROUP BY MODE
),
-- Updated 3-year average label
prior_period_label AS (
    SELECT
      CASE
        WHEN (SELECT is_full_year FROM date_info) = 1
        THEN
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' Avg'
        ELSE
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' YTD Avg'
      END AS label
    FROM date_info
)
-- Final output
SELECT
  mas.MODE,
  'Current Period' AS period,
  COALESCE(cp.sum_count, 0) AS period_sum,
  di.date_range_label AS period_range
FROM modes_and_severities mas
LEFT JOIN current_period cp ON mas.MODE = cp.MODE
CROSS JOIN date_info di
UNION ALL
SELECT
  mas.MODE,
  '3-Year Avg' AS period,
  ROUND(pa.avg_sum_count, 1) AS period_sum,
  ppl.label AS period_range
FROM modes_and_severities mas
LEFT JOIN prior_avg pa ON mas.MODE = pa.MODE
CROSS JOIN prior_period_label ppl
ORDER BY MODE, period;
```

```sql period_comp_mode_3ytd
WITH 
-- Normalize the user-provided dates to an exclusive end_date
report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END   AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
-- Validation flag: 1 = valid, 0 = invalid
validate_range AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '1 year' THEN 0
        WHEN EXTRACT(YEAR FROM start_date) <> EXTRACT(YEAR FROM end_date - INTERVAL '1 day')
          THEN 0
        ELSE 1
      END AS is_valid
    FROM report_date_range
),
-- Date info with full-year/YTD detection and compact formatting
date_info AS (
    SELECT
      r.start_date,
      r.end_date,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)
        WHEN r.start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = r.end_date - INTERVAL '1 day'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM (r.end_date - INTERVAL '1 day')) AS VARCHAR), 2) || ' YTD'
        ELSE strftime(r.start_date, '%m/%d/%y') || '-' || strftime(r.end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS date_range_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)      AS current_year_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) - 1 AS VARCHAR), 2)  AS prior_year_label,
      (r.end_date - r.start_date) AS date_range_days,
      v.is_valid,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN 1 ELSE 0
      END AS is_full_year
    FROM report_date_range r
    JOIN validate_range v ON 1=1
),
modes_and_severities AS (
    SELECT DISTINCT MODE
    FROM crashes.crashes
),
-- Current period sum by mode
current_period AS (
    SELECT 
      MODE,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= (SELECT start_date FROM date_info)
      AND REPORTDATE <  (SELECT end_date   FROM date_info)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY MODE
),
-- Three prior 1-year slices
prior_years AS (
    SELECT MODE, SUM(COUNT) AS sum_count, 1 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '1 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '1 year'
      AND AGE BETWEEN ${inputs.min_age.value} AND (
        CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120
             THEN 119 ELSE ${inputs.max_age.value} END
      )
    GROUP BY MODE
    UNION ALL
    SELECT MODE, SUM(COUNT) AS sum_count, 2 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '2 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '2 year'
      AND AGE BETWEEN ${inputs.min_age.value} AND (
        CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120
             THEN 119 ELSE ${inputs.max_age.value} END
      )
    GROUP BY MODE
    UNION ALL
    SELECT MODE, SUM(COUNT) AS sum_count, 3 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '3 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '3 year'
      AND AGE BETWEEN ${inputs.min_age.value} AND (
        CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120
             THEN 119 ELSE ${inputs.max_age.value} END
      )
    GROUP BY MODE
),
-- Average of those three prior years
prior_avg AS (
    SELECT
      MODE,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN (
             COALESCE(MAX(CASE WHEN yr_offset=1 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=2 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=3 THEN sum_count END),0)
           ) / 3.0
           ELSE NULL
      END AS avg_sum_count
    FROM prior_years
    GROUP BY MODE
),
-- Totals 
total_counts AS (
    SELECT
      SUM(cp.sum_count) AS total_current_period,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN SUM(ROUND(pa.avg_sum_count, 2))
           ELSE NULL
      END AS total_prior_avg
    FROM current_period cp
    FULL JOIN prior_avg pa USING (MODE)
),
-- Prior period label
prior_period_label AS (
    SELECT
      CASE
        WHEN (SELECT is_full_year FROM date_info) = 1
        THEN
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' Avg'
        ELSE
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' YTD Avg'
      END AS label
    FROM date_info
)
SELECT
  mas.MODE,
  CASE
    WHEN mas.MODE = 'Driver'        THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/driver.png'
    WHEN mas.MODE = 'Passenger'     THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/passenger.png'
    WHEN mas.MODE = 'Pedestrian'    THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/pedestrian.png'
    WHEN mas.MODE = 'Bicyclist'     THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/bicyclist.png'
    WHEN mas.MODE = 'Motorcyclist*' THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/motorcyclist.png'
    WHEN mas.MODE = 'Scooterist*'   THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/scooterist.png'
    WHEN mas.MODE IN ('Unknown','Other')
                                    THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/unknown.png'
    ELSE NULL
  END AS ICON,
  COALESCE(cp.sum_count, 0) AS current_period_sum,
  ROUND(COALESCE(pa.avg_sum_count, 0), 2) AS prior_3yr_avg_sum,
  ROUND(
      COALESCE(cp.sum_count, 0) - COALESCE(pa.avg_sum_count, 0),
      2
  ) AS difference,
  CASE
    WHEN COALESCE(cp.sum_count, 0) = 0
      OR COALESCE(pa.avg_sum_count, 0) = 0
    THEN NULL
    ELSE
      (COALESCE(cp.sum_count, 0) - ROUND(pa.avg_sum_count, 2))
      / ROUND(pa.avg_sum_count, 2)
  END AS percentage_change,
  (SELECT date_range_label   FROM date_info)        AS current_period_range,
  (SELECT label              FROM prior_period_label) AS prior_period_range,
  (SELECT current_year_label FROM date_info)        AS current_year_label,
  (SELECT prior_year_label   FROM date_info)        AS prior_year_label,
  CASE
    WHEN COALESCE(total_current_period, 0) = 0
      OR COALESCE(total_prior_avg, 0) = 0
    THEN NULL
    ELSE
      (ROUND(total_current_period, 1) - ROUND(total_prior_avg, 1))
      / ROUND(total_prior_avg, 1)
  END AS total_percentage_change,
  COALESCE(cp.sum_count, 0) / NULLIF(total_current_period, 0) AS current_mode_percentage,
  CASE WHEN total_prior_avg IS NOT NULL
       THEN pa.avg_sum_count / NULLIF(total_prior_avg, 0)
       ELSE NULL
  END AS prior_mode_percentage
FROM modes_and_severities mas
LEFT JOIN current_period cp USING (MODE)
LEFT JOIN prior_avg      pa USING (MODE),
     total_counts;
```

```sql period_comp_severity
WITH 
    report_date_range AS (
        SELECT
        CASE 
            WHEN '${inputs.date_range.end}'::DATE 
                >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
            ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
        END   AS end_date,
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
          END AS date_range_label,
          (end_date - start_date) AS date_range_days
        FROM report_date_range
    ),
    offset_period AS (
        SELECT
          start_date,
          end_date,
          CASE 
              WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)
              WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
              WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
              WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
              WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
              ELSE INTERVAL '1 year'
          END AS interval_offset
        FROM date_info
    ),
    severities AS (
        SELECT DISTINCT SEVERITY
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
    ),
    current_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes 
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE BETWEEN
                (SELECT start_date FROM date_info)
            AND (SELECT end_date FROM date_info)
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY SEVERITY
    ),
    prior_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes 
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE BETWEEN
                (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period)
            AND (SELECT end_date FROM date_info)   - (SELECT interval_offset FROM offset_period)
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY SEVERITY
    ),
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM current_period cp
        FULL JOIN prior_period pp USING (SEVERITY)
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
          END AS prior_date_range_label
        FROM prior_date_info
    )
SELECT 
    s.SEVERITY,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    COALESCE(pp.sum_count, 0) AS prior_period_sum, 
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE 
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) <> 0
        THEN (COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0)) / COALESCE(pp.sum_count, 0)
        ELSE NULL
    END AS percentage_change,
    (SELECT date_range_label       FROM date_info)        AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
    (total_current_period - total_prior_period)
        / NULLIF(total_prior_period, 0) AS total_percentage_change,
    COALESCE(cp.sum_count, 0) / NULLIF(total_current_period, 0) AS current_severity_percentage,
    COALESCE(pp.sum_count, 0) / NULLIF(total_prior_period, 0) AS prior_severity_percentage
FROM severities s
LEFT JOIN current_period cp USING (SEVERITY)
LEFT JOIN prior_period   pp USING (SEVERITY),
     total_counts;
```

```sql period_comp_severity_3ytd
WITH 
-- Normalize the user-provided dates to an exclusive end_date (half-open window)
report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END   AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
-- Validation flag: 1 = valid, 0 = invalid
validate_range AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '1 year' THEN 0
        WHEN EXTRACT(YEAR FROM start_date) <> EXTRACT(YEAR FROM end_date - INTERVAL '1 day')
        THEN 0
        ELSE 1
      END AS is_valid
    FROM report_date_range
),
-- Date info with full-year/YTD detection and compact formatting
date_info AS (
    SELECT
      r.start_date,
      r.end_date,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)
        WHEN r.start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = r.end_date - INTERVAL '1 day'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM (r.end_date - INTERVAL '1 day')) AS VARCHAR), 2) || ' YTD'
        ELSE strftime(r.start_date, '%m/%d/%y') || '-' || strftime(r.end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS date_range_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)      AS current_year_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) - 1 AS VARCHAR), 2)  AS prior_year_label,
      (r.end_date - r.start_date) AS date_range_days,
      v.is_valid,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN 1 ELSE 0
      END AS is_full_year
    FROM report_date_range r
    JOIN validate_range v ON 1=1
),
severities AS (
    SELECT DISTINCT SEVERITY
    FROM crashes.crashes
    WHERE SEVERITY IN ${inputs.multi_severity.value}
),
-- Current period sum by severity
current_period AS (
    SELECT 
      SEVERITY,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= (SELECT start_date FROM date_info)
      AND REPORTDATE <  (SELECT end_date   FROM date_info)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
),
-- Three prior 1-year slices (T-1, T-2, T-3)
prior_years AS (
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 1 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '1 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '1 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
    UNION ALL
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 2 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '2 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '2 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
    UNION ALL
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 3 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '3 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '3 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
),
-- Average across T-1, T-2, T-3
prior_avg AS (
    SELECT
      SEVERITY,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN (
             COALESCE(MAX(CASE WHEN yr_offset=1 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=2 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=3 THEN sum_count END),0)
           ) / 3.0
           ELSE NULL
      END AS avg_sum_count
    FROM prior_years
    GROUP BY SEVERITY
),
-- Totals 
total_counts AS (
    SELECT
      SUM(cp.sum_count) AS total_current_period,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN SUM(ROUND(pa.avg_sum_count, 2))
           ELSE NULL
      END AS total_prior_avg
    FROM current_period cp
    FULL JOIN prior_avg pa USING (SEVERITY)
),
-- Prior period label
prior_period_label AS (
    SELECT
      CASE
        WHEN (SELECT is_full_year FROM date_info) = 1
        THEN
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' Avg'
        ELSE
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' YTD Avg'
      END AS label
    FROM date_info
)
SELECT 
    s.SEVERITY,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    ROUND(pa.avg_sum_count, 2) AS prior_3yr_avg_sum, 
    CASE WHEN pa.avg_sum_count IS NOT NULL
         THEN ROUND(COALESCE(cp.sum_count, 0) - pa.avg_sum_count, 2)
         ELSE NULL
    END AS difference,
    CASE
        WHEN COALESCE(cp.sum_count, 0) = 0
          OR COALESCE(pa.avg_sum_count, 0) = 0
        THEN NULL
        ELSE
          (COALESCE(cp.sum_count, 0) - ROUND(pa.avg_sum_count, 1))
          / ROUND(pa.avg_sum_count, 1)
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT label FROM prior_period_label)   AS prior_period_range,
    CASE
        WHEN COALESCE(total_current_period, 0) = 0
          OR COALESCE(total_prior_avg, 0) = 0
        THEN NULL
        ELSE
          (ROUND(total_current_period, 1) - ROUND(total_prior_avg, 1))
          / ROUND(total_prior_avg, 1)
    END AS total_percentage_change,
    COALESCE(cp.sum_count, 0) / NULLIF(total_current_period, 0) AS current_severity_percentage,
    CASE WHEN total_prior_avg IS NOT NULL
         THEN pa.avg_sum_count / NULLIF(total_prior_avg, 0)
         ELSE NULL
    END AS prior_severity_percentage
FROM 
    severities s
LEFT JOIN current_period cp ON s.SEVERITY = cp.SEVERITY
LEFT JOIN prior_avg pa      ON s.SEVERITY = pa.SEVERITY,
    total_counts;
```

```sql barchart_severity
WITH 
    report_date_range AS (
        SELECT
            CASE 
                WHEN '${inputs.date_range.end}'::DATE 
                    >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
                THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
                ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
            END   AS end_date,
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
            END AS date_range_label,
            (end_date - start_date) AS date_range_days
        FROM report_date_range
    ),
    offset_period AS (
        SELECT
            start_date,
            end_date,
            CASE 
                WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)
                WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
                WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
                WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
                WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
                ELSE INTERVAL '1 year'
            END AS interval_offset
        FROM date_info
    ),
    severities AS (
        SELECT DISTINCT SEVERITY
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
    ),
    current_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value}
            AND REPORTDATE BETWEEN
                (SELECT start_date FROM date_info)
                AND
                (SELECT end_date   FROM date_info)
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY SEVERITY
    ),
    prior_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value}
            AND REPORTDATE BETWEEN
                ((SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period))
                AND
                ((SELECT end_date   FROM date_info) - (SELECT interval_offset FROM offset_period))
            AND AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0
                                 AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
        GROUP BY SEVERITY
    ),
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM current_period cp
        FULL JOIN prior_period pp ON cp.SEVERITY = pp.SEVERITY
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
            END AS prior_date_range_label
        FROM prior_date_info
    )
SELECT
    s.SEVERITY,
    'Current Period' AS period,
    COALESCE(cp.sum_count, 0) AS period_sum,
    di.date_range_label AS period_range
FROM severities s
LEFT JOIN current_period cp ON s.SEVERITY = cp.SEVERITY
CROSS JOIN date_info di
UNION ALL
SELECT
    s.SEVERITY,
    'Prior Period' AS period,
    COALESCE(pp.sum_count, 0) AS period_sum,
    pdl.prior_date_range_label AS period_range
FROM severities s
LEFT JOIN prior_period pp ON s.SEVERITY = pp.SEVERITY
CROSS JOIN prior_date_label pdl
ORDER BY s.SEVERITY, period;
```

```sql barchart_severity_3ytd
WITH 
-- Normalize the user-provided dates to an exclusive end_date (half-open window)
report_date_range AS (
    SELECT
      CASE 
        WHEN '${inputs.date_range.end}'::DATE 
             >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
        ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
      END   AS end_date,
      '${inputs.date_range.start}'::DATE AS start_date
),
-- Validation flag: 1 = valid, 0 = invalid
validate_range AS (
    SELECT
      start_date,
      end_date,
      CASE 
        WHEN end_date > start_date + INTERVAL '1 year' THEN 0
        WHEN EXTRACT(YEAR FROM start_date) <> EXTRACT(YEAR FROM end_date - INTERVAL '1 day')
          THEN 0
        ELSE 1
      END AS is_valid
    FROM report_date_range
),
-- Updated date_info with full-year/YTD detection and compact formatting
date_info AS (
    SELECT
      r.start_date,
      r.end_date,
      CASE
        -- Full calendar year → 'YY
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)
        -- YTD → 'YY YTD
        WHEN r.start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = r.end_date - INTERVAL '1 day'
        THEN '''' || RIGHT(CAST(EXTRACT(YEAR FROM (r.end_date - INTERVAL '1 day')) AS VARCHAR), 2) || ' YTD'
        -- Otherwise → mm/dd/yy–mm/dd/yy
        ELSE
          strftime(r.start_date, '%m/%d/%y')
          || '-' ||
          strftime(r.end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS date_range_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) AS VARCHAR), 2)      AS current_year_label,
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM r.start_date) - 1 AS VARCHAR), 2)  AS prior_year_label,
      (r.end_date - r.start_date) AS date_range_days,
      v.is_valid,
      CASE
        WHEN r.start_date = DATE_TRUNC('year', r.start_date)
         AND r.end_date   = DATE_TRUNC('year', r.start_date) + INTERVAL '1 year'
        THEN 1 ELSE 0
      END AS is_full_year
    FROM report_date_range r
    JOIN validate_range v ON 1=1
),
severities AS (
    SELECT DISTINCT SEVERITY
    FROM crashes.crashes
    WHERE SEVERITY IN ${inputs.multi_severity.value}
),
-- Current period sum by severity
current_period AS (
    SELECT 
      SEVERITY,
      SUM(COUNT) AS sum_count
    FROM crashes.crashes
    WHERE
      SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= (SELECT start_date FROM date_info)
      AND REPORTDATE <  (SELECT end_date   FROM date_info)
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
),
-- Three prior 1-year slices
prior_years AS (
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 1 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '1 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '1 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
    UNION ALL
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 2 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '2 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '2 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
    UNION ALL
    SELECT SEVERITY, SUM(COUNT) AS sum_count, 3 AS yr_offset
    FROM crashes.crashes
    JOIN date_info di ON 1=1
    WHERE di.is_valid = 1
      AND SEVERITY IN ${inputs.multi_severity.value}
      AND REPORTDATE >= di.start_date - INTERVAL '3 year'
      AND REPORTDATE <  di.end_date   - INTERVAL '3 year'
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                    CASE 
                      WHEN ${inputs.min_age.value} <> 0
                       AND ${inputs.max_age.value} = 120
                      THEN 119
                      ELSE ${inputs.max_age.value}
                    END
                  )
    GROUP BY SEVERITY
),
-- Average across T-1, T-2, T-3
prior_avg AS (
    SELECT
      SEVERITY,
      CASE WHEN (SELECT is_valid FROM date_info) = 1
           THEN (
             COALESCE(MAX(CASE WHEN yr_offset=1 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=2 THEN sum_count END),0) +
             COALESCE(MAX(CASE WHEN yr_offset=3 THEN sum_count END),0)
           ) / 3.0
           ELSE NULL
      END AS avg_sum_count
    FROM prior_years
    GROUP BY SEVERITY
),
-- Updated 3-year average label
prior_period_label AS (
    SELECT
      CASE
        WHEN (SELECT is_full_year FROM date_info) = 1
        THEN
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' Avg'
        ELSE
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 3 AS VARCHAR), 2)
          || '⁃' ||
          '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
          || ' YTD Avg'
      END AS label
    FROM date_info
)
-- Final output
SELECT
  s.SEVERITY,
  'Current Period' AS period,
  COALESCE(cp.sum_count, 0) AS period_sum,
  di.date_range_label AS period_range
FROM severities s
LEFT JOIN current_period cp ON s.SEVERITY = cp.SEVERITY
CROSS JOIN date_info di
UNION ALL
SELECT
  s.SEVERITY,
  '3-Year Avg' AS period,
  ROUND(pa.avg_sum_count, 0) AS period_sum,
  ppl.label AS period_range
FROM severities s
LEFT JOIN prior_avg pa ON s.SEVERITY = pa.SEVERITY
CROSS JOIN prior_period_label ppl
ORDER BY SEVERITY, period;
```

```sql yoy_text_fatal
WITH date_range AS (
    SELECT
        CASE
            -- Jan 1–9 freeze: exclusive end = Jan 1 of current year
            WHEN extract(month FROM current_date) = 1
             AND extract(day   FROM current_date) <= 9
            THEN date_trunc('year', current_date)
            -- Otherwise: exclusive end = max(REPORTDATE) + 1 day
            ELSE MAX(LAST_RECORD)::DATE + INTERVAL '1 day'
        END AS max_report_date_excl
    FROM crashes.crashes
),
-- Count Fatal and Major crashes in the current year (based on frozen date)
severity_counts AS (
    SELECT
        SUM(CASE WHEN c.SEVERITY = 'Fatal' THEN c.COUNT ELSE 0 END) AS fatal_this_year,
        SUM(CASE WHEN c.SEVERITY = 'Major' THEN c.COUNT ELSE 0 END) AS major_this_year
    FROM crashes.crashes c
    CROSS JOIN date_range dr
    WHERE EXTRACT(YEAR FROM c.REPORTDATE) =
          EXTRACT(YEAR FROM dr.max_report_date_excl - INTERVAL '1 day')
),
params AS (
    SELECT
        -- Current period: Jan 1 of the year before the exclusive end
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 day') AS current_year_start,
        dr.max_report_date_excl AS current_year_end_excl,
        -- Prior period: shift back one full year
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 year' - INTERVAL '1 day') AS prior_year_start,
        (dr.max_report_date_excl - INTERVAL '1 year') AS prior_year_end_excl,
        -- Year labels
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 day') AS current_year,
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 year' - INTERVAL '1 day') AS year_prior,
        -- inFirstWeek OR (fatal=0 OR major=0)
        CASE
            WHEN (
                -- First week of data: Jan 1–9
                (extract(month FROM current_date) = 1 AND extract(day FROM current_date) <= 9)
                OR
                -- Fallback: no Fatal OR no Major crashes yet this year
                (SELECT fatal_this_year FROM severity_counts) = 0
                OR
                (SELECT major_this_year FROM severity_counts) = 0
            )
            THEN TRUE
            ELSE FALSE
        END AS is_first_week
    FROM date_range dr
),
yearly_counts AS (
    SELECT
        SUM(
            CASE
                WHEN cr.REPORTDATE >= p.current_year_start
                 AND cr.REPORTDATE <  p.current_year_end_excl
                THEN cr.COUNT ELSE 0
            END
        ) AS current_year_sum,

        SUM(
            CASE
                WHEN cr.REPORTDATE >= p.prior_year_start
                 AND cr.REPORTDATE <  p.prior_year_end_excl
                THEN cr.COUNT ELSE 0
            END
        ) AS prior_year_sum

    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.prior_year_start
      AND cr.REPORTDATE <  p.current_year_end_excl
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
    strftime(p.current_year_end_excl - INTERVAL '1 day', '%m/%d/%y') AS max_report_date_formatted,
    p.is_first_week
FROM yearly_counts yc
CROSS JOIN params p;
```

```sql yoy_text_fatal_3ytd
WITH date_range AS (
    SELECT
        CASE
            -- Freeze exclusive end to Jan 1 during Jan 1–9
            WHEN extract(month FROM current_date) = 1
             AND extract(day   FROM current_date) <= 9
            THEN date_trunc('year', current_date)
            -- Otherwise: exclusive end = max(REPORTDATE) + 1 day
            ELSE MAX(LAST_RECORD)::DATE + INTERVAL '1 day'
        END AS max_report_date_excl
    FROM crashes.crashes
),
-- Count Fatal and Major crashes in the current year (based on frozen date)
severity_counts AS (
    SELECT
        SUM(CASE WHEN c.SEVERITY = 'Fatal' THEN c.COUNT ELSE 0 END) AS fatal_this_year,
        SUM(CASE WHEN c.SEVERITY = 'Major' THEN c.COUNT ELSE 0 END) AS major_this_year
    FROM crashes.crashes c
    CROSS JOIN date_range dr
    WHERE EXTRACT(YEAR FROM c.REPORTDATE) =
          EXTRACT(YEAR FROM dr.max_report_date_excl - INTERVAL '1 day')
),
params AS (
    SELECT
        -- Current YTD window: Jan 1 of the year before exclusive end
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 day') AS current_year_start,
        dr.max_report_date_excl AS current_year_end_excl,
        -- Year label for current year
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 day') AS current_year,
        -- inFirstWeek OR (fatal=0 OR major=0)
        CASE
            WHEN (
                -- First week of data: Jan 1–9
                (extract(month FROM current_date) = 1 AND extract(day FROM current_date) <= 9)
                OR
                -- Fallback: no Fatal OR no Major crashes yet this year
                (SELECT fatal_this_year FROM severity_counts) = 0
                OR
                (SELECT major_this_year FROM severity_counts) = 0
            )
            THEN TRUE
            ELSE FALSE
        END AS is_first_week
    FROM date_range dr
),
-- Current YTD fatal count
current_ytd AS (
    SELECT
        SUM(COUNT) AS current_year_sum
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.current_year_start
      AND cr.REPORTDATE <  p.current_year_end_excl
),
-- Three prior YTD periods (shift exclusive window back 1, 2, 3 years)
prior_years AS (
    SELECT
        1 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '1 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '1 year'
    UNION ALL
    SELECT
        2 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '2 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '2 year'
    UNION ALL
    SELECT
        3 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Fatal'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '3 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '3 year'
),
-- Average of the three prior YTDs (rounded)
prior_avg AS (
    SELECT
        ROUND(
            (COALESCE(MAX(CASE WHEN yr_offset = 1 THEN sum_count END), 0) +
             COALESCE(MAX(CASE WHEN yr_offset = 2 THEN sum_count END), 0) +
             COALESCE(MAX(CASE WHEN yr_offset = 3 THEN sum_count END), 0)
            ) / 3.0
        , 1) AS prior_3yr_avg_sum
    FROM prior_years
)
SELECT
    'Fatal' AS severity,
    cy.current_year_sum,
    pa.prior_3yr_avg_sum,
    ABS(cy.current_year_sum - pa.prior_3yr_avg_sum) AS difference,
    CASE WHEN pa.prior_3yr_avg_sum <> 0
         THEN (cy.current_year_sum - pa.prior_3yr_avg_sum) / pa.prior_3yr_avg_sum
         ELSE NULL END AS percentage_change,
    CASE WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) > 0 THEN 'an increase of'
         WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) < 0 THEN 'a decrease of'
         ELSE NULL END AS percentage_change_text,
    CASE WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) > 0 THEN 'more'
         WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) < 0 THEN 'fewer'
         ELSE 'no change' END AS difference_text,
    p.current_year,
    '''' || RIGHT(CAST(p.current_year AS VARCHAR), 2) AS current_year_label,
    '''' || RIGHT(CAST(p.current_year - 3 AS VARCHAR), 2)
          || '-' || '''' || RIGHT(CAST(p.current_year - 1 AS VARCHAR), 2)
          || ' YTD Avg' AS prior_period_label,
    '''' || RIGHT(CAST(p.current_year - 1 AS VARCHAR), 2) AS last_year_label,
    CASE WHEN cy.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN cy.current_year_sum = 1 THEN 'fatality' ELSE 'fatalities' END AS fatality,
    -- Display last included date (exclusive end minus 1 day)
    strftime(p.current_year_end_excl - INTERVAL '1 day', '%m/%d/%y') AS max_report_date_formatted,
    p.is_first_week
FROM current_ytd cy
CROSS JOIN prior_avg pa
CROSS JOIN params p;
```

```sql yoy_text_major_injury
WITH date_range AS (
    SELECT
        CASE
            -- During Jan 1–9, freeze exclusive end to Jan 1 of current year
            WHEN extract(month FROM current_date) = 1
             AND extract(day   FROM current_date) <= 9
            THEN date_trunc('year', current_date)
            -- Otherwise: exclusive end = max(REPORTDATE) + 1 day
            ELSE MAX(LAST_RECORD)::DATE + INTERVAL '1 day'
        END AS max_report_date_excl
    FROM crashes.crashes
),
-- Count Fatal and Major crashes in the current year (based on frozen date)
severity_counts AS (
    SELECT
        SUM(CASE WHEN c.SEVERITY = 'Fatal' THEN c.COUNT ELSE 0 END) AS fatal_this_year,
        SUM(CASE WHEN c.SEVERITY = 'Major' THEN c.COUNT ELSE 0 END) AS major_this_year
    FROM crashes.crashes c
    CROSS JOIN date_range dr
    WHERE EXTRACT(YEAR FROM c.REPORTDATE) =
          EXTRACT(YEAR FROM dr.max_report_date_excl - INTERVAL '1 day')
),
params AS (
    SELECT
        -- Current period: Jan 1 of the year before the exclusive end
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 day') AS current_year_start,
        dr.max_report_date_excl AS current_year_end_excl,
        -- Prior period: shift back one full year
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 year' - INTERVAL '1 day') AS prior_year_start,
        (dr.max_report_date_excl - INTERVAL '1 year') AS prior_year_end_excl,
        -- Year labels
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 day') AS current_year,
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 year' - INTERVAL '1 day') AS year_prior,
        -- inFirstWeek OR (fatal=0 OR major=0)
        CASE
            WHEN (
                -- First week of data: Jan 1–9
                (extract(month FROM current_date) = 1 AND extract(day FROM current_date) <= 9)
                OR
                -- Fallback: no Fatal OR no Major crashes yet this year
                (SELECT fatal_this_year FROM severity_counts) = 0
                OR
                (SELECT major_this_year FROM severity_counts) = 0
            )
            THEN TRUE
            ELSE FALSE
        END AS is_first_week
    FROM date_range dr
),
yearly_counts AS (
    SELECT
        SUM(
            CASE
                WHEN cr.REPORTDATE >= p.current_year_start
                 AND cr.REPORTDATE <  p.current_year_end_excl
                THEN cr.COUNT ELSE 0
            END
        ) AS current_year_sum,
        SUM(
            CASE
                WHEN cr.REPORTDATE >= p.prior_year_start
                 AND cr.REPORTDATE <  p.prior_year_end_excl
                THEN cr.COUNT ELSE 0
            END
        ) AS prior_year_sum
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Major'
      AND cr.REPORTDATE >= p.prior_year_start
      AND cr.REPORTDATE <  p.current_year_end_excl
)
SELECT
    'Major' AS severity,
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
    CASE WHEN yc.current_year_sum = 1 THEN 'major injury' ELSE 'major injuries' END AS major_injury,
    -- Display last included date
    strftime(p.current_year_end_excl - INTERVAL '1 day', '%m/%d/%y') AS max_report_date_formatted,
    p.is_first_week
FROM yearly_counts yc
CROSS JOIN params p;
```

```sql yoy_text_major_injury_3ytd
WITH date_range AS (
    SELECT
        CASE
            -- Freeze exclusive end to Jan 1 during Jan 1–9
            WHEN extract(month FROM current_date) = 1
             AND extract(day   FROM current_date) <= 9
            THEN date_trunc('year', current_date)
            -- Otherwise: exclusive end = max(REPORTDATE) + 1 day
            ELSE MAX(LAST_RECORD)::DATE + INTERVAL '1 day'
        END AS max_report_date_excl
    FROM crashes.crashes
),
-- Count Fatal and Major crashes in the current year (based on frozen date)
severity_counts AS (
    SELECT
        SUM(CASE WHEN c.SEVERITY = 'Fatal' THEN c.COUNT ELSE 0 END) AS fatal_this_year,
        SUM(CASE WHEN c.SEVERITY = 'Major' THEN c.COUNT ELSE 0 END) AS major_this_year
    FROM crashes.crashes c
    CROSS JOIN date_range dr
    WHERE EXTRACT(YEAR FROM c.REPORTDATE) =
          EXTRACT(YEAR FROM dr.max_report_date_excl - INTERVAL '1 day')
),
params AS (
    SELECT
        -- Current YTD window: Jan 1 of the year before exclusive end
        date_trunc('year', dr.max_report_date_excl - INTERVAL '1 day') AS current_year_start,
        dr.max_report_date_excl AS current_year_end_excl,
        -- Year label for current year
        extract(year FROM dr.max_report_date_excl - INTERVAL '1 day') AS current_year,
        -- inFirstWeek OR (fatal=0 OR major=0)
        CASE
            WHEN (
                -- First week of data: Jan 1–9
                (extract(month FROM current_date) = 1 AND extract(day FROM current_date) <= 9)
                OR
                -- Fallback: no Fatal OR no Major crashes yet this year
                (SELECT fatal_this_year FROM severity_counts) = 0
                OR
                (SELECT major_this_year FROM severity_counts) = 0
            )
            THEN TRUE
            ELSE FALSE
        END AS is_first_week
    FROM date_range dr
),
-- Current YTD major injury count
current_ytd AS (
    SELECT
        SUM(COUNT) AS current_year_sum
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Major'
      AND cr.REPORTDATE >= p.current_year_start
      AND cr.REPORTDATE <  p.current_year_end_excl
),
-- Three prior YTD periods (shift exclusive window back 1, 2, 3 years)
prior_years AS (
    SELECT
        1 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Major'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '1 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '1 year'
    UNION ALL
    SELECT
        2 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Major'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '2 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '2 year'
    UNION ALL
    SELECT
        3 AS yr_offset,
        SUM(COUNT) AS sum_count
    FROM crashes.crashes cr
    CROSS JOIN params p
    WHERE cr.SEVERITY = 'Major'
      AND cr.REPORTDATE >= p.current_year_start - INTERVAL '3 year'
      AND cr.REPORTDATE <  p.current_year_end_excl - INTERVAL '3 year'
),
-- Average of the three prior YTDs
prior_avg AS (
    SELECT
        (COALESCE(MAX(CASE WHEN yr_offset = 1 THEN sum_count END), 0) +
         COALESCE(MAX(CASE WHEN yr_offset = 2 THEN sum_count END), 0) +
         COALESCE(MAX(CASE WHEN yr_offset = 3 THEN sum_count END), 0)
        ) / 3.0 AS prior_3yr_avg_sum
    FROM prior_years
)
SELECT
    'Major' AS severity,
    cy.current_year_sum,
    pa.prior_3yr_avg_sum,
    ABS(cy.current_year_sum - pa.prior_3yr_avg_sum) AS difference,
    CASE WHEN pa.prior_3yr_avg_sum <> 0
         THEN (cy.current_year_sum - pa.prior_3yr_avg_sum) / pa.prior_3yr_avg_sum
         ELSE NULL END AS percentage_change,
    CASE WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) > 0 THEN 'an increase of'
         WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) < 0 THEN 'a decrease of'
         ELSE NULL END AS percentage_change_text,
    CASE WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) > 0 THEN 'more'
         WHEN (cy.current_year_sum - pa.prior_3yr_avg_sum) < 0 THEN 'fewer'
         ELSE 'no change' END AS difference_text,
    p.current_year,
    -- 'YY label for current year
    '''' || RIGHT(CAST(p.current_year AS VARCHAR), 2) AS current_year_label,
    -- 'YY label for last year
    '''' || RIGHT(CAST(p.current_year - 1 AS VARCHAR), 2) AS last_year_label,
    -- Label for the prior period range, e.g. '22-'24 YTD Avg
    '''' || RIGHT(CAST(p.current_year - 3 AS VARCHAR), 2)
          || '-' || '''' || RIGHT(CAST(p.current_year - 1 AS VARCHAR), 2)
          || ' YTD Avg' AS prior_period_label,
    CASE WHEN cy.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN cy.current_year_sum = 1 THEN 'major injury' ELSE 'major injuries' END AS major_injury,
    -- Display last included date
    strftime(p.current_year_end_excl - INTERVAL '1 day', '%m/%d/%y') AS max_report_date_formatted,
    p.is_first_week
FROM current_ytd cy
CROSS JOIN prior_avg pa
CROSS JOIN params p;
```

```sql severity_selection
  -- 1. Aggregate severities based on the INTERSECTION of inputs
WITH
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
        SEVERITY IN ${inputs.multi_severity.value}
    )
-- 2. Final formatting for SEVERITY_SELECTION
SELECT
  CASE
    WHEN severity_count = 0 THEN ' '
    WHEN severity_count = 1 THEN severity_list
    WHEN severity_count = 2 THEN REPLACE(severity_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(severity_list, ',([^,]+)$', ', and \\1')
    END AS SEVERITY_SELECTION
FROM
  severity_agg_cte
```

<!--
echartsOptions={{animation: false}}
-->

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

<Tabs>
  <Tab label="{`${period_comp_mode_3ytd[0].current_year_label}`} vs {`${period_comp_mode_3ytd[0].prior_period_range}`}">
    <Grid cols=2>

      <!-- Column 1: Mode (3YTD vs 3-year average) -->
      <Group>
        <DataTable data={period_comp_mode_3ytd} totalRow sort="current_period_sum desc" wrapTitles rowShading title="Year Over Year Comparison of {`${severity_selection[0].SEVERITY_SELECTION}`} by Road User">
          <Column id="MODE" title="Road User" description="*Fatal Only" wrap=true totalAgg="Total"/>
          <Column id="current_period_sum" title="{period_comp_mode_3ytd[0].current_period_range}"/>
          <Column id="prior_3yr_avg_sum" fmt="#,##0.0" description="Average counts are rounded to simplify reporting." title="{period_comp_mode_3ytd[0].prior_period_range}" />
          <Column id="difference" contentType="delta" fmt="#,##0.0" downIsGood title="Diff"/>
          <Column id="percentage_change" fmt="pct0" title="% Diff" totalAgg={period_comp_mode_3ytd[0].total_percentage_change} totalFmt="pct0"/>
        </DataTable>

        <div style="font-size: 14px;">
          <b>Percentage Breakdown of {`${severity_selection[0].SEVERITY_SELECTION}`} by Road User</b>
        </div>

        <BarChart 
          data={barchart_mode_3ytd}
          chartAreaHeight=80
          x=period_range
          y=period_sum
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=MODE
          seriesColors={{"Pedestrian": '#00FFD4',"Other": '#06DFC8',"Bicyclist": '#0BBFBC',"Scooterist*": '#119FB0',"Motorcyclist*": '#167FA3',"Passenger": '#1C5F97',"Driver": '#271F7F',"Unknown": '#213F8B'}}
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10} 
        />
      </Group>

      <!-- Column 2: Severity (3YTD vs 3-year average) -->
      <Group>
        <DataTable data={period_comp_severity_3ytd} totalRow=true sort="current_period_sum desc" wrapTitles=true rowShading=true title="Year Over Year Comparison of {`${severity_selection[0].SEVERITY_SELECTION}`} for All Road Users">
          <Column id=SEVERITY title=Severity wrap=true totalAgg="Total"/>
          <Column id=current_period_sum title="{period_comp_severity_3ytd[0].current_period_range}" />
          <Column id=prior_3yr_avg_sum fmt='#,##0.0' description="Average counts are rounded to simplify reporting." title="{period_comp_severity_3ytd[0].prior_period_range}" />
          <Column id=difference contentType=delta fmt='#,##0.0' downIsGood=True title="Diff"/>
          <Column id=percentage_change fmt="pct0" title="% Diff" totalAgg={period_comp_severity_3ytd[0].total_percentage_change} totalFmt="pct0" /> 
        </DataTable>

        <div style="font-size: 14px;">
          <b>Percentage Breakdown of {`${severity_selection[0].SEVERITY_SELECTION}`} for All Road Users</b>
        </div>

        <BarChart 
          data={barchart_severity_3ytd}
          chartAreaHeight=80
          x=period_range
          y=period_sum
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=SEVERITY
          seriesColors={{"Minor": '#ffdf00',"Major": '#ff9412',"Fatal": '#ff5a53'}}
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10}
        /> 

        <Alert status="positive">
          <div markdown style="font-size: 14px;">

            Since Mayor Bowser launched Vision Zero in 2015, the District has transformed how we design and use our streets, strengthening laws, expanding education, redesigning roads and intersections, lowering speed limits, and increasing enforcement to make travel safer for everyone. Learn more: [Progress Timeline](/Progress/).

          </div>
          <div markdown style="font-size: 14px;">

            Additionally, DDOT uses crash injury data to target engineering fixes that slow speeds, shorten crossings, and carve out safe spaces for all road users. Learn more: [Engineering for Safety](https://visionzero.dc.gov/pages/engineering).

          </div>
          <div markdown style="font-size: 14px;">

            Similarly, DDOT intentionally aligns with Vision Zero goals through safety-focused projects across all eight wards. Learn more: [Projects](https://projects.ddot.dc.gov/pages/projects).

          </div>
        </Alert>
      </Group>

    </Grid>
  </Tab>

  <Tab label="{`${period_comp_mode_3ytd[0].current_year_label}`} vs {`${period_comp_mode_3ytd[0].prior_year_label}`} YTD">
    <Grid cols=2>

      <!-- Column 1: Mode (YTD vs prior YTD) -->
      <Group>
        <DataTable data={period_comp_mode} totalRow sort="current_period_sum desc" wrapTitles rowShading title="Year Over Year Comparison of {`${severity_selection[0].SEVERITY_SELECTION}`} by Road User">
          <Column id="MODE" title="Road User" description="*Fatal Only" wrap=true totalAgg="Total"/>
          <Column id=ICON title=' ' contentType=image height=22px align=center totalAgg=" "/>
          <Column id="current_period_sum" title="{period_comp_mode[0].current_period_range}"/>
          <Column id="prior_period_sum" title="{period_comp_mode[0].prior_period_range}"/>
          <Column id="difference" contentType="delta" downIsGood title="Diff"/>
          <Column id="percentage_change" fmt="pct0" title="% Diff" totalAgg={period_comp_mode[0].total_percentage_change} totalFmt="pct0"/>
        </DataTable>

        <div style="font-size: 14px;">
          <b>Percentage Breakdown of {`${severity_selection[0].SEVERITY_SELECTION}`} by Road User</b>
        </div>

        <BarChart 
          data={barchart_mode}
          chartAreaHeight=80
          x=period_range
          y=period_sum
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=MODE
          seriesColors={{"Pedestrian": '#00FFD4',"Other": '#06DFC8',"Bicyclist": '#0BBFBC',"Scooterist*": '#119FB0',"Motorcyclist*": '#167FA3',"Passenger": '#1C5F97',"Driver": '#271F7F',"Unknown": '#213F8B'}}
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10} 
        />
      </Group>

      <!-- Column 2: Severity (YTD vs prior YTD) -->
      <Group>
        <DataTable data={period_comp_severity} totalRow=true sort="current_period_sum desc" wrapTitles=true rowShading=true title="Year Over Year Comparison of {`${severity_selection[0].SEVERITY_SELECTION}`} for All Road Users">
          <Column id=SEVERITY title=Severity wrap=true totalAgg="Total"/>
          <Column id=current_period_sum title="{period_comp_severity[0].current_period_range}" />
          <Column id=prior_period_sum title="{period_comp_severity[0].prior_period_range}" />
          <Column id=difference contentType=delta downIsGood=True title="Diff"/>
          <Column id=percentage_change fmt='pct0' title="% Diff" totalAgg={period_comp_severity[0].total_percentage_change} totalFmt='pct0' /> 
        </DataTable>

        <div style="font-size: 14px;">
          <b>Percentage Breakdown of {`${severity_selection[0].SEVERITY_SELECTION}`} for All Road Users</b>
        </div>

        <BarChart 
          data={barchart_severity}
          chartAreaHeight=80
          x=period_range
          y=period_sum
          xLabelWrap={true}
          swapXY=true
          yFmt=pct0
          series=SEVERITY
          seriesColors={{"Minor": '#ffdf00',"Major": '#ff9412',"Fatal": '#ff5a53'}}
          labels={true}
          type=stacked100
          downloadableData=false
          downloadableImage=false
          leftPadding={10}
        /> 

        <Alert status="positive">
          <div markdown style="font-size: 14px;">

            Since Mayor Bowser launched Vision Zero in 2015, the District has transformed how we design and use our streets, strengthening laws, expanding education, redesigning roads and intersections, lowering speed limits, and increasing enforcement to make travel safer for everyone. [Progress Timeline](/Progress/).

          </div>
          <div markdown style="font-size: 14px;">

            Additionally, DDOT uses crash injury data to target engineering fixes that slow speeds, shorten crossings, and carve out safe spaces for all road users. Learn more: [Engineering for Safety](https://visionzero.dc.gov/pages/engineering).

          </div>
          <div markdown style="font-size: 14px;">

            Similarly, DDOT intentionally aligns with Vision Zero goals through safety-focused projects across all eight wards. Learn more: [Projects](https://projects.ddot.dc.gov/pages/projects).

          </div>
        </Alert>
      </Group>

    </Grid>
  </Tab>
</Tabs>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons. The maximum comparison period is 5 years.
</Note>

<Details title="About this dashboard">

    The Traffic Fatalities and Injuries Dashboard can be used by the public to know more about injuries or fatalities product of a crash in the District of Columbia (DC).
    
    Adjust the Road User, Severity, Age and Date filters to refine the results.

</Details>

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
        <td>The individual operating the motor vehicle.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/passenger.png" alt="Passenger Icon" width="32"></td>
        <td>Passenger</td>
        <td>The individual riding along in the motor vehicle.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/pedestrian.png" alt="Pedestrian Icon" width="32"></td>
        <td>Pedestrian</td>
        <td>An individual moving on foot, or using a wheelchair or other personal mobility device.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/bicyclist.png" alt="Bicyclist Icon" width="32"></td>
        <td>Bicyclist</td>
        <td>A person riding a bicycle or motorized bicycle.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/motorcyclist.png" alt="Motorcyclist Icon" width="32"></td>
        <td>Motorcyclist*</td>
        <td>User of a motor-driven cycle (e.g., motorcycle or moped). *Fatal only.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/scooterist.png" alt="Scooterist Icon" width="32"></td>
        <td>Scooterist*</td>
        <td>User of a standing scooter or personal mobility device. *Fatal only.</td>
      </tr>
      <tr>
        <td><img src="https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/unknown.png" alt="Other Icon" width="32"></td>
        <td>Other**</td>
        <td>Includes motor-driven cycles (commonly referred to as mopeds and motorcycles), as well as personal mobility devices such as standing scooters, and others, including unknown classifications. **Major and minor injury only.</td>
      </tr>
    </tbody>
  </table>

</Details>

<Details title="About the data">

The data come from the tables Crashes in DC and Crash Details from DC's Open Data portal (see links below), as well as internal tracking of traffic fatalities by the District Department of Transportation (DDOT) and the Metropolitan Police Department (MPD). 
    
### The data is filtered to:
        - Only keep records of crashes that occured on or after 1/1/2017
        - Only keep records of crashes that involved a fatality, a major injury, or minor injury. See section "Injury Crashes" below. 

All counts on this page are for persons injured, NOT the number of crashes. For example, one crash may involve injuries to three persons; in that case, all three persons will be counted in all the charts and indicators on this dashboard. 

Injury Crashes are defined based on information collected at the scene of the crash. See below for examples of the different types of injury categories. 

### Injury Category:
        - Major Injury:	Unconsciousness; Apparent Broken Bones; Concussion; Gunshot (non-fatal); Severe Laceration; Other Major Injury. 
        - Minor Injury:	Abrasions; Minor Cuts; Discomfort; Bleeding; Swelling; Pain; Apparent Minor Injury; Burns-minor; Smoke Inhalation; Bruises

While the injury crashes shown on this map include any type of injury, summaries of injuries submitted for federal reports only include those that fall under the Model Minimum Uniform Crash Criteria https://www.nhtsa.gov/mmucc-1, which do not include "discomfort" and "pain". Note: Data definitions of injury categories may differ due to source (e.g., federal rules) and may change over time, which may cause numbers to vary among data sources. 

All data comes from MPD. 

    - Crashes in DC (Open Data): https://opendata.dc.gov/datasets/crashes-in-dc
    - Crash Details (Open Data): https://opendata.dc.gov/datasets/crash-details-table

</Details>