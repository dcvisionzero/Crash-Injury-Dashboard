---
---

# <Value data={intx_info} column=INTERSECTION_NAME/>

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

<Value data={intx_info} column=INTERSECTION_NAME/>

<DataTable data={crashes_fatal}/>
<DataTable data={crashes_major}/>
<DataTable data={crashes_minor}/>