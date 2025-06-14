SELECT
    strftime(LAST_RECORD, '%Y-%m-%d') AS end_date,
    LPAD(CAST(DATE_PART('month', LAST_RECORD) AS VARCHAR), 2, '0') || '/' ||
    LPAD(CAST(DATE_PART('day', LAST_RECORD) AS VARCHAR), 2, '0') || '/' ||
    RIGHT(CAST(DATE_PART('year', LAST_RECORD) AS VARCHAR), 2) || ',' AS latest_record,
    LPAD(CAST(DATE_PART('month', LAST_UPDATE) AS VARCHAR), 2, '0') || '/' ||
    LPAD(CAST(DATE_PART('day', LAST_UPDATE) AS VARCHAR), 2, '0') || '/' ||
    RIGHT(CAST(DATE_PART('year', LAST_UPDATE) AS VARCHAR), 2) || ' at ' ||
    LPAD(CAST(DATE_PART('hour', LAST_UPDATE) AS VARCHAR), 2, '0') || ':' ||
    LPAD(CAST(DATE_PART('minute', LAST_UPDATE) AS VARCHAR), 2, '0') AS latest_update
FROM crashes.crashes
ORDER BY LAST_RECORD DESC
LIMIT 1;
