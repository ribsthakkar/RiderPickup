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

*Note the "." syntax below just indicates that the field after the "."
is a child parameter of the field before the "." See the
`config/sample_app_config.yaml` for proper format.*

|Parameter                             | Type    | Details                                                                                                                                   |
|-----------------------------|---------|-------------------------------------------------------------------------------------------------------------------------------------------|
| database.enabled           | Boolean | True if input data such as revenue table, merge addresses, driver table will come from database. Otherwise it uses CSVs with paths below |
| database.url               | String  | URL to PostgreSQL database. Ignored if database.enabled is False                                                                        |
| geocoder_key               | String  | API Key for geocoding. Currently only support [OpenCage Geocoder](https://opencagedata.com/api)                                     |
| trips_parser               | String  | Parser used to read the incoming trips file. See more [here](./avicena/parsers/README.md)                                                                                   |
| optimizer                   | String  | Model used to calculate and assign trips. See more details below.                                                                                                  |
| seed                        | Integer | Sets the Python random seed.                                                                                                             |
| merge_address_table_path | String  | Path to CSV representation of merge_address_table. Ignored if database.enabled is True.                                              |
| revenue_table_path        | String  | Path to CSV representation of revenue rate. Ignored if database.enabled is True.                                                       |
| driver_table_path         | String  | Path to CSV representation of drivers table. Ignored if database.enabled is True.                                                      |
| output_directory           | String  | Path to directory where the generated files are stored. These include the one or more parsed trips file (depending on parser), the resulting CSV with the solution, and an HTML page that provides a visualization of the solution.                                          |

In addition to the `app_config.yaml`, you will need to provide a
`config/optimizer_config.yaml`. This configuration file provides the
configuration for optimizer model (specified in the `app_config.yaml`)
used to solve the problem. Below is a list of supported optimizers and
their configuration definitions. Samples are also provided in the
`config/` folder.

| Optimizer           	| Configuration Details          	| Comments                                                                                                                                                                                                                        	|
|---------------------	|------------------------	|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------	|
| GeneralOptimizer         	| [Glossary](./avicena/optimizers/README.md#GeneralOptimizer)                   	| Self Developed Formulation to Solve Problem 	|
| PDWTWOptimizer         	|  [Glossary](./avicena/optimizers/README.md#PDWTWOptimizer)                     	| (Not working in non-experimental mode yet) Formulation from following paper with additional fairness constraints integrated [here]()  	|

Finally, the app will need a `log_config.yaml` with details about how
and what kind of logging we expect from the application. Information
about how to setup the log config can be found at Python's *logging*
module [documentation](https://docs.python.org/3/howto/logging.html).
For simplicity, a copy of the `sample_log_config.yaml` will suffice.

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
Avicena is run through the command line by simply following the format
below. If the database is enabled in the application configuration, then
the resulting dispatch "Assignment" and its driver specific solutions
"DriverAssignment", will be stored in the database. In the output
directory you will find any files generated during the model's running.
At the least, they include `parsed_trips.csv` with the basic trip
details standarized and parsed from the original trips file,
`solution.csv` with the final dispatch assignments, `visualization.html`
which provides a visual representation of the final solution. 

```
usage: run.py [-h] [-n NAME] [-s SPEED] [-d DATE] [-t TRIPS_FILE]
              [-i DRIVER_IDS [DRIVER_IDS ...]]

Run the Patient Dispatch Model

optional arguments:
  -h, --help            show this help message and exit

required arguments:
  -n NAME, --name NAME  Name of Model
  -s SPEED, --speed SPEED
                        Assumed Traveling Speed in MPH
  -d DATE, --date DATE  Date in MM-DD-YYYY format
  -t TRIPS_FILE, --trips-file TRIPS_FILE
                        Path to Trips File
  -i DRIVER_IDS [DRIVER_IDS ...], --driver-ids DRIVER_IDS [DRIVER_IDS ...]
                        List of driver IDs separated by spaces

```
