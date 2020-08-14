# Avicena
### Problem Description
Avicena is an application that solves the patient pickup and dropoff
problem. Below is a rough description of the problem's attributes:
* There are some number of patients that must be transported from one
  location to one or more other locations through out the day, and there
  are some number of drivers available to complete the trips.
* For each leg of their trip a patient must be picked up from their
  starting location within a time window of the scheduled pickup time,
  and they must be dropped off no later than a short time interval after
  the scheduled dropoff time.
* Some trips known as "merge" trips mean that a patient has two back to
  back trips. These trips often indicate short visits to the pharmacy to
  pick up prescriptions. Therefore, the same driver must complete both
  legs.
* Some patients require wheelchair support in their vehicles, which only
  a subset of the drivers can provide. Drivers can only transport
  patients for which their vehicle is equipped.
* All drivers should receive approximately the same compensation, and
  all wheelchair drivers should receive a approximately the same number
  of wheelchair bound trips.
* Drivers are split into two groups. A group that begins before a
  designated "early day time" on Mondays, Wednesdays, and Fridays and
  another group that begins before the "early day time" on Tuesdays,
  Thursdays, and Saturdays. If there is a day where all drivers are from
  the same group, a part of the drivers will be randomly selected to
  temporarily be part of the second group.
* The goal is to minimize the total amount of time spent traveling on
  the road while ensuring to meet all of driver fairness requirements
  and trip scheduling requirements.
  
In general, the patient pickup and dropoff problem is a special case of
the Vehicle Routing with Time Windows problem. However, here we have
additional constraints that take into account the preferences and
fairness attributes for the drivers.

### Prepare Environment
1. Make sure IBM CPLEX Solver is installed. Use the following link:
   [CPLEX](https://www.ibm.com/support/knowledgecenter/SSSA5P_12.7.1/ilog.odms.cplex.help/CPLEX/GettingStarted/topics/set_up/setup_synopsis.html)
   Follow the instructions on the website to prepare the CPLEX
   Installation with usage for Python. Make sure you do not re-install
   CPLEX using PIP or it will overwrite the licensed version from IBM.
   However, if you are unable to obtain a CPLEX license, PIP will
   install a community version of CPLEX. (Warning: the community version
   will likely only support on the order of 2 drivers and 7-10 trips)
2. Clone this repository: 
```
git clone https://github.com/ribsthakkar/RiderPickup
```
3. Setup virtual environment 
```
cd RiderPickup/
python -m venv venv/
source venv/bin/activate
export PYTHONPATH="$PYTHONPATH:<path_to_current_directory>"
```
4. Install Requirements:
```
pip install -r requirements.txt
```

### Setup
#### Application Configuration
`config/sample_app_config.yaml` provides an example configuration YAML.
A configuration file of this format must be placed at the path
`config/app_config.yaml` to run the application. Below is a glossary of
the application configuration parameters.

In addition to the `app_config.yaml`, you will need to provide a
`config/optimizer_config.yaml`. This configuration file provides the
configuration for optimizer model (specified in the `app_config.yaml`) 
used to solve the problem. Below is a list of supported optimizers and
their configuration definitions.

#### Database Setup (optional)
The command-line application supports interfacing with a PostgreSQL
database. We assume you have a PostgreSQL server hosted somewhere with a
configured username and login. If in the database section in your
`config/app_config.yaml` the "enabled" flag is set to True, Avicena will
poll inputs such as the merge address table, the revenue rates table,
and the drivers table from the database. Therefore it is assumed that
the data is already in your database. Follow the instructions below to
setup the database

The database is versioned by alembic. In order to generate the initial
tables in your database, make a copy of `sample_alembic.ini` in the same
directory and name it `alembic.ini`. Modify the line in the file
starting with `sqlalchemy.url = <fake_url>` and replace `<fake_url>` the
URL to connect to your database. Be sure that the URL of the database
will be the same one used in the `app_config.yaml`.
 
 Run the command: 
 ```
 alembic upgrade head
 ```
 After that, the database tables should be created.
 
Once the tables are created, the *revenue_rate*, *merge_details*, and
*driver* tables must be populated with data. In order to help populate
your database with the required inputs, a script
`avicena/prepare_database.py` is provided. It can be run as follows:
```
usage: prepare_database.py [-h] -r REVENUE_TABLE_FILE -m MERGE_DETAILS_FILE -d
                           DRIVER_DETAILS_FILE

Populate Database with Base Information needed including Revenue Table, Merge
Address Details, and Driver Details.

optional arguments:
  -h, --help            show this help message and exit

required arguments:
  -r REVENUE_TABLE_FILE, --revenue-table-csv REVENUE_TABLE_FILE
                        Path to revenue table CSV
  -m MERGE_DETAILS_FILE, --merge-details-csv MERGE_DETAILS_FILE
                        Path to merge details CSV
  -d DRIVER_DETAILS_FILE, --driver-details-csv DRIVER_DETAILS_FILE
                        Path to driver details CSV

```
The three input CSV files must follow the same format and header as
shown by `sample_data/sample_rev_table.csv`,
`sample_data/sample_merge_details.csv`, and
`sample_data/sample_drivers.csv`. 
 

### How to Run
