"""Independent numeric parity tests against the original Excel cached values.
Run: python test_model.py
"""
import json
import math
from pathlib import Path
from model import (bottom_up_tco, sponsor_tco, calculate_emissions, direct_improved_cost,
                   add_per_trip_cost, improved_white_cost, cheapest_cost_option)

cfg=json.loads(Path(__file__).with_name('model_defaults.json').read_text())
TCO_EXPECTED={
 'Low complexity':(541050.7515151515,889292.5),
 'Mixed / typical':(966819.7840909092,1099061.3333333335),
 'High complexity':(2179216.523989899,1799365.6666666667),
 'Downside':(1021388.490132576,1106731.9),
}
CO2_EXPECTED={
 'Low complexity':(0.5979892307692307,0.5274017882352942,0.7710661538461538),
 'Mixed / typical':(1.4686376556776557,1.0720721678321679,0.9276595604395604),
 'High complexity':(2.8023420979020974,1.7167705088757397,1.6903913846153844),
}
OPTIONS=['Current white exchange','Improved white exchange','CHEP pooling']
for name,(white,pool) in TCO_EXPECTED.items():
    res=bottom_up_tco(cfg['tco_scenarios'][name])
    assert math.isclose(res['Current white exchange'].annual,white,rel_tol=0,abs_tol=1e-6),(name,'white')
    assert math.isclose(res['CHEP pooling'].annual,pool,rel_tol=0,abs_tol=1e-6),(name,'pool')
for name,expected in CO2_EXPECTED.items():
    for opt,v in zip(OPTIONS,expected):
        x=calculate_emissions(cfg['sustainability_global'],cfg['sustainability_scenarios'][name][opt],265000)
        assert math.isclose(x.per_trip,v,rel_tol=0,abs_tol=1e-11),(name,opt)
sp=sponsor_tco(265000,843003,909439,265000)
assert sp['Current white exchange'].annual==843003
assert sp['CHEP pooling'].annual==909439
plus=add_per_trip_cost(sp['Current white exchange'],.10,265000)
assert math.isclose(plus.annual,869503)
plus2=add_per_trip_cost(plus,.05,265000)
assert math.isclose(plus2.annual,882753)
imp=improved_white_cost(plus,265000,20000,{'Supplied sponsor baseline':.15},.10,.50)
assert math.isclose(imp.annual,843003*.85+265000*.10*.5+20000)
assert cheapest_cost_option({'Current white exchange':sp['Current white exchange'],'CHEP pooling':sp['CHEP pooling']})['cost_leader']=='Current white exchange'
assert cheapest_cost_option({'Current white exchange':sp['Current white exchange'],'CHEP pooling':sp['CHEP pooling']},{'Current white exchange':'Does not meet requirements'})['cost_leader']=='CHEP pooling'
print('PASS: all 4 financial scenarios and 3 carbon scenarios match cached source values.')
print('PASS: sponsor baseline, extra-cost accumulation, improvement estimate and feasibility checks.')
