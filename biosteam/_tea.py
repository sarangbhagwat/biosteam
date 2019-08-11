# -*- coding: utf-8 -*-
"""
Created on Mon Feb  4 19:38:37 2019

@author: Guest Group
"""

import pandas as pd
import numpy as np
from ._utils import wegstein_secant, aitken_secant, secant
from copy import copy as copy_

__all__ = ('TEA', 'CombinedTEA')


# TODO: Add 'SL', 'DB', 'DDB', 'SYD', 'ACRS' and 'MACRS' functions to generate depreciation data

# %% Depreciation data

_MACRS = {'MACRS5': np.array([.2000, .3200, .1920,
                             .1152, .1152, .0576]),
          
          'MACRS7':  np.array([.1429, .2449, .1749,
                               .1249, .0893, .0892,
                               .0893, .0446]),
          
          'MACRS10': np.array([.1000, .1800, .1440,
                               .1152, .0922, .0737,
                               .0655, .0655, .0656,
                               .0655, .0328]),

          'MACRS15': np.array([.0500, .0950, .0855,
                               .0770, .0693, .0623,
                               .0590, .0590, .0591,
                               .0590, .0591, .0590,
                               .0591, .0590, .0591,
                               .0295]),

          'MACRS20': np.array([0.03750, 0.07219, 0.06677,
                               0.06177, 0.05713, 0.05285,
                               0.04888, 0.04522, 0.4462,
                               0.04461, 0.04462, 0.04461,
                               0.04462, 0.04461, 0.04462,
                               0.04461, 0.04462, 0.04461,
                               0.04462, 0.04461, 0.02231])}


# %% Cash flow and results info

_cashflow_columns = ('Depreciation',
                     'Fixed capital',
                     'Working capital',
                     'Loan',
                     'Loan payment',
                     'Annual operating cost (excl. depr.)',
                     'Sales',
                     'Net earnings',
                     'Cash flow',
                     'Discounted cash flow',
                     'Cumulative cash flow')

# %% Utilities
        
def initial_loan_principal(loan, interest):
    principal = 0
    for loan_i in loan:
        principal = loan_i + principal * interest
    return principal

def final_loan_principal(payment, principal, interest, years):
    for iter in range(years):
        principal += principal * interest - payment
    return principal

def solve_payment(payment, loan, interest, years):
    principal = initial_loan_principal(loan, interest)
    return wegstein_secant(final_loan_principal,
                           payment, payment+1., 1e-4, 1e-4,
                           args=(principal, interest, years))


# %% Techno-Economic Analysis

class TEA:
    """Abstract TEA class for cash flow analysis.
    
        **Abstract methods**
        
            **_TDC:** [function] Should take direct permanent investment as an argument and return total depreciable capital (e.g. _TDC(self, DPI) -> TDC).
            
            **_FCI:** [function] Should take total depreciable capital as an argument and return fixed capital investment (e.g. _FCI(self, TDC) -> FCI).
            
            **_FOC:** [function] Should take fixed capital investment as an arguments and return fixed operating cost without depreciation (e.g. _FOC(self, FCI) -> FOC).
        
        **Parameters**
        
            **system:** [System] Should contain feed and product streams.
            
            **IRR:** [float]  Internal rate of return (fraction).
            
            **duration:** tuple[int, int] Start and end year of venture (e.g. (2018, 2038)).
            
            **depreciation:** [str] 'MACRS' + number of years (e.g. 'MACRS7').
            
            **operating_days:** [float] Number of operating days per year.
            
            **income_tax:** [float] Combined federal and state income tax rate (fraction).
            
            **lang_factor:** [float] Lang factor for getting fixed capital investment from total purchase cost. If no lang factor, estimate capital investment using bare module factors.
            
            **construction_schedule:** tuple[float] Construction investment fractions per year (e.g. (0.5, 0.5) for 50% capital investment in the first year and 50% investment in the second).
            
            **startup_months:** [float] Startup time in months.
            
            **startup_FOCfrac:** [float] Fraction of fixed operating costs incurred during startup.
            
            **startup_VOCfrac:** [float] Fraction of variable operating costs incurred during startup.
            
            **startup_salesfrac:** [float] Fraction of sales achieved during startup.
            
            **WC_over_FCI**: [float] Working capital as a fraction of fixed capital investment.
            
            **finanace_interest:** [float] Yearly interest of capital cost financing as a fraction.
            
            **finance_years:** [int] Number of years the loan is paid for.
            
            **finance_fraction:** [float] Fraction of capital cost that needs to be financed.
                        
        **Examples**
        
            :doc:`Techno-economic analysis of a biorefinery` 
    
    """
    
    __slots__ = ('system', 'income_tax', 'lang_factor', 'WC_over_FCI',
                 'finance_interest', 'finance_years', 'finance_fraction',
                 '_construction_schedule', '_startup_time',
                 'startup_FOCfrac', 'startup_VOCfrac', 'startup_salesfrac',
                 'units', '_startup_schedule', '_operating_days',
                 '_annual_factor', '_duration', '_duration_array',
                 '_depreciation_array', '_depreciation', '_years',
                 '_duration', '_start',  'IRR', '_IRR', '_sales')
    
    def __init_subclass__(self, isabstract=False):
        if isabstract: return
        for method in ('_TDC', '_FCI', '_FOC'):
            if not hasattr(self, method):
                raise NotImplementedError(f"subclass must implement a '{method}' method unless the 'isabstract' keyword argument is True")

    @staticmethod
    def like(system, other):
        """Create a Cashflow object from `system` with the same settings as `other`."""
        self = copy_(other)
        self.units = sorted(system._costunits, key=lambda x: x.line)
        self.system = system
        system._TEA = self
        return self

    def __init__(self, system, IRR, duration, depreciation, income_tax,
                 operating_days, lang_factor, construction_schedule,
                 startup_months, startup_FOCfrac, startup_VOCfrac,
                 startup_salesfrac, WC_over_FCI, finance_interest,
                 finance_years, finance_fraction):
        self.IRR = IRR
        self.duration = duration
        self.depreciation = depreciation
        self.income_tax = income_tax
        self.operating_days = operating_days
        self.lang_factor = lang_factor
        self.construction_schedule = construction_schedule
        self.startup_months = startup_months
        self.startup_FOCfrac = startup_FOCfrac
        self.startup_VOCfrac = startup_VOCfrac
        self.startup_salesfrac = startup_salesfrac
        self.WC_over_FCI = WC_over_FCI
        self.finance_interest = finance_interest
        self.finance_years = finance_years
        self.finance_fraction = finance_fraction
        
        #: Guess IRR for solve_IRR method
        self._IRR = IRR
        
        #: Guess cost for solve_price method
        self._sales = 0
        
        #: list[Unit] All unit operations considered
        self.units = sorted(system._costunits, key=lambda x: x.line)
        
        self.system = system
        system._TEA = self

    @property
    def operating_days(self):
        """[float] Number of operating days per year."""
        return self._operating_days
    @operating_days.setter
    def operating_days(self, days):
        """[float] Number of operating days per year."""
        self._operating_days = days
        self._annual_factor = days*24
    
    @property
    def duration(self):
        """tuple[int, int] Start and end year of venture."""
        return self._duration
    @duration.setter
    def duration(self, duration):
        self._duration = duration
        self._years = duration[1] - duration[0]
        
    @property
    def depreciation(self):
        """[str] 'MACRS' + number of years (e.g. 'MACRS7')."""
        return self._depreciation
    @depreciation.setter
    def depreciation(self, depreciation):
        try:
            self._depreciation_array = _MACRS[depreciation]
        except KeyError:
            raise ValueError(f"depreciation must be either 'MACRS5', 'MACRS7', 'MACRS10' or 'MACRS15 (not {repr(depreciation)})")
        self._depreciation = depreciation
    
    @property
    def construction_schedule(self):
        """tuple[float] Construction investment fractions per year, starting from year 0. For example, for 50% capital investment in year 0 and 50% investment in year 1: (0.5, 0.5)."""
        return tuple(self._construction_schedule)
    @construction_schedule.setter
    def construction_schedule(self, schedule):
        self._construction_schedule = np.array(schedule, dtype=float)
        self._start = len(schedule)
    
    @property
    def startup_months(self):
        return self._startup_time * 12.
    @startup_months.setter
    def startup_months(self, months):
        assert months <= 12., "startup time must be less than a year"
        self._startup_time = months/12.
    
    @property
    def utility_cost(self):
        """Total utility cost (USD/yr)."""
        return sum([u.utility_cost for u in self.units]) * self._annual_factor
    @property
    def purchase_cost(self):
        """Total purchase cost (USD)."""
        return sum([u.purchase_cost for u in self.units])
    @property
    def installation_cost(self):
        """Total installation cost (USD)."""
        return sum([u.installation_cost for u in self.units])
    @property
    def DPI(self):
        """Direct permanent investment."""
        return self.purchase_cost * self.lang_factor if self.lang_factor else self.installation_cost
    @property
    def TDC(self):
        """Total depreciable capital."""
        return self._TDC(self.DPI)
    @property
    def FCI(self):
        """Fixed capital investment."""
        return self._FCI(self.TDC)
    @property
    def TCI(self):
        """Total capital investment."""
        return (1. + self.WC_over_FCI)*self.FCI
    @property
    def FOC(self):
        """Fixed operating costs (USD/yr)."""
        return self._FOC(self.FCI)
    @property
    def VOC(self):
        """Variable operating costs (USD/yr)."""
        return self.material_cost + self.utility_cost
    @property
    def AOC(self):
        """Annual operating cost excluding depreciation (USD/yr)."""
        return self.FOC + self.VOC
    @property
    def working_capital(self):
        return self.WC_over_FCI * self.TDC
    @property
    def material_cost(self):
        """Annual material cost."""
        return sum([s.cost for s in self.system.feeds if s.price]) * self._annual_factor
    @property
    def annual_depreciation(self):
        """Depreciation (USD/yr) equivalent to FCI dived by the the duration of the venture."""
        return self.FCI/(self.duration[1]-self.duration[0])
    @property
    def sales(self):
        """Annual sales revenue."""
        return sum([s.cost for s in self.system.products if s.price]) * self._annual_factor
    @property
    def ROI(self):
        """Return on investment (1/yr) without accounting for annualized depreciation."""
        FCI = self.FCI
        net_earnings = (1-self.income_tax)*(self.sales-self._AOC(FCI))
        TCI = FCI*(1.+self.WC_over_FCI)
        return net_earnings/TCI
    @property
    def net_earnings(self):
        """Net earnings without accounting for annualized depreciation."""
        return (1-self.income_tax)*(self.sales-self.AOC)
    @property
    def PBP(self):
        """Pay back period (yr) without accounting for annualized depreciation."""
        FCI = self.FCI
        net_earnings = (1-self.income_tax)*(self.sales-self._AOC(FCI))
        return FCI/net_earnings

    def get_cashflow_table(self):
        """Return DataFrame of the cash flow analysis."""
        return NotImplemented # TODO: Cashflow table

    @property
    def NPV(self):
        """Net present value."""
        return self._NPV_at_IRR(self.IRR, self.cashflow)
    
    def _AOC(self, FCI):
        """Return AOC at given FCI"""
        return self._FOC(FCI) + self.VOC
    
    def production_cost(self, *products):
        """Return production cost of products.
        
        **Parameters**
        
            ***products:** [Stream] Main products of the system
        
        .. Note::
           If there is more than one main product, The production cost is proportionally allocated to each of the main products with respect to their marketing values. The marketing value of each product is determined by the annual production multiplied by its selling price.
        """
        market_values = np.array([i.cost for i in products])
        weights = market_values/market_values.sum()
        return weights*self.AOC
    
    @property
    def cashflow(self):
        # Cash flow data and parameters
        # C_FC: Fixed capital
        # C_WC: Working capital
        # Loan: Money gained from loan
        # LIP: Loan interest payment
        # D: Depreciation
        # C: Annual operating cost (excluding depreciation)
        # S: Sales
        # NE: Net earnings
        # CF: Cash flow
        TDC = self.TDC
        FCI = self._FCI(TDC)
        WC = self.WC_over_FCI * FCI
        start = self._start
        years = self._years
        self._duration_array = np.arange(-start, years, dtype=float)
        D, C_FC, C_WC, Loan, LIP, C, S = np.zeros((7, start+years))
        construction_schedule = self._construction_schedule
        C_FC[:start] = FCI*construction_schedule
        depreciation = self._depreciation_array
        D[start:start+len(depreciation)] = TDC*depreciation
        C_WC[start-1] = WC
        C_WC[-1] = -WC
        FOC = self._FOC(FCI)
        VOC = self.VOC
        sales = self.sales
        w0 = self._startup_time
        w1 = 1 - w0
        C[start] = (w0*self.startup_VOCfrac*VOC + w1*VOC
                    + w0*self.startup_FOCfrac*FOC + w1*FOC)
        S[start] = w0*self.startup_salesfrac*sales + w1*sales
        start1 = start + 1
        C[start1:] = VOC + FOC
        S[start1:] = sales
        NE = (S - C - D)*(1 - self.income_tax)
        if self.finance_interest:
            interest = self.finance_interest
            years = self.finance_years
            end = start+years
            Loan[:start] = loan = self.finance_fraction*(C_FC[:start]+C_WC[:start])
            LIP[start:end] = solve_payment(loan.sum()/years * (1. + interest),
                                           loan, interest, years)
            return NE + D + Loan - C_FC - C_WC - LIP
        else:
            return NE + D - C_FC - C_WC
    
    def _NPV_at_IRR(self, IRR, cashflow):
        """Return NPV at given IRR and cashflow data."""
        return (cashflow/(1.+IRR)**self._duration_array).sum()

    def _NPV_with_sales(self, sales, cashflow):
        """Return NPV with an additional annualized variable sales."""
        cashflow = cashflow.copy()
        w0 = self._startup_time
        cashflow[self._start] += w0*self.startup_VOCfrac*sales + (1-w0)*sales
        cashflow[self._start+1:] += sales
        return (cashflow/(1+self.IRR)**self._duration_array).sum()

    def solve_IRR(self):
        """Return the IRR at the break even point (NPV = 0) through cash flow analysis."""
        try:
            self._IRR = aitken_secant(self._NPV_at_IRR,
                                      self._IRR, self._IRR+1e-6,
                                      xtol=1e-6, maxiter=200,
                                      args=(self.cashflow,))
        except:
            self._IRR = secant(self._NPV_at_IRR,
                               0.15, 0.15001,
                               xtol=1e-6, maxiter=200,
                               args=(self.cashflow,))
        return self._IRR
    
    def _price2cost(self, stream):
        """Get factor to convert stream price to cost for cashflow in solve_price method."""
        return stream.massnet*self._annual_factor*(1-self.income_tax)
    
    def solve_price(self, stream):
        """Return the price (USD/kg) of stream at the break even point (NPV = 0) through cash flow analysis. 
        
        **Parameters**
        
            **stream:** [Stream] Stream with variable selling price.
            
        """
        price2cost = self._price2cost(stream)
        try:
            self._sales = aitken_secant(self._NPV_with_sales,
                                        self._sales, self._sales+1e-6,
                                        xtol=1e-6, maxiter=200,
                                        args=(self.cashflow,))
        except:
            self._sales = secant(self._NPV_with_sales,
                                 0, 1e-6,
                                 args=(self.cashflow,),
                                 xtol=1e-6, maxiter=200)
        if stream.sink:
            return stream.price - self._sales/price2cost
        elif stream.source:
            return stream.price + self._sales/price2cost
        else:
            raise ValueError(f"stream must be either a feed or a product")
    
    def __repr__(self):
        return f'<{type(self).__name__}: {self.system.ID}>'
    
    def _info(self):
        return (f'{type(self).__name__}: {self.system.ID}\n'
                f' NPV: {self.NPV:.3g} USD at {self.IRR:.1%} IRR\n'
                f' ROI: {self.ROI:.3g} 1/yr\n'
                f' PBP: {self.PBP:.3g} yr')
    
    def show(self):
        """Prints information on unit."""
        print(self._info())
    _ipython_display_ = show
                
    
class CombinedTEA(TEA):
    
    _TDC = _FCI = _FOC = NotImplemented
    
    __slots__ = ('TEAs',)
    
    def __init__(self, TEAs, IRR):
        #: iterable[TEA] All TEA objects for cashflow calculation
        self.TEAs = TEAs
        
        #: [float] Internal rate of return (fraction)
        self.IRR = IRR
        
        #: Guess IRR for solve_IRR method
        self._IRR = IRR
        
        #: Guess sales for solve_price method
        self._sales = 0
    
    @property
    def cashflow(self):
        return sum([i.cashflow for i in self.TEAs])
    @property
    def utility_cost(self):
        """Total utility cost (USD/yr)."""
        return sum([i.utility_cost for i in self.TEAs])
    @property
    def purchase_cost(self):
        """Total purchase cost (USD)."""
        return sum([i.purchase_cost for i in self.TEAs])
    @property
    def installation_cost(self):
        """Total installation cost (USD)."""
        return sum([i.installation_cost for i in self.TEAs])
    @property
    def DPI(self):
        """Direct permanent investment."""
        return sum([i.DPI for i in self.TEAs])
    @property
    def TDC(self):
        """Total depreciable capital."""
        return sum([i.TDC for i in self.TEAs])
    @property
    def FCI(self):
        """Fixed capital investment."""
        return sum([i.FCI for i in self.TEAs])
    @property
    def TCI(self):
        """Total capital investment."""
        return sum([i.TCI for i in self.TEAs])
    @property
    def FOC(self):
        """Fixed operating costs (USD/yr)."""
        return sum([i.FOC for i in self.TEAs])
    @property
    def VOC(self):
        """Variable operating costs (USD/yr)."""
        return self.material_cost + self.utility_cost
    @property
    def AOC(self):
        """Annual operating cost excluding depreciation (USD/yr)."""
        return self.FOC + self.VOC
    @property
    def working_capital(self):
        return sum([i.working_capital for i in self.TEAs])
    @property
    def material_cost(self):
        """Annual material cost."""
        return sum([i.material_cost for i in self.TEAs])
    @property
    def annual_depreciation(self):
        """Depreciation (USD/yr) equivalent to FCI dived by the the duration of the venture."""
        return sum([i.annual_depreciation for i in self.TEAs])
    @property
    def sales(self):
        """Annual sales revenue."""
        return sum([i.sales for i in self.TEAs])
    @property
    def net_earnings(self):
        """Net earnings without accounting for annualized depreciation."""
        return sum([i.net_earnings for i in self.TEAs])
    @property
    def ROI(self):
        """Return on investment (1/yr) without accounting for annualized depreciation."""
        return sum([i.ROI for i in self.TEAs])
    @property
    def PBP(self):
        """Pay back period (yr) without accounting for annualized depreciation."""
        return self.FCI/self.net_earnings
    
    def get_cashflow_table(self):
        """Return DataFrame of the cash flow analysis."""
        return NotImplemented # TODO: Cashflow table
    
    def _NPV_at_IRR(self, IRR, TEA_cashflows):
        """Return NPV at given IRR and cashflow data."""
        return sum([i._NPV_at_IRR(IRR, j) for i, j in TEA_cashflows])

    def _NPV_with_sales(self, sales, TEA_cashflows, cashflow, TEA):
        """Return NPV with additional sales."""
        CF = cashflow.copy()
        TEA_sales = sales*TEA._annual_factor*(1-TEA.income_tax)
        w0 = TEA._startup_time
        cashflow[TEA._start] += w0*TEA.startup_VOCfrac*TEA_sales + (1.-w0)*TEA_sales
        cashflow[TEA._start+1:] += TEA_sales
        NPV = self._NPV_at_IRR(self.IRR, TEA_cashflows)
        cashflow[:] = CF
        return NPV
    
    def solve_IRR(self):
        """Return the IRR at the break even point (NPV = 0) through cash flow analysis."""
        try:
            self._IRR = aitken_secant(self._NPV_at_IRR,
                                      self._IRR, self._IRR+1e-6,
                                      xtol=1e-6, maxiter=200,
                                      args=([(i, i.cashflow) for i in self.TEAs],))
        except:
            self._IRR = secant(self._NPV_at_IRR,
                               0.15, 0.15001,
                               xtol=1e-6, maxiter=200,
                               args=([(i, i.cashflow) for i in self.TEAs],))
        return self._IRR
    
    def solve_price(self, stream, TEA):
        """Return the price (USD/kg) of stream at the break even point (NPV = 0) through cash flow analysis. 
        
        **Parameters**
        
            **stream:** [Stream] Stream with variable selling price.
            
            **TEA:** [TEA] stream should belong here.
            
        """
        price2cost = self._price2cost(stream)
        TEA_cashflows = [(i, i.cashflow) for i in self.TEAs]
        cashflow = TEA_cashflows[self.TEAs.index(TEA)][1]
        try:
            self._sales = aitken_secant(self._NPV_with_sales,
                                        self._sales, self._sales+1e-6,
                                        xtol=1e-6, maxiter=200,
                                        args=(TEA_cashflows, cashflow, TEA))
        except:
            self._sales = secant(self._NPV_with_sales,
                                 0, 1e-6,
                                 args=(TEA_cashflows, cashflow, TEA),
                                 xtol=1e-6, maxiter=200)
        if stream.sink:
            return stream.price - self._sales/price2cost
        elif stream.source:
            return stream.price + self._sales/price2cost
        else:
            raise ValueError(f"stream must be either a feed or a product")
    
    def _price2cost(self, stream):
        """Get factor to convert stream price to cost for cashflow in solve_price method."""
        return stream.massnet
    
    def __repr__(self):
        return f'<{type(self).__name__}: {", ".join([i.system.ID for i in self.TEAs])}>'
    
    def _info(self):
        return (f'{type(self).__name__}: {", ".join([i.system.ID for i in self.TEAs])}\n'
                f' NPV: {self.NPV:.3g} USD at {self.IRR:.1%} IRR\n'
                f' ROI: {self.ROI:.3g} 1/yr\n'
                f' PBP: {self.PBP:.3g} yr')
    
    def show(self):
        """Prints information on unit."""
        print(self._info())
    _ipython_display_ = show
    
    
    
# def update_loan_principal(loan_principal, loan, loan_payment, interest):
#     principal = 0
#     for i, loan_i in enumerate(loan):
#         loan_principal[i] = principal = loan_i + principal * interest - loan_payment[i]