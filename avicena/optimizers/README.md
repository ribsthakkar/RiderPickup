There is currently only one working Optimizer in Avicena:
* GeneralOptimizer

There is experimental code for the PDWTWOptimizer, but it is still under
development. 

All Optimizers must be classes that extend from BaseOptimizer, and must
implement the `solve(self, solution_file) -> Pandas.DataFrame` method.

## Configuration Glossary
Below is a gloassary of the expected parameters in the
`config/optimizer_config.yaml` file when using Avicena depending on
which optimizer is specified in `config/app_config.yaml`.

### GeneralOptimizer
| Parameter           	| Default Value          	| Comments                                                                                                                                                                                                                        	|
|---------------------	|------------------------	|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------	|
| TRIPS_TO_DO         	| 1000                   	| Increase if more than 1000 trips for the day.  Otherwise model will automatically adjust for correct number of trips. If set to less than number of trips in file then it will only run the model on the first subset of trips. 	|
| NUM_DRIVERS         	| 4                      	| Increase if more than 4 drivers. Otherwise it will use the first subset of drivers.                                                                                                                                             	|
| EARLY_PICKUP_WINDOW 	| 0.03125 (45 Mins)      	| The amount of time before the scheduled pickup can a patient be picked up.                                                                                                                                                      	|
| LATE_PICKUP_WINDOW  	| 0.03125 (45 Mins)      	| The amount of time after the scheduled pickup can a patient be picked up.                                                                                                                                                       	|
| EARLY_DROP_WINDOW   	| 0.04166 (1 hour)       	| (Unused) The amount of time before the scheduled dropoff can a patient be dropped.                                                                                                                                              	|
| LATE_DROP_WINDOW    	| 0.00347222222 (5 mins) 	| The amount of time after the scheduled dropoff can a patient be dropped.                                                                                                                                                        	|
| DRIVER_CAP          	| 2.5                    	| How much space is in each driver's vehicle. (W trips use 1.5 units space A trips use 1 unit of space)                                                                                                                           	|
| ROUTE_LIMIT         	| 0.625 (15 hours)          | (Unused) Limit on amount of time between earliest pickup and latest dropoff.                                                                                                                                                             	|
| ROUTE_LIMIT_PENALTY   | 1000                 	    | Penalty per fraction of day for the time of driver's route                                                                                                                                                            	|
| EARLY_DAY_TIME        | 0.1875                  	| Earliest time a driver who isn't on an early day can be assigned to start a trip                                                                                                                                                            	|
| MERGE_PENALTY       	| 1000                   	| Penalty per hour time difference for additional time between merge trip legs                                                                                                                                        	|
| REVENUE_PENALTY     	| 250                    	| Penalty per dollar difference in maximum revenue and minimum revenue                                                                                                                                                            	|
| WHEELCHAIR_PENALTY    | 150                    	| Penalty difference in maximum number of wheel chair trips assigned to a wheelchair driver and minimum number of trips assigned                                                                                                                                                            	|
| MODEL_NAME          	| PDWTW                  	| Internal Name for Model                                                                                                                                                                                                         	|
| STAGE1_TIME         	| 600                    	| Time in seconds to run Stage 1 of Solver                                                                                                                                                                                        	|
| STAGE1_GAP          	| 0.05                   	| Target MIP Gap for Stage 1                                                                                                                                                                                                      	|
| STAGE2_TIME         	| 600                    	| Time in seconds to run Stage 2 of Solver                                                                                                                                                                                        	|
| STAGE2_GAP          	| 0.05                   	| Target MIP Gap for Stage 2                                                                                                                                                                                                      	|

## PDWTWOptimizer
The PDWTW Optimizer is not been fully implemented in a non-experimental
mode. 