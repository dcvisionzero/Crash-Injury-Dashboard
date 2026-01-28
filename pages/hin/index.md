---
title: High Injury Network
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
sidebar_position: 10
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
WHERE
    SEVERITY = 'Fatal'
group by 1
```

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME,
    HIN_TIER,
from hin_polygon.hin_polygon
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

```sql hin_tier_table
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
            WHEN start_date = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
            AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
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
    unique_hin_tier AS (
        SELECT 
          HIN_TIER
        FROM hin_polygon.hin_polygon
        GROUP BY HIN_TIER
    ),

    -- NEW: Flatten HIN_TIER_A, HIN_TIER_B, and HIN_TIER_C into one column
    crashes_with_tiers AS (
        SELECT
            OBJECTID,  -- replace with your actual PK if different
            REPORTDATE,
            SEVERITY,
            MODE,
            AGE,
            HIN_TIER_A AS HIN_TIER,
            COUNT
        FROM crashes.crashes
        WHERE HIN_TIER_A IS NOT NULL

        UNION ALL

        SELECT
            OBJECTID,
            REPORTDATE,
            SEVERITY,
            MODE,
            AGE,
            HIN_TIER_B AS HIN_TIER,
            COUNT
        FROM crashes.crashes
        WHERE HIN_TIER_B IS NOT NULL

        UNION ALL

        SELECT
            OBJECTID,
            REPORTDATE,
            SEVERITY,
            MODE,
            AGE,
            HIN_TIER_C AS HIN_TIER,
            COUNT
        FROM crashes.crashes
        WHERE HIN_TIER_C IS NOT NULL
    ),

    current_period AS (
        SELECT 
            cwt.HIN_TIER, 
            SUM(cwt.COUNT) AS sum_count
        FROM crashes_with_tiers cwt
        JOIN unique_hin_tier uht 
            ON cwt.HIN_TIER = uht.HIN_TIER
        WHERE 
            cwt.SEVERITY IN ${inputs.multi_severity.value} 
            AND cwt.MODE IN ${inputs.multi_mode_dd.value}
            AND cwt.REPORTDATE BETWEEN (SELECT start_date FROM date_info) 
                                   AND (SELECT end_date FROM date_info)
            AND cwt.AGE BETWEEN ${inputs.min_age.value}
                            AND (
                                CASE 
                                    WHEN ${inputs.min_age.value} <> 0 
                                    AND ${inputs.max_age.value} = 120
                                    THEN 119
                                    ELSE ${inputs.max_age.value}
                                END
                            )
        GROUP BY cwt.HIN_TIER
    ),
    prior_period AS (
        SELECT 
            cwt.HIN_TIER, 
            SUM(cwt.COUNT) AS sum_count
        FROM crashes_with_tiers cwt
        JOIN unique_hin_tier uht 
            ON cwt.HIN_TIER = uht.HIN_TIER
        WHERE 
            cwt.SEVERITY IN ${inputs.multi_severity.value} 
            AND cwt.MODE IN ${inputs.multi_mode_dd.value}
            AND cwt.REPORTDATE BETWEEN (
                    (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period)
                ) AND (
                    (SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period)
                )
            AND cwt.AGE BETWEEN ${inputs.min_age.value}
                            AND (
                                CASE 
                                    WHEN ${inputs.min_age.value} <> 0 
                                    AND ${inputs.max_age.value} = 120
                                    THEN 119
                                    ELSE ${inputs.max_age.value}
                                END
                            )
        GROUP BY cwt.HIN_TIER
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
            AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
            THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
            ELSE
            strftime(prior_start_date,   '%m/%d/%y')
            || '-'
            || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
        END AS prior_date_range_label
        FROM prior_date_info
    ),
    totals AS (
        SELECT 
            SUM(COALESCE(cp.sum_count, 0)) AS current_period_total,
            SUM(COALESCE(pp.sum_count, 0)) AS prior_period_total
        FROM 
            unique_hin_tier mas
        LEFT JOIN current_period cp ON mas.HIN_TIER = cp.HIN_TIER
        LEFT JOIN prior_period pp ON mas.HIN_TIER = pp.HIN_TIER
    )
SELECT 
    mas.HIN_TIER,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    COALESCE(pp.sum_count, 0) AS prior_period_sum, 
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE 
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) != 0 THEN ((COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0))
                                                / COALESCE(pp.sum_count, 0))
        ELSE NULL 
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
    CASE 
        WHEN totals.prior_period_total != 0 THEN (
            (totals.current_period_total - totals.prior_period_total) / totals.prior_period_total
        )
        ELSE NULL
    END AS total_percentage_change
FROM unique_hin_tier mas
LEFT JOIN current_period cp ON mas.HIN_TIER = cp.HIN_TIER
LEFT JOIN prior_period pp ON mas.HIN_TIER = pp.HIN_TIER
CROSS JOIN totals;
```

```sql routename_tier_table
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
        WHEN start_date = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
        AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
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
        WHEN end_date > start_date + INTERVAL '5 year' THEN (SELECT 1/0)
        WHEN end_date > start_date + INTERVAL '4 year' THEN INTERVAL '5 year'
        WHEN end_date > start_date + INTERVAL '3 year' THEN INTERVAL '4 year'
        WHEN end_date > start_date + INTERVAL '2 year' THEN INTERVAL '3 year'
        WHEN end_date > start_date + INTERVAL '1 year' THEN INTERVAL '2 year'
        ELSE INTERVAL '1 year'
    END AS interval_offset
    FROM date_info
),
unique_ROUTENAME AS (
    SELECT 
      ROUTENAME
    FROM hin_polygon.hin_polygon
    GROUP BY ROUTENAME
),

-- Flatten ROUTENAME_A/B/C into one column
crashes_with_ROUTENAME AS (
    SELECT
        OBJECTID,
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        ROUTENAME_A AS ROUTENAME,
        COUNT
    FROM crashes.crashes
    WHERE ROUTENAME_A IS NOT NULL

    UNION ALL

    SELECT
        OBJECTID,
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        ROUTENAME_B AS ROUTENAME,
        COUNT
    FROM crashes.crashes
    WHERE ROUTENAME_B IS NOT NULL

    UNION ALL

    SELECT
        OBJECTID,
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        ROUTENAME_C AS ROUTENAME,
        COUNT
    FROM crashes.crashes
    WHERE ROUTENAME_C IS NOT NULL
),

current_period AS (
    SELECT 
        cwr.ROUTENAME, 
        SUM(cwr.COUNT) AS sum_count
    FROM crashes_with_ROUTENAME cwr
    JOIN unique_ROUTENAME ur 
        ON cwr.ROUTENAME = ur.ROUTENAME
    WHERE 
        cwr.SEVERITY IN ${inputs.multi_severity.value} 
        AND cwr.MODE IN ${inputs.multi_mode_dd.value}
        AND cwr.REPORTDATE BETWEEN (SELECT start_date FROM date_info) 
                               AND (SELECT end_date FROM date_info)
        AND cwr.AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
    GROUP BY cwr.ROUTENAME
),
prior_period AS (
    SELECT 
        cwr.ROUTENAME, 
        SUM(cwr.COUNT) AS sum_count
    FROM crashes_with_ROUTENAME cwr
    JOIN unique_ROUTENAME ur 
        ON cwr.ROUTENAME = ur.ROUTENAME
    WHERE 
        cwr.SEVERITY IN ${inputs.multi_severity.value} 
        AND cwr.MODE IN ${inputs.multi_mode_dd.value}
        AND cwr.REPORTDATE BETWEEN (
                (SELECT start_date FROM date_info) - (SELECT interval_offset FROM offset_period)
            ) AND (
                (SELECT end_date FROM date_info) - (SELECT interval_offset FROM offset_period)
            )
        AND cwr.AGE BETWEEN ${inputs.min_age.value}
                        AND (
                            CASE 
                                WHEN ${inputs.min_age.value} <> 0 
                                AND ${inputs.max_age.value} = 120
                                THEN 119
                                ELSE ${inputs.max_age.value}
                            END
                        )
    GROUP BY cwr.ROUTENAME
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
        AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
        THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
        ELSE
        strftime(prior_start_date,   '%m/%d/%y')
        || '-'
        || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
    END AS prior_date_range_label
    FROM prior_date_info
),
totals AS (
    SELECT 
        SUM(COALESCE(cp.sum_count, 0)) AS current_period_total,
        SUM(COALESCE(pp.sum_count, 0)) AS prior_period_total
    FROM 
        unique_ROUTENAME ur
    LEFT JOIN current_period cp ON ur.ROUTENAME = cp.ROUTENAME
    LEFT JOIN prior_period pp ON ur.ROUTENAME = pp.ROUTENAME
)
SELECT 
    ur.ROUTENAME,
    COALESCE(cp.sum_count, 0) AS current_period_sum, 
    COALESCE(pp.sum_count, 0) AS prior_period_sum, 
    COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0) AS difference,
    CASE 
        WHEN COALESCE(cp.sum_count, 0) = 0 THEN NULL
        WHEN COALESCE(pp.sum_count, 0) != 0 THEN ((COALESCE(cp.sum_count, 0) - COALESCE(pp.sum_count, 0))
                                                / COALESCE(pp.sum_count, 0))
        ELSE NULL 
    END AS percentage_change,
    (SELECT date_range_label FROM date_info) AS current_period_range,
    (SELECT prior_date_range_label FROM prior_date_label) AS prior_period_range,
    CASE 
        WHEN totals.prior_period_total != 0 THEN (
            (totals.current_period_total - totals.prior_period_total) / totals.prior_period_total
        )
        ELSE NULL
    END AS total_percentage_change
FROM unique_ROUTENAME ur
LEFT JOIN current_period cp ON ur.ROUTENAME = cp.ROUTENAME
LEFT JOIN prior_period pp ON ur.ROUTENAME = pp.ROUTENAME
CROSS JOIN totals;
```

```sql hin_rate
WITH 
-- 0) Flatten HIN tier columns into one
crashes_with_tiers AS (
  SELECT REPORTDATE, SEVERITY, MODE, AGE, COUNT, HIN_TIER_A AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_A IS NOT NULL
  UNION ALL
  SELECT REPORTDATE, SEVERITY, MODE, AGE, COUNT, HIN_TIER_B AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_B IS NOT NULL
  UNION ALL
  SELECT REPORTDATE, SEVERITY, MODE, AGE, COUNT, HIN_TIER_C AS HIN_TIER
  FROM crashes.crashes
  WHERE HIN_TIER_C IS NOT NULL
),

-- 1) Determine the current period bounds
report_date_range AS (
  SELECT
    CASE 
      WHEN '${inputs.date_range.end}'::DATE 
           >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
      THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
      ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
    END AS end_date,
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
      WHEN start_date = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
       AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
      THEN EXTRACT(YEAR FROM '${inputs.date_range.end}'::DATE)::VARCHAR || ' YTD'
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
      WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', '${inputs.date_range.end}'::DATE)
       AND '${inputs.date_range.end}'::DATE = (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
      THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
      ELSE
        strftime(prior_start_date, '%m/%d/%y')
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
    SEVERITY IN ${inputs.multi_severity.value}
    AND MODE     IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM current_window)
    AND (SELECT end_date   FROM current_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
current_total AS (
  SELECT SUM(COUNT) AS total_injuries
  FROM crashes.crashes
  WHERE
    SEVERITY IN ${inputs.multi_severity.value}
    AND MODE     IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM current_window)
    AND (SELECT end_date   FROM current_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
prior_hin AS (
  SELECT SUM(COUNT) AS injuries_in_hin_prior
  FROM crashes_with_tiers
  WHERE
    SEVERITY IN ${inputs.multi_severity.value}
    AND MODE     IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM prior_window)
    AND (SELECT end_date   FROM prior_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
),
prior_total AS (
  SELECT SUM(COUNT) AS total_injuries_prior
  FROM crashes.crashes
  WHERE
    SEVERITY IN ${inputs.multi_severity.value}
    AND MODE     IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN 
        (SELECT start_date FROM prior_window)
    AND (SELECT end_date   FROM prior_window)
    AND AGE BETWEEN (SELECT min_age FROM age_bounds) AND (SELECT max_age FROM age_bounds)
)

-- 7) Final output
SELECT
  1 AS period_sort,
  (SELECT date_range_label FROM date_info) AS period,
  ch.injuries_in_hin,
  ct.total_injuries,
  CASE 
    WHEN ct.total_injuries = 0 THEN NULL
    ELSE ch.injuries_in_hin * 1.0 / ct.total_injuries
  END AS proportion_hin
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
  END AS proportion_hin
FROM prior_hin AS ph
CROSS JOIN prior_total AS pt

ORDER BY period_sort;
```

```sql hin_tier_map
WITH
-- Flatten GIS_ID_A/B/C into one column
crashes_with_gis AS (
    SELECT
        OBJECTID, 
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        GIS_ID_A AS GIS_ID,
        COUNT
    FROM crashes.crashes
    WHERE GIS_ID_A IS NOT NULL

    UNION ALL

    SELECT
        OBJECTID,
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        GIS_ID_B AS GIS_ID,
        COUNT
    FROM crashes.crashes
    WHERE GIS_ID_B IS NOT NULL

    UNION ALL

    SELECT
        OBJECTID,
        REPORTDATE,
        SEVERITY,
        MODE,
        AGE,
        GIS_ID_C AS GIS_ID,
        COUNT
    FROM crashes.crashes
    WHERE GIS_ID_C IS NOT NULL
),

-- Get unique GIS_ID → HIN_TIER mapping from your HIN table
unique_gis_tier AS (
    SELECT DISTINCT
        GIS_ID,
        HIN_TIER AS TIER,
        ROUTENAME
    FROM hin_polygon.hin_polygon
)

SELECT
    ugt.GIS_ID,
    ugt.TIER,
    ugt.ROUTENAME,
    COALESCE(SUM(cwg.COUNT), 0) AS count
FROM unique_gis_tier ugt
LEFT JOIN crashes_with_gis cwg
    ON ugt.GIS_ID = cwg.GIS_ID
    AND cwg.MODE IN ${inputs.multi_mode_dd.value}
    AND cwg.SEVERITY IN ${inputs.multi_severity.value}
    AND cwg.REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
                           AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND cwg.AGE BETWEEN ${inputs.min_age.value}
                    AND (
                        CASE 
                            WHEN ${inputs.min_age.value} <> 0 
                            AND ${inputs.max_age.value} = 120
                            THEN 119
                            ELSE ${inputs.max_age.value}
                        END
                    )
GROUP BY ugt.GIS_ID, ugt.TIER, ugt.ROUTENAME
ORDER BY ugt.GIS_ID, ugt.TIER, ugt.ROUTENAME;
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
presetRanges={['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Last 6 Months', 'Last 12 Months', 'Month to Today', 'Last Month', 'Year to Today', 'Last Year', 'All Time']}
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
        <BaseMap
            height=560
            startingZoom=12
            title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by Road Segments of the HIN ({`${hin_tier_table[0].current_period_range}`})"
        >
        <Areas data={hin_tier_map} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/hin_buff_over_30.geojson' geoId=GIS_ID areaCol=GIS_ID value=count borderWidth=1
        tooltip={[
            {id:'ROUTENAME', showColumnName:false, fmt:'id', valueClass:'text-l font-semibold'},
            {id: 'TIER'},
            {id: 'count'}
        ]}
        />
        </BaseMap>
        <Note>
            The road segments have been oversized for visualization purposes
        </Note>
    </Group>
    <Group>
        <DataTable data={hin_tier_table} totalRow=true sort="current_period_sum desc" wrapTitles=true rowShading=true title="Year Over Year Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by HIN Tier">
            <Column id=HIN_TIER title=Tier wrap=true totalAgg="Total"/>
            <Column id=current_period_sum title="{hin_tier_table[0].current_period_range}" />
            <Column id=prior_period_sum title="{hin_tier_table[0].prior_period_range}" />
            <Column id=difference contentType=delta downIsGood=True title="Diff"/>
            <Column id=percentage_change fmt='pct0' title="% Diff" totalAgg={hin_tier_table[0].total_percentage_change} totalFmt='pct0' /> 
        </DataTable>
        <DataTable data={routename_tier_table} totalRow=true sort="current_period_sum desc" wrapTitles=true rowShading=true rows=8 title="Year Over Year Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by HIN Roadway">
            <Column id=ROUTENAME title=Roadway wrap=true totalAgg="Total"/>
            <Column id=current_period_sum title="{hin_tier_table[0].current_period_range}" />
            <Column id=prior_period_sum title="{hin_tier_table[0].prior_period_range}" />
            <Column id=difference contentType=delta downIsGood=True title="Diff"/>
            <Column id=percentage_change fmt='pct0' title="% Diff" totalAgg={hin_tier_table[0].total_percentage_change} totalFmt='pct0' /> 
        </DataTable>
        <DataTable data={hin_rate} wrapTitles=true rowShading=true title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} in HIN vs All Roads in DC">
            <Column id=period />
            <Column id=injuries_in_hin title="In HIN"/>
            <Column id=total_injuries title="Overall" />
            <Column id=proportion_hin title="% in HIN" fmt='pct0' />
        </DataTable>
        <Note>
            The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons. The maximum comparison period is 5 years.
        </Note>
    </Group>
</Grid>