"""Pure calculation layer for CHEP pallet decision prototype.

Financial calculations are translated from TCOv3.xlsx, Calculation rows 6:35.
Emissions equations are translated from Pallet_Customer_Sustainability_V2.xlsx,
Calculations rows 6:8. Inputs remain screening assumptions until validated.

No external requests, no file I/O, no Streamlit dependency in this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Mapping, Any


@dataclass
class CostResult:
    annual: float
    per_trip: float
    lines: Dict[str, float]
    blocks: Dict[str, float]


@dataclass
class CarbonResult:
    per_trip: float
    annual_tonnes: float
    components: Dict[str, float]
    timber_kg_per_trip: float


WHITE_LINES = {
    'Loss replacements': 'Direct costs',
    'Repairs': 'Direct costs',
    'Scrap replacements': 'Direct costs',
    'Haulier swap fee': 'Logistics',
    'Extra collections': 'Logistics',
    'Sorting and inspection': 'Labour & admin',
    'Voucher administration': 'Labour & admin',
    'Compliance reporting': 'Compliance',
    'Automation downtime': 'Risk',
    'Rejected loads': 'Risk',
    'Pallet shortages': 'Risk',
    'Voucher non-redemption': 'Hidden costs',
    'Empty pallet storage': 'Hidden costs',
}
POOL_LINES = {
    'Rental fee': 'Direct costs',
    'Daily rental': 'Direct costs',
    'Lost-pallet charges': 'Direct costs',
    'Receiving inspection': 'Labour & admin',
    'Compliance reporting': 'Compliance',
    'Automation downtime': 'Risk',
    'Rejected loads': 'Risk',
    'Pallet shortages': 'Risk',
    'Empty pallet storage': 'Hidden costs',
}


def result_from_lines(lines: Dict[str, float], categories: Dict[str, str], movements: float) -> CostResult:
    if movements <= 0:
        raise ValueError('Annual loaded movements must be greater than zero.')
    blocks = {}
    for name, amount in lines.items():
        category = categories[name]
        blocks[category] = blocks.get(category, 0.0) + amount
    total = sum(lines.values())
    return CostResult(total, total / movements, lines, blocks)


def bottom_up_tco(a: Mapping[str, float]) -> Dict[str, CostResult]:
    """Exact numeric translation of uploaded TCOv3's two-option cost lines."""
    n = float(a['annual_movements'])
    if n <= 0 or a['pallets_per_truck'] <= 0:
        raise ValueError('Annual movements and pallets per truck must be positive.')
    epal_price = a['new_pallet_price'] * (1.0 + a['timber_price_change'])
    labour = a['labour_per_hour']
    salary = a['admin_salary']
    w = {
        'Loss replacements': n * a['white_loss_rate'] * epal_price,
        'Repairs': n * a['white_repair_rate'] * a['repair_cost'],
        'Scrap replacements': n * a['white_scrap_rate'] * epal_price,
        'Haulier swap fee': n * a['white_swap_fee'],
        'Extra collections': n * a['white_extra_collection_rate'] * 2.0 * a['white_collection_km_oneway'] * a['truck_cost_per_km'] / a['pallets_per_truck'],
        'Sorting and inspection': n * a['white_sort_minutes'] / 60 * labour,
        'Voucher administration': a['white_voucher_admin_fte'] * salary,
        'Compliance reporting': a['white_compliance_fte'] * salary,
        'Automation downtime': a['white_downtime_hours'] * a['downtime_white_per_hour'],
        'Rejected loads': n * a['white_rejection_rate'] * a['rejection_white_cost'],
        'Pallet shortages': a['white_shortage_days'] * a['shortage_cost_per_day'],
        'Voucher non-redemption': n * a['white_voucher_share'] * a['white_unpaid_voucher_rate'] * epal_price,
        'Empty pallet storage': a['white_storage_cost'],
    }
    p = {
        'Rental fee': n * a['pool_rental_per_trip'],
        'Daily rental': n * a['cycle_days'] * a['pool_rental_per_day'],
        'Lost-pallet charges': n * a['pool_loss_rate'] * a['pool_loss_charge'],
        'Receiving inspection': n * a['pool_inspection_minutes'] / 60 * labour,
        'Compliance reporting': a['pool_compliance_fte'] * salary,
        'Automation downtime': a['pool_downtime_hours'] * (a['downtime_pool_per_hour'] if a['downtime_pool_per_hour'] else a['downtime_white_per_hour']),
        'Rejected loads': n * a['pool_rejection_rate'] * (a['rejection_pool_cost'] if a['rejection_pool_cost'] else a['rejection_white_cost']),
        'Pallet shortages': a['pool_shortage_days'] * a['shortage_cost_per_day'],
        'Empty pallet storage': a['pool_storage_cost'],
    }
    # The source workbook sets both working-capital amounts to zero. Preserve that
    # exclusion and disclose it rather than silently estimating its value.
    return {
        'Current white exchange': result_from_lines(w, WHITE_LINES, n),
        'CHEP pooling': result_from_lines(p, POOL_LINES, n),
    }


def sponsor_tco(movements: float, sponsor_white: float, sponsor_pool: float, sponsor_movements: float) -> Dict[str, CostResult]:
    """Proportional volume scaling is illustrative: fixed/variable split is unavailable."""
    if movements <= 0 or sponsor_movements <= 0:
        raise ValueError('Annual movements must be positive.')
    factor = movements / sponsor_movements
    result = {}
    for name, amount in [('Current white exchange', sponsor_white), ('CHEP pooling', sponsor_pool)]:
        result[name] = result_from_lines({'Supplied sponsor baseline': amount * factor}, {'Supplied sponsor baseline': 'Sponsor baseline'}, movements)
    return result


def add_per_trip_cost(base: CostResult, extra_per_trip: float, movements: float) -> CostResult:
    lines = dict(base.lines)
    if extra_per_trip:
        lines['Explicit additional cost (not in baseline)'] = lines.get('Explicit additional cost (not in baseline)', 0.0) + extra_per_trip * movements
    categories = ({**WHITE_LINES, **POOL_LINES, 'Supplied sponsor baseline':'Sponsor baseline', 'Explicit additional cost (not in baseline)':'Scenario adjustments'})
    return result_from_lines(lines, categories, movements)


def improved_white_cost(white: CostResult, movements: float, annual_implementation: float,
                        savings_rates: Mapping[str, float], extra_white_cost: float = 0.0,
                        extra_saving_share: float = 0.0) -> CostResult:
    """Optional, user-proposed interventions; NOT a TCO result from either Excel file.

    Additional per-trip white adjustment already in `white`; only savings are
    applied to that added line and to named source line costs. Rates are [0,1].
    """
    lines = {}
    for key, amount in white.lines.items():
        pct = extra_saving_share if key == 'Explicit additional cost (not in baseline)' else savings_rates.get(key, 0)
        if not (0 <= pct <= 1):
            raise ValueError('Improvement savings rates must be 0–100%.')
        lines[key] = amount * (1 - pct)
    lines['Improvement implementation'] = annual_implementation
    categories = {**WHITE_LINES, **POOL_LINES, 'Supplied sponsor baseline':'Sponsor baseline',
                  'Explicit additional cost (not in baseline)':'Scenario adjustments',
                  'Improvement implementation':'Implementation'}
    return result_from_lines(lines, categories, movements)


def direct_improved_cost(movements: float, annual_cost: float) -> CostResult:
    return result_from_lines({'User-supplied improved TCO':annual_cost}, {'User-supplied improved TCO':'Customer input'}, movements)


def calculate_emissions(shared: Mapping[str, float], data: Mapping[str, float], movements: float) -> CarbonResult:
    """Reproduces sustainability Calculations B:H, excluding outbound loaded freight."""
    loops = data['useful_loops']
    moves_per_loop = shared['movements_per_epd_loop']
    cap = shared['floor_positions'] * data['pallets_per_stack'] * data['utilisation']
    if loops <= 0 or moves_per_loop <= 0 or cap <= 0 or movements <= 0:
        raise ValueError('Lifetime loops, movements/loop, utilisation and capacity must be positive.')
    production = shared['epd_prod_per_loop'] * shared['epd_reference_loops'] / loops / moves_per_loop
    repair = shared['repair_emission_per_repair'] * data['repairs_per_loop'] / moves_per_loop
    end_of_life = shared['epd_eol_per_loop'] * shared['epd_reference_loops'] / loops / moves_per_loop
    transport = data['return_km'] * shared['truck_kg_per_km'] / cap
    timber = (shared['pallet_mass_kg'] * shared['timber_share'] / loops + shared['repair_timber_per_loop'] * data['repairs_per_loop']) / moves_per_loop
    components={'Production allocation': production, 'Repair processing':repair, 'End-of-life allocation':end_of_life, 'Empty return transport': transport}
    total = sum(components.values())
    return CarbonResult(total, total * movements/1000, components, timber)


def cheapest_cost_option(costs: Mapping[str, CostResult], feasibility: Mapping[str, str] | None = None) -> dict:
    """Returns cost ranking only; never asserts an ESG/compliance recommendation."""
    feasibility = feasibility or {}
    eligible = {name:c for name,c in costs.items() if feasibility.get(name) != 'Does not meet requirements'}
    if not eligible:
        return {'status':'No option currently feasible', 'cost_leader':None, 'confidence':'Not established'}
    winner = min(eligible, key=lambda k:eligible[k].annual)
    confidence = 'Only provisional: service/compliance checks incomplete' if any(feasibility.get(k,'Not validated')=='Not validated' for k in eligible) else 'Feasibility checks confirmed by user'
    return {'status':'Cost comparison only','cost_leader':winner,'confidence':confidence}
