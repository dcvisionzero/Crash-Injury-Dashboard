---
title: Intersections
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
sidebar_link: false
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

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME,
    CASE
        WHEN TIER_1 = 1 THEN '1'
        WHEN TIER_2 = 1 THEN '2'
        WHEN TIER_3 = 1 THEN '3'
        ELSE NULL
    END AS Tier
from hin.hin
group by all
```

```sql intersection_map
SELECT
    c.INTERSECTIONKEY,
    ANY_VALUE(c.INTERSECTION_NAME) AS INTERSECTION_NAME,
    COALESCE(SUM(c.COUNT), 0) AS count
FROM crashes.crashes c
WHERE c.INTERSECTIONKEY IS NOT NULL
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
GROUP BY c.INTERSECTIONKEY
```

```sql period_comp_intx
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
    unique_intx AS (
        SELECT 
            INTERSECTIONKEY,
            canonical_name AS INTERSECTION_NAME
        FROM 
            intersections.intersections_unique
        WHERE 
            INTERSECTIONKEY IS NOT NULL
            AND ('${inputs.roadsegment_a.value}' = 'All Streets'
                 OR STREET_1_FULL = '${inputs.roadsegment_a.value}'
                 OR STREET_2_FULL = '${inputs.roadsegment_a.value}')
            AND ('${inputs.roadsegment_b.value}' = 'All Streets'
                 OR STREET_1_FULL = '${inputs.roadsegment_b.value}'
                 OR STREET_2_FULL = '${inputs.roadsegment_b.value}')
            AND (CASE
                    WHEN length('${inputs.intx_select_pt.INTERSECTIONKEY}') = 32
                        THEN INTERSECTIONKEY = '${inputs.intx_select_pt.INTERSECTIONKEY}'
                    WHEN length('${inputs.intx_select.INTERSECTIONKEY}') = 32
                        THEN INTERSECTIONKEY = '${inputs.intx_select.INTERSECTIONKEY}'
                    ELSE TRUE
                 END)
    ),
    crashed_intx AS (
        SELECT DISTINCT 
            INTERSECTIONKEY
        FROM 
            crashes.crashes
        WHERE 
            INTERSECTIONKEY IS NOT NULL
    ),
    current_period AS (
        SELECT 
            crashes.INTERSECTIONKEY, 
            SUM(crashes.COUNT) AS sum_count
        FROM 
            crashes.crashes 
        JOIN 
            unique_intx ui 
            ON crashes.INTERSECTIONKEY = ui.INTERSECTIONKEY
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
            crashes.INTERSECTIONKEY
    ),
    prior_period AS (
        SELECT 
            crashes.INTERSECTIONKEY, 
            SUM(crashes.COUNT) AS sum_count
        FROM 
            crashes.crashes 
        JOIN 
            unique_intx ui 
            ON crashes.INTERSECTIONKEY = ui.INTERSECTIONKEY
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
            crashes.INTERSECTIONKEY
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
    ui.INTERSECTIONKEY,
    ui.INTERSECTION_NAME,
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
        WHEN ci.INTERSECTIONKEY IS NOT NULL THEN
            '/intersections/' || ui.INTERSECTIONKEY
            || '?start='    || '${inputs.date_range.start}'
            || '&end='      || '${inputs.date_range.end}'
            || '&severity=' || array_to_string(list_value${inputs.multi_severity.value}, ',')
            || '&mode='     || array_to_string(list_value${inputs.multi_mode_dd.value}, ',')
            || '&min_age='  || '${inputs.min_age.value}'
            || '&max_age='  || '${inputs.max_age.value}'
    END AS link
FROM unique_intx ui
LEFT JOIN current_period cp ON ui.INTERSECTIONKEY = cp.INTERSECTIONKEY
LEFT JOIN prior_period pp ON ui.INTERSECTIONKEY = pp.INTERSECTIONKEY
LEFT JOIN crashed_intx ci ON ui.INTERSECTIONKEY = ci.INTERSECTIONKEY
ORDER BY current_period_sum DESC, ui.INTERSECTIONKEY;
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

```sql roadsegment_dropdown_a
SELECT 'All Streets' AS road, 0 AS sort_order
UNION ALL
SELECT DISTINCT road, 1 AS sort_order
FROM (
    SELECT STREET_1_FULL AS road FROM intersections.intersections_unique WHERE INTERSECTIONKEY IS NOT NULL
    UNION
    SELECT STREET_2_FULL AS road FROM intersections.intersections_unique WHERE INTERSECTIONKEY IS NOT NULL
)
ORDER BY sort_order, road
```

```sql roadsegment_dropdown_b
SELECT 'All Streets' AS road, 0 AS sort_order
UNION ALL
SELECT DISTINCT road, 1 AS sort_order
FROM (
    SELECT STREET_2_FULL AS road FROM intersections.intersections_unique
        WHERE STREET_1_FULL = '${inputs.roadsegment_a.value}' AND INTERSECTIONKEY IS NOT NULL
    UNION
    SELECT STREET_1_FULL AS road FROM intersections.intersections_unique
        WHERE STREET_2_FULL = '${inputs.roadsegment_a.value}' AND INTERSECTIONKEY IS NOT NULL
)
ORDER BY sort_order, road
```

```sql intx_vs_overall
WITH
    report_date_range AS (
        SELECT
        CASE 
            WHEN '${inputs.date_range.end}'::DATE >= (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE
            THEN (SELECT MAX(LAST_RECORD) FROM crashes.crashes)::DATE + INTERVAL '1 day'
            ELSE '${inputs.date_range.end}'::DATE + INTERVAL '1 day'
        END AS end_date,
        '${inputs.date_range.start}'::DATE AS start_date
    ),
    date_info AS (
        SELECT start_date, end_date,
            CASE
                WHEN start_date = DATE_TRUNC('year', start_date) AND end_date = DATE_TRUNC('year', start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM start_date)::VARCHAR
                WHEN start_date = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = end_date - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM (end_date - INTERVAL '1 day'))::VARCHAR || ' YTD'
                ELSE strftime(start_date, '%m/%d/%y') || '-' || strftime(end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS date_range_label
        FROM report_date_range
    ),
    offset_period AS (
        SELECT start_date, end_date,
        CASE 
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
                WHEN prior_start_date = DATE_TRUNC('year', prior_start_date) AND prior_end_date = DATE_TRUNC('year', prior_start_date) + INTERVAL '1 year'
                    THEN EXTRACT(YEAR FROM prior_start_date)::VARCHAR
                WHEN (SELECT start_date FROM date_info) = DATE_TRUNC('year', CURRENT_DATE) AND '${inputs.date_range.end}'::DATE = (SELECT end_date FROM date_info) - INTERVAL '1 day'
                    THEN EXTRACT(YEAR FROM prior_end_date)::VARCHAR || ' YTD'
                ELSE strftime(prior_start_date, '%m/%d/%y') || '-' || strftime(prior_end_date - INTERVAL '1 day', '%m/%d/%y')
            END AS prior_date_range_label
        FROM prior_date_info
    ),
    filt AS (
        SELECT REPORTDATE, INTERSECTIONKEY, "COUNT"
        FROM crashes.crashes
        WHERE SEVERITY IN ${inputs.multi_severity.value}
          AND MODE IN ${inputs.multi_mode_dd.value}
          AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
    ),
    current_totals AS (
        SELECT
            SUM(CASE WHEN INTERSECTIONKEY IS NOT NULL THEN "COUNT" ELSE 0 END) AS c_in,
            SUM("COUNT") AS c_all
        FROM filt
        WHERE REPORTDATE BETWEEN (SELECT start_date FROM date_info) AND (SELECT end_date FROM date_info)
    ),
    prior_totals AS (
        SELECT
            SUM(CASE WHEN INTERSECTIONKEY IS NOT NULL THEN "COUNT" ELSE 0 END) AS p_in,
            SUM("COUNT") AS p_all
        FROM filt
        WHERE REPORTDATE BETWEEN (SELECT prior_start_date FROM prior_date_info) AND (SELECT prior_end_date FROM prior_date_info)
    )
SELECT
    (SELECT date_range_label FROM date_info) AS period,
    COALESCE((SELECT c_in FROM current_totals), 0) AS in_intersection,
    COALESCE((SELECT c_all FROM current_totals), 0) AS overall_count,
    COALESCE((SELECT c_in FROM current_totals), 0) * 1.0 / NULLIF((SELECT c_all FROM current_totals), 0) AS pct_in_intersection,
    1 AS sort_order
UNION ALL
SELECT
    (SELECT prior_date_range_label FROM prior_date_label),
    COALESCE((SELECT p_in FROM prior_totals), 0),
    COALESCE((SELECT p_all FROM prior_totals), 0),
    COALESCE((SELECT p_in FROM prior_totals), 0) * 1.0 / NULLIF((SELECT p_all FROM prior_totals), 0),
    2
ORDER BY sort_order
```

```sql intersection_points
-- Same counts as intersection_map, joined to centroids so the intersections
-- stay visible when zoomed out (the 100 ft polygons are too small to see
-- at city level). Shares the color scale with the polygon layer.
SELECT
    m.INTERSECTIONKEY,
    m.INTERSECTION_NAME,
    m.count,
    i.LATITUDE,
    i.LONGITUDE
FROM ${intersection_map} m
INNER JOIN intersections.intersections_unique i
    ON m.INTERSECTIONKEY = i.INTERSECTIONKEY
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

<Grid cols=2>
    <Group>
        <BaseMap
            height=450
            title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by Intersection ({`${period_comp_intx[0].current_period_range}`})"
        >
        <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00
            tooltip={[
                {id: 'ROUTENAME', showColumnName:false},
                {id: 'Tier'}
            ]}
        />
        <Areas data={intersection_map} name=intx_select geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/Intersection_Points_buffers.geojson' geoId=INTERSECTIONKEY areaCol=INTERSECTIONKEY value=count min=0 opacity=0.7 borderWidth=0.5 borderColor='#A9A9A9' ignoreZoom=true
            tooltip={[
                {id:'INTERSECTION_NAME', valueClass:'text-l font-semibold', showColumnName:false},
                {id:'count'}
            ]}
        />
        <Points data={intersection_points} name=intx_select_pt lat=LATITUDE long=LONGITUDE value=count min=0 opacity=0.5 ignoreZoom=true legend=false
            tooltip={[
                {id:'INTERSECTION_NAME', valueClass:'text-l font-semibold', showColumnName:false},
                {id:'count'}
            ]}
        />
        </BaseMap>
        <Note>
            The purple lines represent DC's High Injury Network.
        </Note>
        <Note>
            The shaded circles represent 100‑foot buffers around each intersection. The map displays only those intersections that have at least one injury crash under the selected filters.
        </Note>
    </Group>
    <Group>
        <div style="font-size: 14px;">
            <b>Find a Specific Intersection</b>
        </div>
        <Dropdown data={roadsegment_dropdown_a} name=roadsegment_a value=road title="Street 1" defaultValue="All Streets"/>
        <Dropdown data={roadsegment_dropdown_b} name=roadsegment_b value=road title="Street 2" defaultValue="All Streets"/>
        <DataTable data={period_comp_intx} link=link search=false rows=10 sort="current_period_sum desc" title="Year Over Year Comparison of {`${mode_severity_selection[0].SEVERITY_SELECTION}`} for {`${mode_severity_selection[0].MODE_SELECTION}`} by Intersection" wrapTitles=true rowShading=true>
            <Column id=INTERSECTION_NAME title="Intersection" wrap=true/>
            <Column id=current_period_sum title={`${period_comp_intx[0].current_period_range}`} />
            <Column id=prior_period_sum title={`${period_comp_intx[0].prior_period_range}`}  />
            <Column id=difference title="Diff" contentType=delta downIsGood=True />
            <Column id=percentage_change fmt='pct0' title="% Diff" /> 
        </DataTable>
        <DataTable data={intx_vs_overall} rows=all rowShading=true title="Injury Crashes at Intersections vs. Overall">
            <Column id=period title="Period"/>
            <Column id=in_intersection title="In Intersection" fmt='#,##0'/>
            <Column id=overall_count title="Overall" fmt='#,##0'/>
            <Column id=pct_in_intersection title="% in Intersection" fmt='pct0'/>
        </DataTable>
    </Group>
</Grid>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs. This lag factors into prior period comparisons. The maximum comparison period is 5 years. Crashes are assigned to the nearest intersection within 100 ft; crashes farther than that (mid-block) are excluded. Rows with at least one crash on record link to an intersection detail page.
</Note>