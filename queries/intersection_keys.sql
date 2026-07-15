select INTERSECTIONKEY
from crashes.crashes
where INTERSECTIONKEY is not null
group by all;