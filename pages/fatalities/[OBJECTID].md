---
queries:
   - fatality: fatality.sql
---

# <Value data={Tittle} column=ADDRESS/> - <Value data={Tittle} column=Date/> hrs.

```sql fatality_with_link
select *, '/fatalities/' || OBJECTID as link
from ${fatality}
```

```sql unique_hin
select 
    GIS_ID,
    ROUTENAME
from hin.hin
group by all
```

```sql columns
  SELECT column_name
  FROM information_schema.columns
  WHERE table_schema = 'crashes'
    AND table_name = 'crashes';
```

```sql Tittle
  SELECT 
    ADDRESS,
    CONCAT(
          LPAD(EXTRACT(MONTH FROM REPORTDATE)::TEXT, 2, '0'), '/', 
          LPAD(EXTRACT(DAY FROM REPORTDATE)::TEXT, 2, '0'), '/', 
          RIGHT(EXTRACT(YEAR FROM REPORTDATE)::TEXT, 2), ' ', 
          LPAD(EXTRACT(HOUR FROM REPORTDATE)::TEXT, 2, '0'), ':', 
          LPAD(EXTRACT(MINUTE FROM REPORTDATE)::TEXT, 2, '0')
    ) AS Date
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'
```

```sql pivot_table
  SELECT 
    'Date' AS column_name, 
      CONCAT(
          LPAD(EXTRACT(MONTH FROM REPORTDATE)::TEXT, 2, '0'), '/', 
          LPAD(EXTRACT(DAY FROM REPORTDATE)::TEXT, 2, '0'), '/', 
          RIGHT(EXTRACT(YEAR FROM REPORTDATE)::TEXT, 2), ' ', 
          LPAD(EXTRACT(HOUR FROM REPORTDATE)::TEXT, 2, '0'), ':', 
          LPAD(EXTRACT(MINUTE FROM REPORTDATE)::TEXT, 2, '0')
      ) AS column_value
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Road User', replace(MODE, '*', '') AS MODE
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Age', 
    CASE
        WHEN CAST(AGE AS INTEGER) = 120 THEN '-'
        ELSE CAST(CAST(AGE AS INTEGER) AS VARCHAR)
    END AS AGE
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'CCN', CCN::TEXT
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Address', ADDRESS
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Ward', WARD
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Striking Vehicle', StrinkingVehicle
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Second Striking Vehicle/Object', SecondStrikingVehicleObject
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Site Visit Status', SiteVisitStatus
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Factors Discussed at Site Visit', FactorsDiscussedAtSiteVisit
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

UNION ALL

  SELECT 'Actions Planned and Completed', ActionsPlannedAndCompleted
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'

  UNION ALL

  SELECT 'Actions Under Consideration', ActionsUnderConsideration
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}';
```

```sql incidents
  SELECT
      MODE,
      LATITUDE,
      LONGITUDE
  FROM crashes.crashes
  WHERE OBJECTID = '${params.OBJECTID}'
  GROUP BY all
```

```sql mode_selection
    SELECT
        STRING_AGG(DISTINCT MODE, ', ' ORDER BY MODE ASC) AS MODE_SELECTION
    FROM
        crashes.crashes
    WHERE
        MODE IN ${inputs.multi_mode_dd.value};
```

<Grid cols=2>
    <Group>
      <BaseMap
        height=445
        title="Fatality Location"
        startingZoom=17
        >
        <Points data={incidents} lat=LATITUDE long=LONGITUDE value=MODE pointName=MODE colorPalette={['#ff5a53']}/>
        <Areas data={unique_hin} geoJsonUrl='https://raw.githubusercontent.com/rafaelmorenoco/Crash-Injury-Dashboard-Frontend/main/static/High_Injury_Network.geojson' geoId=GIS_ID areaCol=GIS_ID borderColor=#9d00ff color=#1C00ff00/ ignoreZoom=true 
        tooltip={[
          {id: 'ROUTENAME'}
        ]}
        />
      </BaseMap>
      <Note>
        The purple lines represent DC's High Injury Network
      </Note>
    </Group>
    <Group>
      <DataTable data={pivot_table} rows=all wrapTitles=true rowShading=true>
        <Column id=column_name title="Fatality Details" wrap=true/>
        <Column id=column_value title=" " wrap=true/>
      </DataTable>
    </Group>
</Grid>
