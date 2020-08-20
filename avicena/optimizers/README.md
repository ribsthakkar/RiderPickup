There is currently only one working Optimizer in Avicena:
* GeneralOptimizer

There is experimental code for the PDWTWOptimizer, but it is still under
development. 

All Optimizers must be classes that extend from BaseOptimizer, and must
implement and conform to the following methods:

* `__init__(self, trips: List[Trip], drivers: List[Driver], name: str, date: str, speed: int, config: Dict[str, Any]) -> None`
* `solve(self, solution_file) ->
Pandas.DataFrame`

Furthermore, all optimizers must fix a seed in their configuration.

## Configuration Glossary
Below is a gloassary of the expected parameters in the
`config/optimizer_config.yaml` file when using Avicena depending on
which optimizer is specified in `config/app_config.yaml`.

### ALL OPTIMIZERS
| Parameter           	| Default Value          	| Comments                                                                                                                                                                                                                        	|
|---------------------	|------------------------	|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------	|
| seed         	| 1000                   	| Increase if more than 1000 trips for the day.  Otherwise model will automatically adjust for correct number of trips. If set to less than number of trips in file then it will only run the model on the first subset of trips. 	|


### GeneralOptimizer
| Parameter           	| Default Value          	| Comments                                                                                                                                                                                                                        	|
|---------------------	|------------------------	|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------	|
| max_trips         	| 1000                   	| Increase if more than 1000 trips for the day.  Otherwise model will automatically adjust for correct number of trips. If set to less than number of trips in file then it will only run the model on the first subset of trips. 	|
| max_drivers         	| 10                      	| Increase if more than 4 drivers. Otherwise it will use the first subset of drivers.                                                                                                                                             	|
| driver_capacity          	| 2.5                    	| How much space is in each driver's vehicle. (W trips use 1.5 units space A trips use 1 unit of space)                                                                                                                           	|
| early_day_time        | 4:30                  	| Earliest time a driver who isn't on an early day can be assigned to start a trip                                                                                                                                                            	|
| early_pickup_window 	| 45      	| The amount of time in minutes before the scheduled pickup can a patient be picked up.                                                                                                                                                      	|
| late_pickup_window  	| 15     	| The amount of time in minutes after the scheduled pickup can a patient be picked up.                                                                                                                                                       	|
| early_drop_window   	| 60      	| (Unused) The amount of time in minutes before the scheduled dropoff can a patient be dropped.                                                                                                                                              	|
| late_drop_window    	| 5 	| The amount of time in minutes after the scheduled dropoff can a patient be dropped.                                                                                                                                                        	|
| route_limit         	| 900          | (Unused) Limit on amount of time in minutes between earliest pickup and latest dropoff.                                                                                                                                                             	|
| route_limit_penalty   | 1000                 	    | Minutes penalty per fraction of day for the time of driver's route                                                                                                                                                            	|
| merge_penalty       	| 1000                   	| Minutes penalty per hour time difference for additional time between merge trip legs                                                                                                                                        	|
| revenue_penalty     	| 250                    	| Minutes penalty per dollar difference in maximum revenue and minimum revenue                                                                                                                                                            	|
| wheelchair_penalty    | 150                    	| Minutes penalty per number difference in maximum number of wheel chair trips assigned to a wheelchair driver and minimum number of trips assigned                                                                                                                                                            	|
| stage1_time         	| 600                    	| Time in seconds to run Stage 1 of Solver                                                                                                                                                                                        	|
| stage1_gap          	| 0.05                   	| Target MIP Gap for Stage 1                                                                                                                                                                                                      	|
| stage2_time         	| 600                    	| Time in seconds to run Stage 2 of Solver                                                                                                                                                                                        	|
| stage2_gap          	| 0.05                   	| Target MIP Gap for Stage 2                                                                                                                                                                                                      	|
| max_retries          	| 3                   	| Number of times to attempt to solve if no solution found within the solve time parameters                                                                                                                                                                                                    	|

All time windows and penalties are interpreted in minutes. The objective
of the GeneralOptimizer is to reduce the overall time minutes traveled
by the drivers plus the minute penalties that applied for various
aspects of fairness.

## PDWTWOptimizer
The PDWTW Optimizer is not been fully implemented in a non-experimental
mode. 