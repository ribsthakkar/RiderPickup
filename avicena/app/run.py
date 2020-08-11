from avicena.parsers.LogistiCareParser import pdf2csv
from avicena.util.TimeWindows import ONE_MINUTE

config = {'merge_addresses':[], 'merge_window': ONE_MINUTE, 'geo_key':'78bdef6c2b254abaa78c55640925d3db'}
pdf2csv('temp.pdf', '../../input/rev_table.csv','./', config)