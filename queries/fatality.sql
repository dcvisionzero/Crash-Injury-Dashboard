select 
    OBJECTID
from crashes.crashes
where SEVERITY = 'Fatal'
group by all