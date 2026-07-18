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

<DataTable data={intx_info}/>
