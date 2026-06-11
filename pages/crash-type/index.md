---
title: Crash Type
queries:
   - last_record: last_record.sql
   - age_range: age_range.sql
   - has_fatal: has_fatal.sql
   - has_major: has_major.sql
sidebar_position: 11
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

```sql unique_crash_type
select 
    TYPE_OF_CRASH
from crashes.crashes
group by 1
```

```sql sankey_crash_type
-- Flows: Road User (source) -> Crash Type (target), weighted by persons (COUNT).
-- percent = each flow's share of its source road user's total (so it reads as
-- "of pedestrians, X% were in this crash type").
WITH crash_map AS (
    SELECT * FROM (VALUES
        ('single motor vehicle', 'MV-Obj'),
        ('motor vehicle - motor vehicle', 'MV-MV'),
        ('multiple motor vehicles', '>2 MV'),
        ('single bicycle', 'Bic-Obj'),
        ('bicycle - bicycle', 'Bic-Bic'),
        ('multiple bicycles', '>2 Bic'),
        ('pedestrian only', 'Ped-Obj'),
        ('other', 'Oth-Obj'),
        ('single motorcycle*', 'MC*-Obj'),
        ('single standing scooter*', 'SS*-Obj'),
        ('motor vehicle - pedestrian', 'MV-Ped'),
        ('motor vehicle - bicycle', 'MV-Bic'),
        ('motor vehicle - other', 'MV-Oth'),
        ('motor vehicle - motorcycle*', 'MV-MC*'),
        ('motor vehicle - standing scooter*', 'MV-SS*'),
        ('other - bicycle', 'Oth-Bic'),
        ('other - pedestrian', 'Oth-Ped'),
        ('motorcycle* - pedestrian', 'MC*-Ped'),
        ('motorcycle* - bicycle', 'MC*-Bic'),
        ('standing scooter* - pedestrian', 'SS*-Ped'),
        ('standing scooter* - bicycle', 'SS*-Bic'),
        ('bicycle - pedestrian', 'Bic-Ped'),
        ('multi-party', 'MP'),
        ('unclassified', 'Unc')
    ) AS t(TYPE_OF_CRASH, TYPE_ABBR)
),
base AS (
    SELECT
        c.MODE,
        COALESCE(m.TYPE_ABBR, c.TYPE_OF_CRASH) AS crash_type,
        SUM(c.COUNT) AS value
    FROM crashes.crashes c
    LEFT JOIN crash_map m ON c.TYPE_OF_CRASH = m.TYPE_OF_CRASH
    WHERE
        c.MODE IN ${inputs.multi_mode_dd.value}
        AND c.SEVERITY = '${inputs.multi_severity.value}'
        AND c.TYPE_OF_CRASH IN ${inputs.multi_crash_type.value}
        AND c.REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE)
            AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
        AND c.AGE BETWEEN ${inputs.min_age.value}
            AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120
                      THEN 119 ELSE ${inputs.max_age.value} END)
    GROUP BY c.MODE, COALESCE(m.TYPE_ABBR, c.TYPE_OF_CRASH)
)
SELECT
    MODE       AS source,
    crash_type AS target,
    value,
    value::DOUBLE / NULLIF(SUM(value) OVER (PARTITION BY MODE), 0) AS percent
FROM base
WHERE value > 0
ORDER BY MODE, value DESC;
```

```sql crash_type_breakdown
-- Overall distribution across the current selection (one row per crash type).
WITH base AS (
    SELECT
        TYPE_OF_CRASH,
        SUM(COUNT) AS value
    FROM crashes.crashes
    WHERE
        MODE IN ${inputs.multi_mode_dd.value}
        AND SEVERITY = '${inputs.multi_severity.value}'
        AND TYPE_OF_CRASH IN ${inputs.multi_crash_type.value}
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
    GROUP BY TYPE_OF_CRASH
)
SELECT
    TYPE_OF_CRASH,
    value AS count,
    value::DOUBLE / NULLIF(SUM(value) OVER (), 0) AS percent
FROM base
WHERE value > 0
ORDER BY value DESC;
```

```sql mode_severity_selection
WITH
  total_modes_cte AS (
    SELECT COUNT(DISTINCT MODE) AS total_mode_count
    FROM crashes.crashes
  ),
  mode_agg_cte AS (
    SELECT
      STRING_AGG(
        DISTINCT CASE
          WHEN MODE LIKE '%*' THEN REPLACE(MODE, '*', 's*')
          ELSE MODE || 's'
        END,
        ', '
        ORDER BY MODE ASC
      ) AS mode_list,
      COUNT(DISTINCT MODE) AS mode_count
    FROM crashes.crashes
    WHERE MODE IN ${inputs.multi_mode_dd.value}
  ),
  severity_agg_cte AS (
    SELECT
      CASE '${inputs.multi_severity.value}'
        WHEN 'Fatal' THEN 'Fatalities'
        WHEN 'Major' THEN 'Major Injuries'
        WHEN 'Minor' THEN 'Minor Injuries'
        ELSE ' '
      END AS severity_list
  )
SELECT
  CASE
    WHEN mode_count = 0 THEN ' '
    WHEN mode_count = total_mode_count THEN 'All Road Users'
    WHEN mode_count = 1 THEN mode_list
    WHEN mode_count = 2 THEN REPLACE(mode_list, ', ', ' and ')
    ELSE REGEXP_REPLACE(mode_list, ',([^,]+)$', ', and \\1')
  END AS MODE_SELECTION,
  severity_list AS SEVERITY_SELECTION
FROM
  mode_agg_cte,
  severity_agg_cte,
  total_modes_cte;
```

<DateRange
start="2015-01-01"
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
    const todayStr = fmt.format(new Date());
    const [year, month, day] = todayStr.split('-').map(Number);
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
    defaultValue={
        (() => {
            const fmt = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' });
            const [year, month, day] = fmt.format(new Date()).split('-').map(Number);
            const inFirstWeek = (month === 1 && day <= 9);
            const noFatalYet = (has_fatal[0].f_count === 0);
            const useMinor = !inFirstWeek && noFatalYet;
            return useMinor ? 'Minor' : 'Fatal';
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
    data={unique_crash_type} 
    name=multi_crash_type
    value=TYPE_OF_CRASH
    title="Crash Type"
    multiple=true
    selectAllByDefault=true
    description="Optional. Leave all selected to explore every crash type."
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
    <b>{`${mode_severity_selection[0].SEVERITY_SELECTION}`} by Crash Type for {`${mode_severity_selection[0].MODE_SELECTION}`}</b>
</div>

<Note>
    Each flow goes from a road user to the crash type they were involved in. Percentages show each crash type's share of that road user's total. Counts are persons, not crashes.
</Note>

<script>
  const roadUserColors = {
    'Driver':        '#2563EB',
    'Passenger':     '#38BDF8',
    'Pedestrian':    '#EC4899',
    'Bicyclist':     '#10B981',
    'Scooterist*':   '#34F5C5',
    'Motorcyclist*': '#D946EF',
    'Other':         '#94A3B8',
  };

  const severityColors = {
    'Minor': '#ffdf00',
    'Major': '#ff9412',
    'Fatal': '#ff5a53',
  };

  const severityCrashLabel = {
    'Fatal': 'Fatal Crash',
    'Major': 'Major Crash',
    'Minor': 'Minor Crash',
  };

  $: crashHeader = severityCrashLabel[inputs.multi_severity?.value] ?? 'Crash Type';

  $: crashTypeColor = severityColors[inputs.multi_severity?.value] ?? '#A8A29E';

  $: sankeyNodes = (() => {
    const rows = sankey_crash_type ?? [];
    const names = [...new Set([
      ...rows.map(r => r.source),
      ...rows.map(r => r.target)
    ])];
    return names.map(name => ({
      name,
      itemStyle: { color: roadUserColors[name] ?? crashTypeColor }
    }));
  })();
</script>

{#key sankey_crash_type}
<SankeyDiagram
    data={sankey_crash_type}
    sourceCol=source
    targetCol=target
    valueCol=value
    percentCol=percent
    linkLabels=full
    linkColor=source
    nodeLabels=name
    valueFmt=num0
    chartAreaHeight={500}
    nodeGap={20}
    sort=true
    emptySet=pass
    emptyMessage="No crashes match the current filters"   
    echartsOptions={{
        series: [{
            data: sankeyNodes,
            top: 40,
            left: '3%',
            right: '8%',
            bottom: '2%',
            labelLayout: { hideOverlap: false },
            label:     { fontSize: 13, formatter: (params) => params.name },
            edgeLabel: { fontSize: 13 }
        }],
        graphic: [
            { type: 'text', left: '3%',  top: 15,
            style: { text: 'Road User',  fontSize: 13, fontWeight: 'bold', fill: '#475569' } },
            { type: 'text', left: '70%', top: 15,
            style: { text: crashHeader, fontSize: 13, fontWeight: 'bold', fill: '#475569', textAlign: 'center', lineHeight: 17 } }
        ]
    }}
/>
{/key}


<Note>
    Crash type abbreviations: Motor Vehicle (MV), Bicycle (Bic), Pedestrian (Ped), Other (Oth), Motorcycle* (MC*), Standing Scooter* (SS*), Multi-party (MP), Object (Obj), Unclassified (Unc).
</Note>

<Note>
    *Fatal only.  For fatalities, crash type is defined exclusively by the first striking vehicle and the second striking vehicle or object.
</Note>

<Note>
    If too many counts and percentages overlap, try further filtering by Road User or moving the Road User node on the left side.
</Note>

<Note>
    The latest crash record in the dataset is from <Value data={last_record} column="latest_record"/> and the data was last updated on <Value data={last_record} column="latest_update"/> hrs.
</Note>

<Details title="See Total {`${mode_severity_selection[0].SEVERITY_SELECTION}`} by Crash Type">
    
    <DataTable data={crash_type_breakdown} sort="count desc" title="{`${mode_severity_selection[0].SEVERITY_SELECTION}`} by Crash Type for {`${mode_severity_selection[0].MODE_SELECTION}`}" totalRow=true wrapTitles=true rowShading=true>
        <Column id=TYPE_OF_CRASH title="Crash Type" totalAgg="Total"/>
        <Column id=count title="{`${mode_severity_selection[0].MODE_SELECTION}`}" />
        <Column id=percent fmt="pct1" title="% of Total" totalAgg=sum/>
    </DataTable>

</Details>

<Details title="About Crash Types">

Crash type describes the mix of road users or vehicles involved in a crash, without assigning fault. The `-Obj` suffix marks a single-party crash type: one road user with no second road user recorded, which for a vehicle is typically a fixed object.

<div class="crash-type-about">

<table border="1" cellspacing="0" cellpadding="8">
    <thead>
      <tr><th>Crash Type</th><th>Abbr.</th><th>Meaning</th></tr>
    </thead>
    <tbody>
      <tr><td>single motor vehicle</td><td>MV-Obj</td><td>One motor vehicle, no other party (e.g., ran off road or struck a fixed object).</td></tr>
      <tr><td>motor vehicle - motor vehicle</td><td>MV-MV</td><td>Two motor vehicles.</td></tr>
      <tr><td>multiple motor vehicles</td><td>&gt;2 MV</td><td>Three or more motor vehicles.</td></tr>
      <tr><td>motor vehicle - pedestrian</td><td>MV-Ped</td><td>A motor vehicle and a pedestrian.</td></tr>
      <tr><td>motor vehicle - bicycle</td><td>MV-Bic</td><td>A motor vehicle and a bicycle.</td></tr>
      <tr><td>motor vehicle - other</td><td>MV-Oth</td><td>A motor vehicle and an "other" road user.</td></tr>
      <tr><td>motor vehicle - motorcycle*</td><td>MV-MC*</td><td>A motor vehicle and a motorcycle.</td></tr>
      <tr><td>motor vehicle - standing scooter*</td><td>MV-SS*</td><td>A motor vehicle and a standing scooter.</td></tr>
      <tr><td>single bicycle</td><td>Bic-Obj</td><td>One bicycle, no other party.</td></tr>
      <tr><td>bicycle - bicycle</td><td>Bic-Bic</td><td>Two bicycles.</td></tr>
      <tr><td>multiple bicycles</td><td>&gt;2 Bic</td><td>Three or more bicycles.</td></tr>
      <tr><td>bicycle - pedestrian</td><td>Bic-Ped</td><td>A bicycle and a pedestrian.</td></tr>
      <tr><td>other - bicycle</td><td>Oth-Bic</td><td>An "other" road user and a bicycle.</td></tr>
      <tr><td>other - pedestrian</td><td>Oth-Ped</td><td>An "other" road user and a pedestrian.</td></tr>
      <tr><td>pedestrian only</td><td>Ped-Obj</td><td>A pedestrian with no other recorded party.</td></tr>
      <tr><td>other</td><td>Oth-Obj</td><td>An "other" road user only (major/minor injury data).</td></tr>
      <tr><td>single motorcycle*</td><td>MC*-Obj</td><td>One motorcycle, no other party.</td></tr>
      <tr><td>single standing scooter*</td><td>SS*-Obj</td><td>One standing scooter, no other party.</td></tr>
      <tr><td>motorcycle* - pedestrian</td><td>MC*-Ped</td><td>A motorcycle and a pedestrian.</td></tr>
      <tr><td>motorcycle* - bicycle</td><td>MC*-Bic</td><td>A motorcycle and a bicycle.</td></tr>
      <tr><td>standing scooter* - pedestrian</td><td>SS*-Ped</td><td>A standing scooter and a pedestrian.</td></tr>
      <tr><td>standing scooter* - bicycle</td><td>SS*-Bic</td><td>A standing scooter and a bicycle.</td></tr>
      <tr><td>multi-party</td><td>MP</td><td>Three or more different road-user types involved.</td></tr>
      <tr><td>unclassified</td><td>Unc</td><td>Could not be classified from the available fields.</td></tr>
    </tbody>
  </table>

</div>

</Details>

<style>
  :global(.crash-type-about th),
  :global(.crash-type-about td) {
    padding: 8px 22px;
  }
</style>
