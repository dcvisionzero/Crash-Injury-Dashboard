---
queries:
   - age_range: age_range.sql
---

<script>
  const csv = (v, fallback) => (v ? v.split(',').map((s) => s.trim()) : fallback);

  $: qp      = $page.url.searchParams;
  $: dSev    = csv(qp.get('severity'), ['Fatal', 'Major', 'Minor']);
  $: dMode   = csv(qp.get('mode'), null);
  $: dMinAge = qp.get('min_age') ? Number(qp.get('min_age')) : 0;
  $: dMaxAge = qp.get('max_age') ? Number(qp.get('max_age')) : 120;
  $: dStart  = qp.get('start') ?? '2017-01-01';
  $: dEnd    = qp.get('end');
</script>

# <Value data={intx_info} column=INTERSECTION_NAME/>

```sql unique_mode
select MODE from crashes.crashes group by 1
```

```sql unique_severity
select SEVERITY from crashes.crashes group by 1
```

```sql intx_info
SELECT
    INTERSECTIONKEY,
    canonical_name AS INTERSECTION_NAME
FROM intersections.intersections_unique
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
```

```sql crashes_at
SELECT
    REPORTDATE,
    MODE,
    SEVERITY,
    LATITUDE,
    LONGITUDE
FROM crashes.crashes
WHERE INTERSECTIONKEY = '${params.INTERSECTIONKEY}'
    AND SEVERITY IN ${inputs.multi_severity.value}
    AND MODE IN ${inputs.multi_mode_dd.value}
    AND REPORTDATE BETWEEN ('${inputs.date_range.start}'::DATE) AND (('${inputs.date_range.end}'::DATE) + INTERVAL '1 day')
    AND AGE BETWEEN ${inputs.min_age.value} AND (CASE WHEN ${inputs.min_age.value} <> 0 AND ${inputs.max_age.value} = 120 THEN 119 ELSE ${inputs.max_age.value} END)
ORDER BY REPORTDATE DESC
```

```sql crashes_fatal
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Fatal'
```

```sql crashes_major
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Major'
```

```sql crashes_minor
SELECT * FROM ${crashes_at} WHERE SEVERITY = 'Minor'
```

<DateRange
start={dStart}
end={dEnd ? dEnd : undefined}
name="date_range"
presetRanges={['Last 30 Days', 'Last 12 Months', 'Year to Today', 'Last Year', 'All Time']}
defaultValue="Year to Today"
/>

<Dropdown data={unique_severity} name="multi_severity" value="SEVERITY" title="Severity" multiple={true} defaultValue={dSev}/>

<Dropdown data={unique_mode} name=multi_mode_dd value=MODE title="Road User" multiple=true defaultValue={dMode ?? undefined} selectAllByDefault={dMode === null}/>

<Dropdown data={age_range} name=min_age value=age_int title="Min Age" defaultValue={dMinAge}/>

<Dropdown data={age_range} name="max_age" value=age_int title="Max Age" order="age_int desc" defaultValue={dMaxAge}/>

<Value data={intx_info} column=INTERSECTION_NAME/>

<DataTable data={crashes_fatal}/>
<DataTable data={crashes_major}/>
<DataTable data={crashes_minor}/>