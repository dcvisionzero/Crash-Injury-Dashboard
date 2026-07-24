---
title: Temporal Analysis (BETA)
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
sidebar_link: false
---

```sql unique_mode
SELECT 
    MODE
FROM crashes.crashes
GROUP BY 1
```

```sql unique_severity
SELECT 
    SEVERITY
FROM crashes.crashes
GROUP BY 1
```

```sql day_time
WITH reference AS (
    SELECT
        dow.day_of_week,
        dow.day_number,
        hr.hour_number
    FROM 
        (VALUES 
            ('Sun', 0), 
            ('Mon', 1), 
            ('Tue', 2), 
            ('Wed', 3), 
            ('Thu', 4), 
            ('Fri', 5), 
            ('Sat', 6)
        ) AS dow(day_of_week, day_number),
        GENERATE_SERIES(0, 23) AS hr(hour_number)
),
count_data AS (
    SELECT
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 'Sun'
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 'Mon'
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 'Tue'
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 'Wed'
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 'Thu'
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 'Fri'
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 'Sat'
        END AS day_of_week,
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 0
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 1
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 2
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 3
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 4
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 5
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 6
        END AS day_number,
        LPAD(CAST(DATE_PART('hour', REPORTDATE) AS VARCHAR), 2, '0') AS hour_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
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
    GROUP BY day_of_week, day_number, hour_number
)
SELECT
    r.day_of_week,
    r.day_number,
    LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') AS hour_number,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON r.day_of_week = cd.day_of_week
 AND LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') = cd.hour_number
ORDER BY r.day_number, r.hour_number;
```

```sql time
WITH reference AS (
    SELECT hr.hour_number
    FROM GENERATE_SERIES(0, 23) AS hr(hour_number)
),
count_data AS (
    SELECT
        LPAD(CAST(DATE_PART('hour', REPORTDATE) AS VARCHAR), 2, '0') AS hour_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
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
    GROUP BY hour_number
)
SELECT
    'Total' AS Total,
    LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') AS hour_number,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON LPAD(CAST(r.hour_number AS VARCHAR), 2, '0') = cd.hour_number
ORDER BY r.hour_number;
```

```sql day
WITH reference AS (
    SELECT
        dow.day_of_week,
        dow.day_number,
        'Total' AS total
    FROM 
        (VALUES 
            ('Sun', 0), 
            ('Mon', 1), 
            ('Tue', 2), 
            ('Wed', 3), 
            ('Thu', 4), 
            ('Fri', 5), 
            ('Sat', 6)
        ) AS dow(day_of_week, day_number)
),
count_data AS (
    SELECT
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 'Sun'
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 'Mon'
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 'Tue'
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 'Wed'
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 'Thu'
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 'Fri'
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 'Sat'
        END AS day_of_week,
        CASE
            WHEN DATE_PART('dow', REPORTDATE) = 1 THEN 0
            WHEN DATE_PART('dow', REPORTDATE) = 2 THEN 1
            WHEN DATE_PART('dow', REPORTDATE) = 3 THEN 2
            WHEN DATE_PART('dow', REPORTDATE) = 4 THEN 3
            WHEN DATE_PART('dow', REPORTDATE) = 5 THEN 4
            WHEN DATE_PART('dow', REPORTDATE) = 6 THEN 5
            WHEN DATE_PART('dow', REPORTDATE) = 0 THEN 6
        END AS day_number,
        SUM("COUNT") AS "count"
    FROM crashes.crashes
    WHERE 
        MODE       IN ${inputs.multi_mode_dd.value}
        AND SEVERITY IN ${inputs.multi_severity.value}
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
    GROUP BY day_of_week, day_number
)
SELECT
    r.day_of_week,
    r.day_number,
    r.total,
    COALESCE(cd."count", 0) AS "count"
FROM reference r
LEFT JOIN count_data cd
  ON r.day_of_week = cd.day_of_week
ORDER BY r.day_number;
```

```sql period_compare
-- Current period vs the same window in each of the 5 prior years.
--
-- Returns one long-format table covering BOTH breakdowns and BOTH severities,
-- tagged by `dim` and `sev`:
--   dim = 'dow' -> Mon..Sun          sev = 'Fatal'
--   dim = 'tod' -> six 4-hour blocks sev = 'Major'
-- Two rows per bucket per severity: the prior-5-year average and the current
-- period.
--
-- Notes on convention:
--   * The Severity dropdown is deliberately NOT applied here. Fatalities and
--     major injuries move in opposite directions, so this page always shows
--     them side by side. Road user and age filters still apply.
--   * Shares are computed within each severity, so Fatal and Major each sum
--     to 100% and a 25-fatality year stays comparable to a 162-injury one.
--   * Windows are half-open [start, end) and prior years shift back by whole
--     years, matching the YoY logic on the home page. This differs slightly
--     from the BETWEEN ... + 1 day used by the heatmap queries above, which
--     is inclusive on both ends.
--   * `people` is the raw count for the current period and the per-year
--     average for the baseline.
--   * `is_valid` = 0 when the selected range spans more than one calendar
--     year, in which case a prior-period comparison is not meaningful and
--     the baseline series returns NULL.
WITH
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
  date_info AS (
    SELECT
      start_date,
      end_date,
      CASE
        WHEN end_date > start_date + INTERVAL '1 year' THEN 0
        WHEN EXTRACT(YEAR FROM start_date)
             <> EXTRACT(YEAR FROM end_date - INTERVAL '1 day') THEN 0
        ELSE 1
      END AS is_valid,
      CASE
        WHEN start_date = DATE_TRUNC('year', start_date)
         AND end_date   = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
        THEN 1 ELSE 0
      END AS is_full_year
    FROM report_date_range
  ),
  labels AS (
    SELECT
      -- Current period label, same rules as `selected_date_range`
      CASE
        WHEN is_full_year = 1
          THEN CAST(EXTRACT(YEAR FROM start_date) AS VARCHAR)
        WHEN start_date = DATE_TRUNC('year', CURRENT_DATE)
         AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
          THEN CAST(EXTRACT(YEAR FROM (end_date - INTERVAL '1 day')) AS VARCHAR) || ' YTD'
        ELSE strftime(start_date, '%m/%d/%y')
             || '-'
             || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
      END AS current_label,
      -- Baseline label, e.g. '21-'25 YTD Avg
      '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 5 AS VARCHAR), 2)
           || '-'
           || '''' || RIGHT(CAST(EXTRACT(YEAR FROM start_date) - 1 AS VARCHAR), 2)
           || CASE WHEN is_full_year = 1 THEN ' Avg' ELSE ' YTD Avg' END
      AS prior_label
    FROM date_info
  ),
  -- Road user and age filters still apply. Severity does NOT: this block
  -- always returns Fatal and Major separately so the two can sit side by
  -- side, independent of the Severity dropdown.
  filtered AS (
    SELECT REPORTDATE, "COUNT", SEVERITY
    FROM crashes.crashes
    WHERE
      MODE IN ${inputs.multi_mode_dd.value}
      AND SEVERITY IN ('Fatal', 'Major')
      AND AGE BETWEEN ${inputs.min_age.value}
                  AND (
                      CASE 
                          WHEN ${inputs.min_age.value} <> 0 
                               AND ${inputs.max_age.value} = 120
                          THEN 119
                          ELSE ${inputs.max_age.value}
                      END
                  )
  ),
  -- Stack the two breakdowns so the period logic below is written once
  tagged AS (
    SELECT
      REPORTDATE,
      "COUNT",
      SEVERITY AS sev,
      'dow' AS dim,
      CASE DATE_PART('dow', REPORTDATE)
        WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
        WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri'
        ELSE 'Sat'
      END AS bucket
    FROM filtered
    UNION ALL
    SELECT
      REPORTDATE,
      "COUNT",
      SEVERITY AS sev,
      'tod' AS dim,
      CASE
        WHEN DATE_PART('hour', REPORTDATE) < 4  THEN '12a-4a'
        WHEN DATE_PART('hour', REPORTDATE) < 8  THEN '4a-8a'
        WHEN DATE_PART('hour', REPORTDATE) < 12 THEN '8a-12p'
        WHEN DATE_PART('hour', REPORTDATE) < 16 THEN '12p-4p'
        WHEN DATE_PART('hour', REPORTDATE) < 20 THEN '4p-8p'
        ELSE '8p-12a'
      END AS bucket
    FROM filtered
  ),
  -- Reference grid so empty buckets still render, one set per severity
  bucket_ref AS (
    SELECT * FROM (VALUES
      ('dow', 'Mon', 0), ('dow', 'Tue', 1), ('dow', 'Wed', 2), ('dow', 'Thu', 3),
      ('dow', 'Fri', 4), ('dow', 'Sat', 5), ('dow', 'Sun', 6),
      ('tod', '12a-4a', 0), ('tod', '4a-8a', 1), ('tod', '8a-12p', 2),
      ('tod', '12p-4p', 3), ('tod', '4p-8p', 4), ('tod', '8p-12a', 5)
    ) AS t(dim, bucket, bucket_order)
  ),
  sev_ref AS (
    SELECT * FROM (VALUES ('Fatal'), ('Major')) AS t(sev)
  ),
  grid AS (
    SELECT b.dim, b.bucket, b.bucket_order, s.sev
    FROM bucket_ref b CROSS JOIN sev_ref s
  ),
  offsets AS (
    SELECT gs AS yr_offset FROM GENERATE_SERIES(1, 5) AS t(gs)
  ),
  current_counts AS (
    SELECT g.dim, g.bucket, g.sev, SUM(g."COUNT") AS n
    FROM tagged g, date_info d
    WHERE g.REPORTDATE >= d.start_date
      AND g.REPORTDATE <  d.end_date
    GROUP BY 1, 2, 3
  ),
  -- Pooled across the 5 prior windows; divided by 5 for the average
  prior_counts AS (
    SELECT g.dim, g.bucket, g.sev, SUM(g."COUNT") AS n
    FROM tagged g, date_info d, offsets o
    WHERE d.is_valid = 1
      AND g.REPORTDATE >= d.start_date - (o.yr_offset * INTERVAL '1 year')
      AND g.REPORTDATE <  d.end_date   - (o.yr_offset * INTERVAL '1 year')
    GROUP BY 1, 2, 3
  ),
  -- Shares are within each severity, so Fatal and Major each sum to 100%
  cur_tot AS (SELECT dim, sev, SUM(n) AS tot FROM current_counts GROUP BY 1, 2),
  pri_tot AS (SELECT dim, sev, SUM(n) AS tot FROM prior_counts   GROUP BY 1, 2)
SELECT
  r.dim,
  r.sev,
  r.bucket,
  r.bucket_order,
  l.prior_label                                        AS period,
  0                                                    AS period_order,
  CASE WHEN d.is_valid = 1
       THEN ROUND(CAST(COALESCE(p.n, 0) AS DOUBLE) / 5.0, 1) END  AS people,
  CASE WHEN d.is_valid = 1
       THEN CAST(COALESCE(p.n, 0) AS DOUBLE) / NULLIF(pt.tot, 0) END AS share,
  d.is_valid
FROM grid r
LEFT JOIN prior_counts p ON p.dim = r.dim AND p.bucket = r.bucket AND p.sev = r.sev
LEFT JOIN pri_tot     pt ON pt.dim = r.dim AND pt.sev = r.sev
CROSS JOIN labels l
CROSS JOIN date_info d
UNION ALL
SELECT
  r.dim,
  r.sev,
  r.bucket,
  r.bucket_order,
  l.current_label                                      AS period,
  1                                                    AS period_order,
  CAST(COALESCE(c.n, 0) AS DOUBLE)                     AS people,
  CAST(COALESCE(c.n, 0) AS DOUBLE) / NULLIF(ct.tot, 0) AS share,
  d.is_valid
FROM grid r
LEFT JOIN current_counts c ON c.dim = r.dim AND c.bucket = r.bucket AND c.sev = r.sev
LEFT JOIN cur_tot       ct ON ct.dim = r.dim AND ct.sev = r.sev
CROSS JOIN labels l
CROSS JOIN date_info d
ORDER BY dim, sev, bucket_order, period_order;
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

```sql selected_date_range
WITH
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
date_info AS (
    SELECT
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
      END AS current_period_range
    FROM report_date_range
)
SELECT current_period_range
FROM date_info;
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

<script>
  // Split the query by breakdown AND severity, then drop every column the
  // chart does not need. That second part matters: Evidence draws each
  // numeric column as its own series, so leaving bucket_order / period_order
  // / is_valid in the data produces a legend full of junk series.
  // Row order is preserved from the SQL ORDER BY, which is why sort=false
  // is enough to keep Mon..Sun and 12a-4a..8p-12a in the right sequence.
  const forChart = (rows, which, severity) =>
    (rows ?? [])
      .filter(d => d.dim === which && d.sev === severity)
      .map(d => ({ bucket: d.bucket, period: d.period, share: d.share, people: d.people }));

  $: dow_fatal = forChart(period_compare, 'dow', 'Fatal');
  $: dow_major = forChart(period_compare, 'dow', 'Major');
  $: tod_fatal = forChart(period_compare, 'tod', 'Fatal');
  $: tod_major = forChart(period_compare, 'tod', 'Major');

  // Series labels come from the query so they follow the selected date range
  $: prior_label   = (period_compare ?? []).find(d => d.period_order === 0)?.period ?? '';
  $: current_label = (period_compare ?? []).find(d => d.period_order === 1)?.period ?? '';

  // 0 when the selected range spans more than one calendar year
  $: comparison_valid = (period_compare ?? []).length ? period_compare[0].is_valid === 1 : true;

  // Gray baseline in both charts; current period carries the severity color
  const fatalPalette = ['#6c757d', '#ff5a53'];
  const majorPalette = ['#6c757d', '#ff9412'];

  // Bar labels read "12%" over "(3)": rounded share of the period total, with
  // the underlying people count beneath it. ECharts only hands the formatter
  // the plotted y value, so the count is looked up from the same row by
  // category name (p.name) and series label (p.seriesName).
  // No fontSize or color is set, so the labels inherit Evidence's own chart
  // text style. Two lines rather than "12% (3)" on one, because these charts
  // are now quarter-width and a single line will not fit.
  const makeLabelCfg = (rows) => ({
    label: {
      show: true,
      position: 'top',
      formatter: (p) => {
        const bucket = p.name ?? (Array.isArray(p.value) ? p.value[0] : null);
        const row = (rows ?? []).find(
          d => d.bucket === bucket && d.period === p.seriesName
        );
        if (!row || row.share == null) return '';
        return Math.round(row.share * 100) + '%\n(' + Math.round(row.people) + ')';
      }
    }
  });

  // One config per series; ECharts merges the series array by index
  $: dowFatalLabels = { series: [makeLabelCfg(dow_fatal), makeLabelCfg(dow_fatal)] };
  $: dowMajorLabels = { series: [makeLabelCfg(dow_major), makeLabelCfg(dow_major)] };
  $: todFatalLabels = { series: [makeLabelCfg(tod_fatal), makeLabelCfg(tod_fatal)] };
  $: todMajorLabels = { series: [makeLabelCfg(tod_major), makeLabelCfg(tod_major)] };
</script>

<Grid cols=2>
    <Group>
        <div style="font-size: 14px;">
            <b>Fatalities and Major Injuries for {`${mode_severity_selection[0].MODE_SELECTION}`}: {`${selected_date_range[0].current_period_range}`} vs the Prior 5-Year Average</b>
        </div>

        {#if !comparison_valid}
        <Alert status=warning>
            The prior-period comparison needs a date range inside a single calendar year. Use the <b>Year to Today</b> or <b>Last Year</b> preset, or pick a custom range that does not cross a year boundary. The heatmaps on the right are unaffected.
        </Alert>
        {/if}

        <div style="font-size: 13px; margin-top: 8px;">
            <b>By Day of Week</b>
        </div>
        <Grid cols=2>
            <Group>
                <BarChart
                    data={dow_fatal}
                    title="Fatalities"
                    x=bucket
                    y=share
                    series=period
                    seriesOrder={[prior_label, current_label]}
                    type=grouped
                    sort=false
                    chartAreaHeight={230}
                    colorPalette={fatalPalette}
                    yAxisTitle="Share"
                    yFmt=pct1
                    legend={true}
                    echartsOptions={dowFatalLabels}
                />
            </Group>
            <Group>
                <BarChart
                    data={dow_major}
                    title="Major Injuries"
                    x=bucket
                    y=share
                    series=period
                    seriesOrder={[prior_label, current_label]}
                    type=grouped
                    sort=false
                    chartAreaHeight={230}
                    colorPalette={majorPalette}
                    yAxisTitle="Share"
                    yFmt=pct1
                    legend={true}
                    echartsOptions={dowMajorLabels}
                />
            </Group>
        </Grid>

        <div style="font-size: 13px; margin-top: 8px;">
            <b>By Time of Day</b>
        </div>
        <Grid cols=2>
            <Group>
                <BarChart
                    data={tod_fatal}
                    title="Fatalities"
                    x=bucket
                    y=share
                    series=period
                    seriesOrder={[prior_label, current_label]}
                    type=grouped
                    sort=false
                    chartAreaHeight={220}
                    colorPalette={fatalPalette}
                    yAxisTitle="Share"
                    yFmt=pct1
                    legend={true}
                    echartsOptions={todFatalLabels}
                />
            </Group>
            <Group>
                <BarChart
                    data={tod_major}
                    title="Major Injuries"
                    x=bucket
                    y=share
                    series=period
                    seriesOrder={[prior_label, current_label]}
                    type=grouped
                    sort=false
                    chartAreaHeight={220}
                    colorPalette={majorPalette}
                    yAxisTitle="Share"
                    yFmt=pct1
                    legend={true}
                    echartsOptions={todMajorLabels}
                />
            </Group>
        </Grid>

        <Note>
            These four charts always show fatalities and major injuries separately and ignore the Severity filter. The Road User, Age and date range filters still apply. Bars show each bucket's share of its own severity total for that period, with the underlying people count in parentheses; the baseline count is a per-year average across the 5 prior years.
        </Note>
    </Group>
    <Group>
        <div style="font-size: 14px;">
            <b>{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by Day of Week & Time of the Day ({`${selected_date_range[0].current_period_range}`})</b>
        </div>
        <Heatmap
        data={day}
        subtitle=" "
        x="day_of_week" xSort="day_number"
        y="total"
        value="count"
        legend={true}
        valueLabels={true}
        mobileValueLabels={true}
        chartAreaHeight={50}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                const dayNames = {
                'Sun': 'Sunday','Mon': 'Monday','Tue': 'Tuesday',
                'Wed': 'Wednesday','Thu': 'Thursday','Fri': 'Friday','Sat': 'Saturday'
                };
                let dayAbbrev, count;
                if (params.value && Array.isArray(params.value)) {
                dayAbbrev = params.value[0];
                count      = params.value[2];
                } else {
                dayAbbrev = params.data.day_of_week;
                count     = params.data.count;
                }
                return `<strong>${dayNames[dayAbbrev]}</strong><br>Count: ${count}`;
            }
            }
        }}
        />
        <Heatmap
        data={day_time}
        subtitle="24-Hour Format"
        x="hour_number" xSort="hour_number"
        y="day_of_week" ySort="day_number"
        value="count"
        legend={true}
        filter={true}
        mobileValueLabels={true}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                const dayNames = {
                'Sun': 'Sunday','Mon': 'Monday','Tue': 'Tuesday',
                'Wed': 'Wednesday','Thu': 'Thursday','Fri': 'Friday','Sat': 'Saturday'
                };
                let hour, dayAbbrev, count;
                if (params.value && Array.isArray(params.value)) {
                hour      = params.value[0];
                dayAbbrev = params.value[1];
                count     = params.value[2];
                } else {
                hour      = params.data.hour_number;
                dayAbbrev = params.data.day_of_week;
                count     = params.data.count;
                }
                return `<strong>${dayNames[dayAbbrev]}</strong><br><strong>${hour} hrs</strong><br>Count: ${count}`;
            }
            }
        }}
        />
        <Heatmap
        data={time}
        subtitle="24-Hour Format"
        x="hour_number" xSort="hour_number"
        y="Total"
        value="count"
        legend={true}
        filter={true}
        chartAreaHeight={50}
        mobileValueLabels={true}
        echartsOptions={{
            tooltip: {
            formatter: function (params) {
                let hour, count;
                if (params.value && Array.isArray(params.value)) {
                hour  = params.value[0];
                count = params.value[2];
                } else {
                hour  = params.data.hour_number;
                count = params.data.count;
                }
                return `<strong>${hour} hrs</strong><br>Count: ${count}`;
            }
            }
        }}
        />
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons.
</Note>
