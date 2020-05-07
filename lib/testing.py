from lib.GeneralizedOptimizer import GeneralOptimizer
from lib.PDWTWOptimizer import PDWTWOptimizer
from lib.Preprocessor import TripPreprocess as tp
from datetime import datetime
from lib.Assumptions import preprocess_assumptions, opt_params
from lib.constants import keys

keyFile = open('geocode.key')
keys['geo_key'] = keyFile.readline().rstrip()


rev_table = tp.load_revenue_table('../Data/rev_table.csv')
trips = tp.prepare_and_load_trips('../Data/in_trips_010220.csv',rev_table, preprocess_assumptions)
# trips = tp.load_trips('calc_trips.csv')
drivers = tp.load_drivers('../Data/in_drivers.csv')
# optimizer = PDWTWOptimizer(trips, drivers, opt_params)
# outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
# optimizer.solve(outfile)
# optimizer.visualize(outfile, 'vis-010220.html')

# trips2 = tp.prepare_and_load_trips('../Data/in_trips_022620.csv',rev_table, preprocess_assumptions)
# optimizer2 = PDWTWOptimizer(trips2, drivers, opt_params)
# outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
# optimizer2.solve(outfile)
# optimizer2.visualize(outfile, 'vis-022620.html')

optimizer = GeneralOptimizer(trips, drivers, opt_params)
outfile = 'output/gen_final_output' + str(datetime.now()) + '.csv'
optimizer.solve(outfile)
optimizer.visualize(outfile, 'vis-010220-genopt.html')

# trips2 = tp.prepare_and_load_trips('../Data/in_trips_022620.csv',rev_table, preprocess_assumptions)
# optimizer2 = GeneralOptimizer(trips2, drivers, opt_params)
# outfile = 'output/gen_final_output' + str(datetime.now()) + '.csv'
# optimizer2.solve(outfile)
# optimizer2.visualize(outfile, 'vis-022620-genopt.html')