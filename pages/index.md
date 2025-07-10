---
title: DC Vision Zero Traffic Fatalities and Injuries
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
---

<Details title="About this dashboard">

    The Traffic Fatalities and Injuries Dashboard can be used by the public to know more about injuries or fatalities product of a crash in the District of Columbia (DC).
    
    Adjust the Road User, Severity, Age and Date filters to refine the results.

</Details>

    - As of <Value data={last_record} column="latest_record"/> there <Value data={yoy_text_fatal} column="has_have"/> been <Value data={yoy_text_fatal} column="current_year_sum" agg=sum/> <Value data={yoy_text_fatal} column="fatality"/> among all road users in <Value data={yoy_text_fatal} column="current_year" fmt='####","'/>   <Value data={yoy_text_fatal} column="difference" agg=sum fmt='####' /> <Value data={yoy_text_fatal} column="difference_text"/> (<Delta data={yoy_text_fatal} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the same period in <Value data={yoy_text_fatal} column="year_prior" fmt="####."/>
    - As of <Value data={last_record} column="latest_record"/> there <Value data={yoy_text_major_injury} column="has_have"/> been <Value data={yoy_text_major_injury} column="current_year_sum" agg=sum/> <Value data={yoy_text_major_injury} column="major_injury"/> among all road users in <Value data={yoy_text_major_injury} column="current_year" fmt='####","'/>   <Value data={yoy_text_major_injury} column="difference" agg=sum fmt='####' /> <Value data={yoy_text_major_injury} column="difference_text"/> (<Delta data={yoy_text_major_injury} column="percentage_change" fmt="+0%;-0%;0%" downIsGood=True neutralMin=-0.00 neutralMax=0.00/>) compared to the same period in <Value data={yoy_text_major_injury} column="year_prior" fmt="####."/>

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

```sql interventions_table
SELECT improvement, 
    'https://visionzero.dc.gov/pages/engineering#safety' AS link,
    SUM(Count) AS count,
      CASE
    WHEN improvement = 'Leading Pedestrian Intervals (LPI)'
      THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/LPI_2.png'
    WHEN improvement = 'Rectangular Rapid Flashing Beacon (RRFB)'
      THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/RRFB_2.png'
    WHEN improvement = 'Curb Extensions'
      THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/CE_2.png'
    WHEN improvement = 'Annual Safety Improvement Program (ASAP) - Intersections'
      THEN 'https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Backend/main/Icons/intersection.png'
    ELSE NULL
  END AS icon
FROM interventions.interventions
GROUP BY improvement;
```

```sql barchart_mode
WITH 
    combinations AS (
        SELECT DISTINCT
            MODE,
            SEVERITY
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
    ),
    counts AS (
        SELECT
            MODE,
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
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
        GROUP BY MODE, SEVERITY
    )
SELECT
    c.MODE,
    c.SEVERITY,
    COALESCE(cnt.sum_count, 0) AS sum_count
FROM combinations c
LEFT JOIN counts cnt 
    ON c.MODE = cnt.MODE AND c.SEVERITY = cnt.SEVERITY;
```

```sql period_comp_mode
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
      (SELECT start_date      FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_start_date,
      (SELECT end_date        FROM date_info) - (SELECT interval_offset FROM offset_period) AS prior_end_date
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
  COALESCE(cp.sum_count, 0)                           AS current_period_sum,
  COALESCE(pp.sum_count, 0)                           AS prior_period_sum,
  COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
  CASE
    WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
    WHEN COALESCE(pp.sum_count, 0) != 0 THEN
      (COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0))
      / COALESCE(pp.sum_count, 0)
    ELSE NULL
  END AS percentage_change,
  (SELECT date_range_label       FROM date_info)       AS current_period_range,
  (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
  (total_current_period - total_prior_period)
    / NULLIF(total_prior_period, 0)                    AS total_percentage_change,
  COALESCE(cp.sum_count, 0)
    / NULLIF(total_current_period, 0)                  AS current_mode_percentage,
  COALESCE(pp.sum_count, 0)
    / NULLIF(total_prior_period, 0)                    AS prior_mode_percentage
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
    modes_and_severities AS (
        SELECT DISTINCT 
            MODE
        FROM 
            crashes.crashes
    ), 
    current_period AS (
        SELECT 
            MODE,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
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
        GROUP BY 
            MODE
    ), 
    prior_period AS (
        SELECT 
            MODE,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE >= ((SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period))
            AND REPORTDATE <= ((SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period))
            AND AGE BETWEEN ${inputs.min_age.value}
                                AND (
                                    CASE 
                                        WHEN ${inputs.min_age.value} <> 0 
                                        AND ${inputs.max_age.value} = 120
                                        THEN 119
                                        ELSE ${inputs.max_age.value}
                                    END
                                    )
        GROUP BY 
            MODE
    ), 
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM 
            current_period cp
        FULL JOIN 
            prior_period pp 
        ON cp.MODE = pp.MODE
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
    mas.MODE,
    'Current Period'    AS period,
    COALESCE(cp.sum_count, 0)         AS period_sum,
    di.date_range_label               AS period_range
    FROM modes_and_severities mas
    LEFT JOIN current_period   cp ON mas.MODE = cp.MODE
    CROSS JOIN date_info       di

    UNION ALL

    SELECT
    mas.MODE,
    'Prior Period'      AS period,
    COALESCE(pp.sum_count, 0)         AS period_sum,
    pdl.prior_date_range_label        AS period_range
    FROM modes_and_severities mas
    LEFT JOIN prior_period     pp ON mas.MODE = pp.MODE
    CROSS JOIN prior_date_label pdl

    ORDER BY mas.MODE, period;
```

```sql period_comp_severity
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
    severities AS (
        SELECT DISTINCT 
            SEVERITY
        FROM 
            crashes.crashes
        WHERE
            SEVERITY IN ${inputs.multi_severity.value}     
    ), 
    current_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
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
        GROUP BY 
            SEVERITY
    ), 
    prior_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE >= (
                (SELECT start_date FROM offset_period) - (SELECT interval_offset FROM offset_period)
            )
            AND REPORTDATE <= (
                (SELECT end_date FROM offset_period) - (SELECT interval_offset FROM offset_period)
            )
            AND AGE BETWEEN ${inputs.min_age.value}
                                AND (
                                    CASE 
                                        WHEN ${inputs.min_age.value} <> 0 
                                        AND ${inputs.max_age.value} = 120
                                        THEN 119
                                        ELSE ${inputs.max_age.value}
                                    END
                                    )
        GROUP BY 
            SEVERITY
    ), 
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM 
            current_period cp
        FULL JOIN 
            prior_period pp 
        ON cp.SEVERITY = pp.SEVERITY
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
    s.SEVERITY,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    COALESCE(pp.sum_count, 0) AS prior_period_sum, 
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE 
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) <> 0 THEN ((COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0)) / COALESCE(pp.sum_count, 0))
        ELSE NULL
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
    (total_current_period - total_prior_period) / NULLIF(total_prior_period, 0) AS total_percentage_change,
    (COALESCE(cp.sum_count, 0) / NULLIF(total_current_period, 0)) AS current_severity_percentage,
    (COALESCE(pp.sum_count, 0) / NULLIF(total_prior_period, 0)) AS prior_severity_percentage
FROM 
    severities s
LEFT JOIN 
    current_period cp ON s.SEVERITY = cp.SEVERITY
LEFT JOIN 
    prior_period pp ON s.SEVERITY = pp.SEVERITY,
    total_counts;
```

```sql barchart_severity
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
    severities AS (
        SELECT DISTINCT 
            SEVERITY
        FROM 
            crashes.crashes
        WHERE
            SEVERITY IN ${inputs.multi_severity.value}     
    ), 
    current_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
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
        GROUP BY 
            SEVERITY
    ), 
    prior_period AS (
        SELECT 
            SEVERITY,
            SUM(COUNT) AS sum_count
        FROM 
            crashes.crashes 
        WHERE 
            SEVERITY IN ${inputs.multi_severity.value} 
            AND REPORTDATE >= (
                (SELECT start_date FROM offset_period) - (SELECT interval_offset FROM offset_period)
            )
            AND REPORTDATE <= (
                (SELECT end_date FROM offset_period) - (SELECT interval_offset FROM offset_period)
            )
            AND AGE BETWEEN ${inputs.min_age.value}
                                AND (
                                    CASE 
                                        WHEN ${inputs.min_age.value} <> 0 
                                        AND ${inputs.max_age.value} = 120
                                        THEN 119
                                        ELSE ${inputs.max_age.value}
                                    END
                                    )
        GROUP BY 
            SEVERITY
    ), 
    total_counts AS (
        SELECT 
            SUM(cp.sum_count) AS total_current_period,
            SUM(pp.sum_count) AS total_prior_period
        FROM 
            current_period cp
        FULL JOIN 
            prior_period pp 
        ON cp.SEVERITY = pp.SEVERITY
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
  s.SEVERITY,
  'Current Period' AS period,
  COALESCE(cp.sum_count, 0) AS period_sum,
  di.date_range_label       AS period_range
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

```sql yoy_text_fatal
WITH date_range AS (
    SELECT
        MAX(REPORTDATE)::DATE + INTERVAL '1 day' AS max_report_date
    FROM
        crashes.crashes
),
params AS (
    SELECT
        date_trunc('year', dr.max_report_date) AS current_year_start,
        dr.max_report_date AS current_year_end,
        date_trunc('year', dr.max_report_date - interval '1 year') AS prior_year_start,
        dr.max_report_date - interval '1 year' AS prior_year_end,
        extract(year FROM dr.max_report_date) AS current_year,
        extract(year FROM dr.max_report_date - interval '1 year') AS year_prior
    FROM
        date_range dr
),
yearly_counts AS (
    SELECT
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.current_year_start AND p.current_year_end
            THEN cr.COUNT ELSE 0 END) AS current_year_sum,
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.prior_year_start AND p.prior_year_end
            THEN cr.COUNT ELSE 0 END) AS prior_year_sum
    FROM
        crashes.crashes AS cr
        CROSS JOIN params p
    WHERE
        cr.SEVERITY = 'Fatal'
        AND cr.REPORTDATE >= p.prior_year_start -- More efficient date filtering
        AND cr.REPORTDATE <= p.current_year_end
)
SELECT
    'Fatal' AS severity,
    yc.current_year_sum,
    yc.prior_year_sum,
    ABS(yc.current_year_sum - yc.prior_year_sum) AS difference,
    CASE
        WHEN yc.prior_year_sum <> 0
        THEN ((yc.current_year_sum - yc.prior_year_sum)::numeric / yc.prior_year_sum)
        ELSE NULL
    END AS percentage_change,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'an increase of'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'a decrease of'
        ELSE NULL
    END AS percentage_change_text,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'more'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'fewer'
        ELSE 'no change'
    END AS difference_text,
    p.current_year,
    p.year_prior,
    CASE WHEN yc.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN yc.current_year_sum = 1 THEN 'fatality' ELSE 'fatalities' END AS fatality
FROM
    yearly_counts yc
    CROSS JOIN params p;
```

```sql yoy_text_major_injury
WITH date_range AS (
    SELECT
        MAX(REPORTDATE)::DATE + INTERVAL '1 day' AS max_report_date
    FROM
        crashes.crashes
),
params AS (
    SELECT
        date_trunc('year', dr.max_report_date) AS current_year_start,
        dr.max_report_date AS current_year_end,
        date_trunc('year', dr.max_report_date - interval '1 year') AS prior_year_start,
        dr.max_report_date - interval '1 year' AS prior_year_end,
        extract(year FROM dr.max_report_date) AS current_year,
        extract(year FROM dr.max_report_date - interval '1 year') AS year_prior
    FROM
        date_range dr
),
yearly_counts AS (
    SELECT
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.current_year_start AND p.current_year_end
            THEN cr.COUNT ELSE 0 END) AS current_year_sum,
        SUM(CASE
            WHEN cr.REPORTDATE BETWEEN p.prior_year_start AND p.prior_year_end
            THEN cr.COUNT ELSE 0 END) AS prior_year_sum
    FROM
        crashes.crashes AS cr
        CROSS JOIN params p
    WHERE
        cr.SEVERITY = 'Major'
        AND cr.REPORTDATE >= p.prior_year_start -- More efficient date filtering
        AND cr.REPORTDATE <= p.current_year_end
)
SELECT
    'Major' AS severity,
    yc.current_year_sum,
    yc.prior_year_sum,
    ABS(yc.current_year_sum - yc.prior_year_sum) AS difference,
    CASE
        WHEN yc.prior_year_sum <> 0
        THEN ((yc.current_year_sum - yc.prior_year_sum)::numeric / yc.prior_year_sum)
        ELSE NULL
    END AS percentage_change,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'an increase of'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'a decrease of'
        ELSE NULL
    END AS percentage_change_text,
    CASE
        WHEN (yc.current_year_sum - yc.prior_year_sum) > 0 THEN 'more'
        WHEN (yc.current_year_sum - yc.prior_year_sum) < 0 THEN 'fewer'
        ELSE 'no change'
    END AS difference_text,
    p.current_year,
    p.year_prior,
    CASE WHEN yc.current_year_sum = 1 THEN 'has' ELSE 'have' END AS has_have,
    CASE WHEN yc.current_year_sum = 1 THEN 'major injury' ELSE 'major injuries' END AS major_injury
FROM
    yearly_counts yc
    CROSS JOIN params p;
```

```sql severity_selection
WITH ordered_severities AS (
  SELECT DISTINCT
    SEVERITY
  FROM
    crashes.crashes
  WHERE
    SEVERITY IN ${inputs.multi_severity.value}
),
agg_severities AS (
  SELECT
    STRING_AGG(
      SEVERITY,
      ', '
      ORDER BY
        CASE SEVERITY
          WHEN 'Minor' THEN 1
          WHEN 'Major' THEN 2
          WHEN 'Fatal' THEN 3
        END
    ) AS severity_list,
    COUNT(SEVERITY) AS severity_count
  FROM
    ordered_severities
)
SELECT
  CASE
    WHEN severity_count = 0 THEN ' '
    WHEN severity_count = 1 THEN severity_list
    WHEN severity_count = 2 THEN REPLACE(severity_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(severity_list, ',([^,]+)$', ', and \\1')
  END AS SEVERITY_SELECTION
FROM
  agg_severities;
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
        <DataTable data={period_comp_mode} totalRow sort="current_period_sum desc" wrapTitles rowShading title="Year Over Year Comparison of {`${severity_selection[0].SEVERITY_SELECTION}`} Injuries by Road User">
            <Column id="MODE" title="Road User" description="*Fatal Only" wrap=true totalAgg="Total"/>
            <Column id=ICON title=' ' contentType=image height=22px align=center totalAgg=" "/>
            <Column id="current_period_sum" title="{period_comp_mode[0].current_period_range}"/>
            <Column id="prior_period_sum" title="{period_comp_mode[0].prior_period_range}"/>
            <Column id="difference" contentType="delta" downIsGood title="Diff"/>
            <Column id="percentage_change" fmt="pct0" title="% Diff" totalAgg={period_comp_mode[0].total_percentage_change} totalFmt="pct0"/>
        </DataTable>
        <div style="font-size: 14px;">
            <b>Percentage Breakdown of {`${severity_selection[0].SEVERITY_SELECTION}`} Injuries by Road User</b>
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
    <Group>
        <DataTable data={period_comp_severity} totalRow=true sort="current_period_sum desc" wrapTitles=true rowShading=true title="Year Over Year Comparison of Injuries by Severity for All Road Users">
            <Column id=SEVERITY title=Severity wrap=true totalAgg="Total"/>
            <Column id=current_period_sum title="{period_comp_severity[0].current_period_range}" />
            <Column id=prior_period_sum title="{period_comp_severity[0].prior_period_range}" />
            <Column id=difference contentType=delta downIsGood=True title="Diff"/>
            <Column id=percentage_change fmt='pct0' title="% Diff" totalAgg={period_comp_severity[0].total_percentage_change} totalFmt='pct0' /> 
        </DataTable>
        <div style="font-size: 14px;">
            <b>Percentage Breakdown of Injuries by Severity for All Road Users</b>
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
        <DataTable data={interventions_table} wrapTitles=true rowShading=true title="Roadway Safety Interventions" subtitle="Select any roadway intervention to learn more" link=link>
            <Column id=improvement wrap=true title="Intervention"/>
            <Column id=icon title=' ' contentType=image height=22px align=center />
            <Column id=count/>
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons. The maximum comparison period is 5 years.
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
        <td>Other</td>
        <td>Includes motor-driven cycles (commonly referred to as mopeds and motorcycles), as well as personal mobility devices such as standing scooters, bus occupants, truck occupants, and others, including unknown classifications.</td>
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