This is the repository for running the patient pickup and dropoff problem.
## Prepare Environment
Requires Python 3.6+ and IBM CPLEX 12+
1. Make sure IBM CPLEX Solver is installed.
Use the following link: [CPLEX](https://www.ibm.com/support/knowledgecenter/SSSA5P_12.7.1/ilog.odms.cplex.help/CPLEX/GettingStarted/topics/set_up/setup_synopsis.html)
Follow the instructions on the website to prepare the CPLEX Installation with usage for Python.
2. Clone this repository: 
```
git clone https://github.com/ribsthakkar/RiderPickup
```
3. Install Requirements:
```
cd RiderPickup/
pip install -r requirements.txt
```
4. Get an OpenCage Geocoder API Key
Visit [OpenCage Geocoder](https://opencagedata.com/api) to retrieve an API key and store it in a file

## How to Use
Run Using Python and providing arguments
```
usage: python run.py [-h] [-s S] -r R -t T -d D -k K -o O -v V

Run the Generalized Optimizer with given files

optional arguments:
  -h, --help         show this help message and exit
  -s S, --speed S    Speed in MPH to use for time calculations

required named args:
  -r R, --rev R      Path to CSV with Revenue Table
  -t T, --trips T    Path to CSV Trips File
  -d D, --drivers D  Path to CSV Driver Details File
  -k K, --key K      Path to File With OpenCage GeoCode API Key
  -o O, --output O   File To Store Assignment CSV
  -v V, --vis V      File To Store Assignment HTML Visualization

```
## Parameter Tuning
**Not reccommended to change these values for day to day use**

Below is a list of tunable optimization parameters. These parameters
are on line 54 of the `Assumptions.py`
Some parameters are currently unused by the provided implementation.

| Parameter           	| Default Value          	| Comments                                                                                                                                                                                                                        	|
|---------------------	|------------------------	|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------	|
| TRIPS_TO_DO         	| 1000                   	| Increase if more than 1000 trips for the day.  Otherwise model will automatically adjust for correct number of trips. If set to less than number of trips in file then it will only run the model on the first subset of trips. 	|
| NUM_DRIVERS         	| 4                      	| Increase if more than 4 drivers. Otherwise it will use the first subset of drivers.                                                                                                                                             	|
| EARLY_PICKUP_WINDOW 	| 0.03125 (45 Mins)      	| The amount of time before the scheduled pickup can a patient be picked up.                                                                                                                                                      	|
| LATE_PICKUP_WINDOW  	| 0.03125 (45 Mins)      	| The amount of time after the scheduled pickup can a patient be picked up.                                                                                                                                                       	|
| EARLY_DROP_WINDOW   	| 0.04166 (1 hour)       	| (Unused) The amount of time before the scheduled dropoff can a patient be dropped.                                                                                                                                              	|
| LATE_DROP_WINDOW    	| 0.00347222222 (5 mins) 	| The amount of time after the scheduled dropoff can a patient be dropped.                                                                                                                                                        	|
| DRIVER_CAP          	| 2.5                    	| How much space is in each driver's vehicle. (W trips use 1.5 units space A trips use 1 unit of space)                                                                                                                           	|
| ROUTE_LIMIT         	| 0.625                  	| Limit on amount of time between earliest pickup and latest dropoff.                                                                                                                                                             	|
| MERGE_PENALTY       	| 1000                   	| (unused) penalty on model for not satisfying merge trips. Not integrated in model yet.                                                                                                                                          	|
| REVENUE_PENALTY     	| 250                    	| Penalty per dollar difference in maximum revenue and minimum revenue                                                                                                                                                            	|
| MODEL_NAME          	| PDWTW                  	| Internal Name for Model                                                                                                                                                                                                         	|
| STAGE1_TIME         	| 900                    	| Time in seconds to run Stage 1 of Solver                                                                                                                                                                                        	|
| STAGE1_GAP          	| 0.05                   	| Target MIP Gap for Stage 1                                                                                                                                                                                                      	|
| STAGE2_TIME         	| 900                    	| Time in seconds to run Stage 2 of Solver                                                                                                                                                                                        	|
| STAGE2_GAP          	| 0.05                   	| Target MIP Gap for Stage 2                                                                                                                                                                                                      	|                                                                                                                                                      	|