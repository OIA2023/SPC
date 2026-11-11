"""CHEP Pallet Strategy Advisor — educational Streamlit prototype.

Run: streamlit run app.py
No confidential data is required or collected; all calculations are local to the app.
"""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from model import (bottom_up_tco, sponsor_tco, add_per_trip_cost,
                   improved_white_cost, direct_improved_cost, calculate_emissions,
                   cheapest_cost_option)

st.set_page_config(page_title='Pallet Strategy Advisor | CHEP Case', page_icon='📦', layout='wide', initial_sidebar_state='expanded')

PATH = Path(__file__).with_name('model_defaults.json')
CONFIG = json.loads(PATH.read_text(encoding='utf-8'))
OPTIONS = ['Current white exchange','Improved white exchange','CHEP pooling']
PALETTE = {'Current white exchange':'#64748B', 'Improved white exchange':'#12A594','CHEP pooling':'#2563EB'}

st.markdown('''<style>
.block-container {padding-top:1.5rem; max-width:1250px;}
h1,h2,h3 {letter-spacing:-0.025em;}
div[data-testid="stMetric"] {border:1px solid rgba(140,150,160,.22);padding:12px 16px;border-radius:12px;background:rgba(125,150,170,.055)}
.hero {padding:18px 22px;border:1px solid rgba(128,145,160,.25);border-radius:16px;background:linear-gradient(110deg,rgba(17,105,162,.10),rgba(15,148,133,.045));margin-bottom:20px}
.hero-kicker {font-size:.72rem;text-transform:uppercase;letter-spacing:.15em;font-weight:700;color:#6295ad;margin-bottom:8px}
.hero-title {font-weight:750;font-size:2.1rem;line-height:1.1;letter-spacing:-.04em;margin:0 0 8px 0}
.hero-sub {font-size:.95rem;opacity:.75}
.note {font-size:.86rem;color:#718096}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px}
</style>''',unsafe_allow_html=True)


def eur(v:float, dp:int=0) -> str:
    return f'€{v:,.{dp}f}'


def rate_box(label:str, value:float, key:str, help_:str|None=None, max_pct:float=100) -> float:
    """Render percentages with readable 0–100 values; return decimal fraction."""
    return st.number_input(label,min_value=0.0,max_value=float(max_pct),value=float(value)*100,
                           step=0.5,key=key,format='%.2f',help=help_)/100


def num_box(label:str, value:float, key:str, min_value:float=0.0, step:float=1.0, fmt:str|None=None, help_:str|None=None) -> float:
    kw={'label':label,'min_value':float(min_value),'value':float(value),'step':float(step),'key':key,'help':help_}
    if fmt:kw['format']=fmt
    return st.number_input(**kw)


def cost_chart(costs):
    fig=go.Figure()
    for name in OPTIONS:
        if name in costs:
            fig.add_trace(go.Bar(x=[name],y=[costs[name].annual],name=name,
                marker_color=PALETTE[name],text=[eur(costs[name].annual)],textposition='auto'))
    fig.update_layout(height=355,margin=dict(t=15,l=10,r=15,b=12),showlegend=False,
        yaxis_title='Annual TCO (EUR)',xaxis_title='',plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='rgba(0,0,0,0)')
    return fig


def carbon_chart(carbons):
    fig=go.Figure()
    for name in OPTIONS:
        fig.add_trace(go.Bar(x=[name],y=[carbons[name].annual_tonnes],name=name,
            marker_color=PALETTE[name],text=[f'{carbons[name].annual_tonnes:,.1f} t'],textposition='auto'))
    fig.update_layout(height=355,margin=dict(t=15,l=10,r=15,b=12),showlegend=False,
        yaxis_title='Annual CO₂e (tonnes)',xaxis_title='',plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='rgba(0,0,0,0)')
    return fig


# SIDEBAR — shared customer profile
with st.sidebar:
    st.markdown('### Customer setup')
    scn=st.selectbox('Operating scenario',['Mixed / typical','Low complexity','High complexity','Downside'],
                     help='Downside uses the typical carbon network but a downside TCO scenario.')
    mode=st.radio('Financial reference',['Sponsor starting case','Team bottom-up model'],index=0,
                  help='Sponsor and team model are distinct calculations; do not combine their starting totals.')
    n=int(st.number_input('Loaded pallet movements / year',min_value=1,value=int(CONFIG['sponsor']['annual_movements']),step=5000))
    price=st.number_input('Optional internal carbon value (€/t CO₂e)',min_value=0.0,value=0.0,step=10.0,
                  help='An internal sensitivity only — not a direct cash saving, ETS liability or tax.')
    st.divider()
    st.caption('**Source files**')
    st.caption('TCOv3.xlsx · Pallet_Customer_Sustainability_V2.xlsx')
    st.caption('Inputs are screening estimates until verified with CHEP or a specific customer.')
    st.caption('No account, database connection or customer login required.')

st.markdown('''<div class="hero"><div class="hero-kicker">Supply Chain Pressure Cooker · 2026</div>
<div class="hero-title">Pallet Strategy Advisor</div><div class="hero-sub">
A customer-facing prototype to compare retaining white exchange, improving exchange, and CHEP pooling.
Cost • CO₂e • break-even • operating risk</div></div>''',unsafe_allow_html=True)

st.warning('**Evidence status: preliminary.** CO₂e results are screening estimates, the third option lacks an original annual TCO, and service/regulatory feasibility has not been independently checked.',icon='🧪')

inputs_tab,comparison_tab,sensitivity_tab,method_tab=st.tabs(['🧾 1 · Customer inputs','📊 2 · Results','📈 3 · Sensitivity','📚 4 · Evidence'])

# BASE INPUT OBJECTS — editable copies of the provided values
financial_scn=CONFIG['tco_scenarios'][scn]
financial=dict(financial_scn)
financial['annual_movements']=n
with inputs_tab:
    st.subheader('1. Confirm the customer’s operating assumptions')
    st.caption('Blue or highlighted values in the uploaded workbooks were treated as inputs. Changing them here recalculates the results immediately.')
    st.markdown('#### Financial cost drivers')
    st.caption('These fields power the bottom-up financial model. In sponsor-case mode they are shown for reference, but the sponsor total cannot be reliably decomposed into these cost components.')
    col1,col2,col3=st.columns(3)
    with col1:
        financial['white_loss_rate']=rate_box('White pallet losses (% of trips)',financial['white_loss_rate'],f'loss_{scn}')
        financial['white_voucher_share']=rate_box('Voucher settlements (% of trips)',financial['white_voucher_share'],f'vouchers_{scn}')
        financial['white_unpaid_voucher_rate']=rate_box('Unredeemed vouchers (% of vouchers)',financial['white_unpaid_voucher_rate'],f'unpaid_{scn}')
    with col2:
        financial['white_extra_collection_rate']=rate_box('White extra-collection rate (%)',financial['white_extra_collection_rate'],f'collectionrate_{scn}')
        financial['white_collection_km_oneway']=num_box('Extra white-collection distance (one way, km)',financial['white_collection_km_oneway'],f'collectkm_{scn}',step=10)
        financial['pallets_per_truck']=num_box('Empty white pallets per collection truck',financial['pallets_per_truck'],f'emptycap_{scn}',min_value=1,step=5)
    with col3:
        financial['pool_rental_per_trip']=num_box('CHEP rental fee (€/trip)',financial['pool_rental_per_trip'],f'chepfee_{scn}',step=.05,fmt='%.2f')
        financial['cycle_days']=num_box('Pallet days held (daily rental calculation)',financial['cycle_days'],f'cycledays_{scn}',step=1)
        financial['pool_loss_rate']=rate_box('CHEP charged losses (% of trips)',financial['pool_loss_rate'],f'poolloss_{scn}')
    st.caption('**Source distinction:** These fields alter the team-built TCO, not the sponsor’s €843,003 / €909,439 starting totals.')
    st.markdown('#### Additional cost sensitivities')
    adj1,adj2=st.columns(2)
    with adj1: extra_white = st.number_input('Additional WHITE cost outside the chosen baseline (€/trip)',min_value=0.,value=0.,step=.05,format='%.2f',help='Only enter a cost if you confirm it is not already included in the chosen TCO.')
    with adj2: extra_pool = st.number_input('Additional POOLING cost outside the chosen baseline (€/trip)',min_value=0.,value=0.,step=.05,format='%.2f',help='Only enter a cost if you confirm it is not already included in the chosen TCO.')
    with st.expander('Advanced TCO assumptions (more fields from TCOv3.xlsx)'):
        st.caption('This section preserves the spreadsheet’s remaining inputs. No empirical credibility is implied by their presence in the uploaded workbook.')
        hidden_fields = [
            ('new_pallet_price','New EPAL pallet price (€/pallet)',.1,False),('repair_cost','Repair cost (€/pallet)',.1,False),
            ('labour_per_hour','Warehouse labour (€/hour)',.5,False),('admin_salary','Administrative staff annual cost (€)',100.,False),
            ('truck_cost_per_km','Truck operating cost (€/km)',.1,False),('downtime_white_per_hour','White downtime cost (€/hour)',10.,False),
            ('downtime_pool_per_hour','Pooling downtime cost (€/hour)',10.,False),('rejection_white_cost','White rejection incident cost (€)',5.,False),
            ('rejection_pool_cost','Pooling rejection incident cost (€)',5.,False),('shortage_cost_per_day','Shortage cost per day (€)',100.,False),
            ('timber_price_change','Timber cost change (%)',1.,True),('white_repair_rate','White repair rate (%)',.5,True),
            ('white_scrap_rate','White scrap rate (%)',.5,True),('white_swap_fee','Haulier swap fee (€/trip)',.1,False),
            ('white_sort_minutes','White inspection time (minutes/trip)',.1,False),('white_storage_cost','White empty storage annual cost (€)',100.,False),
            ('white_voucher_admin_fte','White pallet administration FTE',.05,False),('white_compliance_fte','White compliance FTE',.01,False),
            ('white_downtime_hours','White downtime (hours/year)',1.,False),('white_rejection_rate','White rejection rate (%)',.5,True),
            ('white_shortage_days','White shortage days per year',.1,False),('pool_rental_per_day','CHEP daily rental (€/pallet/day)',.005,False),
            ('pool_loss_charge','CHEP lost-pallet charge (€)',1.,False),('pool_inspection_minutes','CHEP receiving inspection (minutes)',.1,False),
            ('pool_storage_cost','CHEP empty storage annual cost (€)',100.,False),('pool_compliance_fte','CHEP compliance FTE',.01,False),
            ('pool_downtime_hours','CHEP downtime (hours/year)',1.,False),('pool_rejection_rate','CHEP rejection rate (%)',.5,True),
            ('pool_shortage_days','CHEP shortage days per year',.1,False),
        ]
        acols=st.columns(3)
        for i,(k,label,step,pct) in enumerate(hidden_fields):
            with acols[i%3]:
                if pct:
                    if k=='timber_price_change':
                        financial[k]=st.number_input(label,min_value=-99.,value=financial[k]*100,step=step,key=f'adv_{k}_{scn}')/100
                    else:financial[k]=rate_box(label,financial[k],f'adv_{k}_{scn}',max_pct=100)
                else:financial[k]=num_box(label,financial[k],f'adv_{k}_{scn}',step=step)

    st.divider()
    st.markdown('#### Improved white exchange — missing financial input')
    st.info('The sustainability workbook calculates improved-white emissions, but **neither uploaded workbook contains an improved-white annual TCO**. Enable a cost estimate here only if your team supplies the missing economics.',icon='ℹ️')
    improved_choice=st.radio('How should improved-white TCO be entered?',[
        'Not yet established — exclude from financial ranking',
        'Enter an improved-white annual TCO directly',
        'Estimate an improvement package (illustrative)'],index=0)
    intervention_cost=0.0; savings_rates={}; direct_annual=None; sponsor_savings=0.0; hidden_saving=0.0
    if improved_choice=='Enter an improved-white annual TCO directly':
        direct_annual=st.number_input('Customer-supported annual improved-white TCO (€)',min_value=0.,value=0.,step=5000.,help='A value of zero means the cost is still missing. Enter a validated or labelled estimate.')
    elif improved_choice.startswith('Estimate an improvement package'):
        intervention_cost=st.number_input('Annual intervention/implementation cost (€)',min_value=0.,value=15000.,step=1000.)
        if mode=='Sponsor starting case':
            sponsor_savings=st.number_input('Assumed current-white cost saving (€/trip)',min_value=0.,value=0.0,step=.05,format='%.2f',help='Do not claim this was calculated in TCOv3; this is a proposed intervention assumption.')
        else:
            st.caption('Choose the proposed reduction in named, already-modelled white-exchange costs:')
            save_fields=[('Loss replacements','Pallet losses'),('Voucher non-redemption','Unpaid vouchers'),
                         ('Extra collections','Extra collections'),('Sorting and inspection','Sorting and inspection'),
                         ('Rejected loads','Rejected pallet incidents'),('Scrap replacements','Scrapped pallets'),
                         ('Voucher administration','Voucher administration')]
            cols=st.columns(2)
            for i,(key,title) in enumerate(save_fields):
                with cols[i%2]:
                    savings_rates[key]=rate_box(f'Improvement in {title}',0.0,f'save_{i}_{scn}')
        hidden_saving=rate_box('Reduction in explicitly added WHITE cost',0.0,f'extra_save_{scn}')

    st.divider()
    st.markdown('#### CO₂e — shared lifecycle screening factors')
    shared=dict(CONFIG['sustainability_global'])
    ecol1,ecol2,ecol3=st.columns(3)
    with ecol1:
        shared['truck_kg_per_km']=num_box('Truck emission factor (kg CO₂e/vehicle-km)',shared['truck_kg_per_km'],'eftruck',step=.05,fmt='%.3f')
        shared['floor_positions']=num_box('Floor pallet positions',shared['floor_positions'],'floors',min_value=1,step=1)
    with ecol2:
        shared['epd_prod_per_loop']=num_box('EPD production proxy (kg CO₂e/loop)',shared['epd_prod_per_loop'],'epdprod',step=.01,fmt='%.4f')
        shared['repair_emission_per_repair']=num_box('Repair-processing proxy (kg CO₂e/repair)',shared['repair_emission_per_repair'],'repairfactor',step=.05,fmt='%.3f')
    with ecol3:
        shared['movements_per_epd_loop']=num_box('Loaded movements per source EPD loop',shared['movements_per_epd_loop'],'epdconv',min_value=0.001,step=1)
        shared['epd_reference_loops']=num_box('Reference EPD pallet life (loops)',shared['epd_reference_loops'],'epdref',min_value=1,step=1)
    with st.expander('Additional CO₂e / timber assumptions'):
        p,q,r=st.columns(3)
        with p:shared['epd_eol_per_loop']=num_box('End-of-life proxy (kg CO₂e/loop)',shared['epd_eol_per_loop'],'epdeol',step=.001,fmt='%.5f')
        with q:shared['pallet_mass_kg']=num_box('Pallet mass (kg)',shared['pallet_mass_kg'],'mass',min_value=.01,step=1)
        with r:shared['timber_share']=rate_box('Timber mass fraction (%)',shared['timber_share'],'timbershare')
        shared['repair_timber_per_loop']=num_box('Repair timber input (kg/loop)',shared['repair_timber_per_loop'],'repairwood',step=.01,fmt='%.3f')
    st.caption('The source labels “production” and “end-of-life” are screening allocations from a Norwegian pallet EPD; **they are not verified standalone CHEP manufacturing or disposal factors**.')
    st.markdown('#### CO₂e — return network for the three options')
    carbon_scenario='Mixed / typical' if scn=='Downside' else scn
    emissions_inputs={k:dict(v) for k,v in CONFIG['sustainability_scenarios'][carbon_scenario].items()}
    for opt in OPTIONS:
        with st.expander(f'{opt} — return and reuse assumptions',expanded=False):
            one,two,three=st.columns(3)
            data=emissions_inputs[opt]
            safe=opt.lower().replace(' ','_')
            with one:
                data['return_km']=num_box('Allocated return distance (km)',data['return_km'],f'co2_km_{safe}_{scn}',step=10)
                data['utilisation']=rate_box('Empty return utilisation (%)',data['utilisation'],f'co2_util_{safe}_{scn}')
            with two:
                data['pallets_per_stack']=num_box('Pallets per empty stack',data['pallets_per_stack'],f'co2_stack_{safe}_{scn}',min_value=1,step=1)
                data['useful_loops']=num_box('Useful lifetime (source loops)',data['useful_loops'],f'co2_loops_{safe}_{scn}',min_value=1,step=1)
            with three:
                data['repairs_per_loop']=num_box('Repairs per source loop',data['repairs_per_loop'],f'co2_repair_{safe}_{scn}',min_value=0,step=.05,fmt='%.3f')
                st.caption('Cycle days are not pallet lifetime movements. Return transport is modelled separately for each option.')
    st.divider()
    st.markdown('#### Mandatory customer suitability checks')
    st.caption('These are explicit customer validations. The spreadsheet does not contain evidence to automatically pass these checks.')
    feasibility={}
    fcols=st.columns(3)
    for i,opt in enumerate(OPTIONS):
        with fcols[i]:
            feasibility[opt]=st.selectbox(opt,['Not validated','Meets requirements','Does not meet requirements'],key=f'feasible_{opt}',help='Covers retailer acceptance, pallet quality, availability and applicable regulatory feasibility.')

# Compute financial and environmental outputs once (single source of truth across all tabs)
if mode == 'Sponsor starting case':
    costs=sponsor_tco(n,CONFIG['sponsor']['white_annual_eur'],CONFIG['sponsor']['pool_annual_eur'],CONFIG['sponsor']['annual_movements'])
else:
    costs=bottom_up_tco(financial)
for opt,extra in [('Current white exchange',extra_white),('CHEP pooling',extra_pool)]:
    costs[opt]=add_per_trip_cost(costs[opt],extra,n)
if improved_choice=='Enter an improved-white annual TCO directly' and direct_annual and direct_annual>0:
    costs['Improved white exchange']=direct_improved_cost(n,direct_annual)
elif improved_choice.startswith('Estimate an improvement package'):
    if mode=='Sponsor starting case':
        improved_cost=costs['Current white exchange'].annual - n*sponsor_savings - n*extra_white*hidden_saving + intervention_cost
        if improved_cost>=0:
            costs['Improved white exchange']=direct_improved_cost(n,improved_cost)
    else:
        costs['Improved white exchange']=improved_white_cost(costs['Current white exchange'],n,intervention_cost,savings_rates,
                                                             extra_white,hidden_saving)
carbons={opt:calculate_emissions(shared,emissions_inputs[opt],n) for opt in OPTIONS}
ranking=cheapest_cost_option(costs,feasibility)

with comparison_tab:
    st.subheader('2. Three-option comparison')
    st.caption(f'Customer volume: {n:,} loaded movements/year • Cost source: {mode} • Scenario: {scn}')
    if mode=='Sponsor starting case':
        st.info('The supplied case totals are held at their reference cost per movement and scaled with annual volume. This is an illustrative assumption because the sponsor baseline does not provide a fixed/variable cost split.')
    else:
        st.info('The team’s base-case bottom-up totals differ from the sponsor’s supplied baseline. This page uses **only the bottom-up result** in the financial comparison.')
    if 'Improved white exchange' not in costs:
        st.warning('**Financial comparison incomplete:** an improved-white TCO is missing. All three CO₂e figures are shown, but only two options have financial totals.')

    rows=[]
    for opt in OPTIONS:
        t=costs.get(opt)
        c=carbons[opt]
        rows.append({'Pallet strategy':opt,
            'Annual TCO (EUR)':round(t.annual) if t else 'Not provided',
            'TCO (EUR/trip)':round(t.per_trip,3) if t else 'Not provided',
            'CO₂e (kg/trip)':round(c.per_trip,3),
            'CO₂e (tonnes/year)':round(c.annual_tonnes,1),
            'Timber proxy (kg/trip)':round(c.timber_kg_per_trip,3),
            'Feasibility':feasibility[opt]})
    st.dataframe(rows,use_container_width=True,hide_index=True)
    a,b,c=st.columns(3)
    a.metric('Cost gap: pooling − current white',eur(costs['CHEP pooling'].annual-costs['Current white exchange'].annual))
    b.metric('Pooling CO₂e saving vs white',f"{carbons['Current white exchange'].annual_tonnes-carbons['CHEP pooling'].annual_tonnes:,.1f} t/yr")
    c.metric('Current cost-leading eligible option',ranking['cost_leader'] or 'None')
    lcol,rcol=st.columns(2)
    with lcol:
        st.markdown('**Annual total cost**')
        st.plotly_chart(cost_chart(costs),use_container_width=True)
    with rcol:
        st.markdown('**Annual physical greenhouse-gas emissions**')
        st.plotly_chart(carbon_chart(carbons),use_container_width=True)
    st.markdown('#### Interpretation')
    if 'Improved white exchange' not in costs:
        st.error('No complete three-way financial recommendation: the improved-white cost is missing. Enter its verified TCO or explicitly choose an illustrative intervention scenario.',icon='⚠️')
    if ranking['cost_leader'] is not None:
        st.markdown(f'**Lowest modelled cost among non-excluded options:** {ranking["cost_leader"]}.')
        st.caption(ranking['confidence']+'. This is not an overall recommendation: sustainability and regulatory/service requirements remain separate constraints.')
    else:st.error('All three options are marked infeasible; revisit the suitability checks.')
    if price>0:
        st.markdown('#### Optional internal carbon valuation — sensitivity only')
        st.caption('Illustrative monetary value of physical emissions; not a realised transaction, tax or EU ETS allowance expense. No carbon valuation has been added to the TCO ranking above.')
        st.dataframe([{'Option':o,'Physical t CO₂e':round(carbons[o].annual_tonnes,2),
            'Illustrative carbon value (€)':round(carbons[o].annual_tonnes*price,2)} for o in OPTIONS],
            use_container_width=True,hide_index=True)
    with st.expander('View component breakdown: annual cost and physical CO₂e'):
        c1,c2=st.columns(2)
        with c1:
            st.caption('Financial components, €/year')
            st.dataframe([{'Option':o,'Cost line':line,'€ / year':round(amount,2)} for o in costs for line,amount in costs[o].lines.items()],use_container_width=True,hide_index=True)
        with c2:
            st.caption('Lifecycle screening, kg CO₂e per loaded movement')
            st.dataframe([{'Option':o,'Component':line,'kg CO₂e/trip':round(amount,4)} for o in OPTIONS for line,amount in carbons[o].components.items()],use_container_width=True,hide_index=True)
    st.markdown('#### Export a customer discussion summary')
    f=io.StringIO();writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    st.download_button('Download three-option comparison (CSV)',data=f.getvalue(),file_name='pallet_customer_comparison.csv',mime='text/csv',icon='📥')

with sensitivity_tab:
    st.subheader('3. Sensitivity and break-even')
    st.caption('These tests vary one input at a time. Any output calculated from unverified assumptions remains a screening result.')
    nwhite=costs['Current white exchange'].annual
    npool=costs['CHEP pooling'].annual
    gap_per_move=(npool-nwhite)/n
    if gap_per_move>0:
        st.info(f'**Current-to-pooling switch point:** if current white-exchange costs increase by another **{eur(gap_per_move,3)} per loaded movement** (and pooling costs do not change), the two existing modelled costs are equal.')
    elif gap_per_move<0:
        st.info(f'Pooling is already cheaper than current white exchange by **{eur(-gap_per_move,3)} per movement**, within this financial scenario.')
    else:st.info('Current white exchange and pooling are equal in this financial scenario.')
    xchoice=['Additional white cost (€/trip)']
    if mode=='Team bottom-up model':xchoice += ['White loss rate (%)','Unredeemed voucher rate (%)','CHEP rental fee (€/trip)']
    sel=st.selectbox('Sensitivity driver',xchoice)
    xs=[]; ys={o:[] for o in OPTIONS if o in costs}
    if sel=='Additional white cost (€/trip)':
        maxx=max(1.,max(0.,gap_per_move)*1.8)
        xs=[i*maxx/45 for i in range(46)]
        for x in xs:
            bumped=add_per_trip_cost(costs['Current white exchange'],x,n)
            ys['Current white exchange'].append(bumped.per_trip)
            ys['CHEP pooling'].append(costs['CHEP pooling'].per_trip)
            if 'Improved white exchange' in costs:
                # For an intervention estimate, partially eliminate the additional shock;
                # for direct input, do not claim it changes with unknown economics.
                if improved_choice.startswith('Estimate'):
                    share=hidden_saving if mode=='Team bottom-up model' else 0.
                    ys['Improved white exchange'].append(costs['Improved white exchange'].per_trip + x*(1-share))
                else:ys['Improved white exchange'].append(costs['Improved white exchange'].per_trip)
        xlab='Additional uncounted white operating cost (€/loaded movement)'
    else:
        if sel=='White loss rate (%)':
            xs=[i*10/45 for i in range(46)]; key='white_loss_rate'; factor=.01;xlab='White pallet loss rate (% of loaded trips)'
        elif sel=='Unredeemed voucher rate (%)':
            xs=[i*60/45 for i in range(46)];key='white_unpaid_voucher_rate';factor=.01;xlab='Unredeemed vouchers (% of vouchers)'
        else:
            basefee=financial['pool_rental_per_trip'];lower=max(0.,basefee-1.5);upper=basefee+1.5
            xs=[lower+i*(upper-lower)/45 for i in range(46)];key='pool_rental_per_trip';factor=1.;xlab='CHEP rental fee (€/trip)'
        for x in xs:
            test_inputs=dict(financial);test_inputs[key]=x*factor
            test_tco=bottom_up_tco(test_inputs)
            t_white=add_per_trip_cost(test_tco['Current white exchange'],extra_white,n)
            t_pool=add_per_trip_cost(test_tco['CHEP pooling'],extra_pool,n)
            ys['Current white exchange'].append(t_white.per_trip)
            ys['CHEP pooling'].append(t_pool.per_trip)
            if 'Improved white exchange' in costs:
                if improved_choice.startswith('Estimate'):
                    new_imp=improved_white_cost(t_white,n,intervention_cost,savings_rates,extra_white,hidden_saving)
                    ys['Improved white exchange'].append(new_imp.per_trip)
                else:ys['Improved white exchange'].append(costs['Improved white exchange'].per_trip)
    fig=go.Figure()
    for opt,yy in ys.items():
        fig.add_trace(go.Scatter(x=xs,y=yy,mode='lines',name=opt,line=dict(color=PALETTE[opt],width=3)))
    fig.update_layout(height=400,xaxis_title=xlab,yaxis_title='Annual TCO / loaded movement (EUR)',
        margin=dict(t=20,l=10,r=10,b=20),legend=dict(orientation='h',y=-.25),
        plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig,use_container_width=True)
    st.caption('The break-even curves are a financial stress test, not a prediction. Flat series indicate a cost held constant during this one-factor test.')

    st.markdown('#### All operating scenarios from both workbooks')
    scenario_rows=[]
    for current in ['Low complexity','Mixed / typical','High complexity','Downside']:
        a=dict(CONFIG['tco_scenarios'][current]);a['annual_movements']=n
        if mode=='Team bottom-up model':scenario_cost=bottom_up_tco(a)
        else:scenario_cost=sponsor_tco(n,CONFIG['sponsor']['white_annual_eur'],CONFIG['sponsor']['pool_annual_eur'],CONFIG['sponsor']['annual_movements'])
        scenario_cost['Current white exchange']=add_per_trip_cost(scenario_cost['Current white exchange'],extra_white,n)
        scenario_cost['CHEP pooling']=add_per_trip_cost(scenario_cost['CHEP pooling'],extra_pool,n)
        se='Mixed / typical' if current=='Downside' else current
        scdata=CONFIG['sustainability_scenarios'][se]
        sw=calculate_emissions(shared,scdata['Current white exchange'],n)
        sp=calculate_emissions(shared,scdata['CHEP pooling'],n)
        scenario_rows.append({'Scenario':current,'White TCO/trip (€)':round(scenario_cost['Current white exchange'].per_trip,3),
            'Pooling TCO/trip (€)':round(scenario_cost['CHEP pooling'].per_trip,3),
            'Pool − white (€/trip)':round(scenario_cost['CHEP pooling'].per_trip-scenario_cost['Current white exchange'].per_trip,3),
            'White CO₂e (kg/trip)':round(sw.per_trip,3),'Pool CO₂e (kg/trip)':round(sp.per_trip,3)})
    st.dataframe(scenario_rows,use_container_width=True,hide_index=True)
    if mode=='Sponsor starting case':
        st.caption('The sponsor reference is unchanged by low/high scenario selection because scenario-specific sponsor costs are unavailable. The team’s scenario calculations are shown when “Team bottom-up model” is selected.')
    else:
        st.caption('Scenario rows use the original TCOv3 defaults for each scenario. Current customer edits on the input tab affect the active comparison, not these source-preserved scenario rows.')
    st.caption('For the Downside row, the sustainability workbook has no separate downside carbon scenario, so the mixed/typical carbon network is used.')

with method_tab:
    st.subheader('4. Sources, limitations and validation')
    st.markdown('''**Reference spreadsheets:**

- `TCOv3.xlsx`, `Inputs`, `Calculation`, `Summary` — current white and CHEP pooling financial calculations, 4 financial scenarios.
- `Pallet_Customer_Sustainability_V2.xlsx`, `Customer Inputs`, `Calculations`, `Scenario Tests`, `Evidence & Guide` — three-option environmental screening.
- Competition brief — sponsor starting position: **265,000 movements; €843,003/year white; €909,439/year pooling**.

**Important boundaries and open questions**

- The **improved white exchange financial model is absent** from both uploaded workbooks. A supplied value or explicit intervention assumptions are required before an all-three financial ranking is possible.
- `TCOv3.xlsx` base-case totals are approximately **€966,820 white / €1,099,061 pooling**, not the sponsor **€843,003 / €909,439**. Do not combine the two accounting boundaries or interpret their difference as a validated benefit.
- The sustainability workbook is **not a verified CHEP LCA**. Inputs include an assumed **0.9 kg CO₂e/vehicle-km**, **26 floor positions**, transport routes and repair factors. A source EPD 'loop' is provisionally treated as **1 loaded movement**.
- The TCO workbook uses **495 empty pallets per truck**, whereas the sustainability model's typical recovery calculation is **26 × 15 × 70% = 273 pallets per truck**. These model different assumed capacities, not a confirmed common operational basis. Validate both before combining them in a unified business case.
- The sustainability transport term covers modelled empty-return/repositioning movements; it **excludes common outbound freight**. Its timber figure is a screening mass proxy, not a certified forestry indicator.
- The TCO workbook allocates **€0 to working capital**. It may also require review of potential overlap between pallet scrap, loss and voucher charges. Do not treat inputs labelled “FOUND” as independently verified merely because they appear in Excel.
- A stored cycle time (days) is **not** equivalent to lifetime pallet movements. Repair and loss rates need matching denominators.
- Carbon emissions should be presented physically (kg CO₂e/trip) **before** any optional internal carbon price. Do not imply this price is an automatic tax or realised cash saving.
- Regulatory compliance, retailer acceptance, service-level guarantees and safety need customer-specific validation; this tool is not legal or engineering assurance.
''')
    st.markdown('#### Public references identified in your sustainability workbook')
    st.markdown('''- [Dotelli et al., *Applied Sciences* (2025)](https://www.mdpi.com/2076-3417/15/4/2032) — published Italian transport-use case (not a CHEP-specific carbon result).
- [Smart Retur EUR pallet EPD](https://www.epd-global.com/) — Norwegian lifecycle proxy, with boundary and allocation assumptions.
- [Smart Freight Centre](https://www.smartfreightcentre.org/) — freight emissions methods and GLEC guidance.
- [Brambles 2026 Sustainability Review](https://www.brambles.com/Content/cms/FY26-Results/pdf/Sustainability/Brambles-2026-Sustainability-Review.pdf) — contextual global sustainability indicators, not a white-versus-CHEP loaded-trip LCA.
''')
    st.markdown('#### Before sharing with a CHEP customer')
    for item in ['Match every active cost input to a customer record or labelled assumption',
        'Confirm the improved-white option has a complete and credible TCO',
        'Validate truck capacity, utilisation, routes, pallet lifetime and CO₂e boundaries',
        'Check which mandatory service, quality and regulatory requirements each option meets',
        'Reconcile the team’s financial totals to the sponsor baseline or document why they differ']:
        st.checkbox(item,value=False,key='audit_'+item)
    st.caption('This app is an educational prototype. It performs local calculations; no inputs are transmitted to CHEP or the competition panel by this code.')

st.divider()
st.caption('Pallet Strategy Advisor · Educational competition prototype · Cost outcomes are not full recommendations · Do not use unvalidated figures as CHEP-specific claims.')
