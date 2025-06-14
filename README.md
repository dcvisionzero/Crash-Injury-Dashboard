# DC Vision Zero Traffic Fatalities and Injury Crashes Dashboard Frontend

## About this dashboard

The Fatal and Injury Crashes Dashboard can be used by the public to know more about injuries or fatalities resulting from crashes in the District of Columbia (DC).

## About the data

The data comes from the tables **Crashes in DC** and **Crash Details** from DC's Open Data portal (see links below), as well as internal tracking of traffic fatalities by the District Department of Transportation (DDOT) and the Metropolitan Police Department (MPD).

### The data is filtered to:
- Only keep records of crashes that occurred on or after 1/1/2017.
- Only keep records of crashes that involved a fatality, a major injury, or a minor injury. See the "Injury Crashes" section below.

All counts on this page are for **persons injured**, not the number of crashes. For example, one crash may involve injuries to three persons; in that case, all three persons will be counted in all the charts and indicators on this dashboard.

Injury Crashes are defined based on information collected at the scene of the crash. Below are examples of the different types of injury categories.

### Injury Category:
- **Major Injury:** Unconsciousness; Apparent Broken Bones; Concussion; Gunshot (non-fatal); Severe Laceration; Other Major Injury.
- **Minor Injury:** Abrasions; Minor Cuts; Discomfort; Bleeding; Swelling; Pain; Apparent Minor Injury; Burns-minor; Smoke Inhalation; Bruises.

While the injury crashes shown on this map include any type of injury, summaries of injuries submitted for federal reports only include those that fall under the [Model Minimum Uniform Crash Criteria](https://www.nhtsa.gov/mmucc-1), which do not include "discomfort" and "pain." 

**Note:** Data definitions of injury categories may differ due to source (e.g., federal rules) and may change over time, which may cause numbers to vary among data sources.

All data comes from MPD.

- [Crashes in DC (Open Data)](https://opendata.dc.gov/datasets/crashes-in-dc)
- [Crash Details (Open Data)](https://opendata.dc.gov/datasets/crash-details-table)

## About Evidence

This dashboard was developed using Evidence, a modern open-source framework designed for creating data-driven dashboards and reports. Evidence uses Markdown and SQL queries to build dashboards, allowing for an efficient and straightforward setup.

For more details on installing Evidence and building your first dashboard, check out the following resources:

- [Install Evidence](https://docs.evidence.dev/install-evidence/)
- [Build Your First App](https://docs.evidence.dev/build-your-first-app/)
