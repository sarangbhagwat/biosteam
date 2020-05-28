# -*- coding: utf-8 -*-
# BioSTEAM: The Biorefinery Simulation and Techno-Economic Analysis Modules
# Copyright (C) 2020, Yoel Cortes-Pena <yoelcortes@gmail.com>
# 
# This module is under the UIUC open-source license. See 
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.
"""
"""
import numpy as np
from .. import Unit
from ._process_specification import ProcessSpecification
from ..utils import static

__all__ = ('MassBalance',)

# %% Mass Balance Unit

@static
class MassBalance(Unit):
    """
    Create a Unit object that changes net input flow rates to satisfy output
    flow rates. This calculation is based on mass balance equations for
    specified IDs. 

    Parameters
    ----------
    ins : stream
        Inlet stream. Doesn't actually affect mass balance. It's just to
        show the position in the process.
    outs : stream
        Outlet stream. Doesn't actually affect mass balance. It's just to
        show the position in the process.
    chemical_IDs : tuple[str]
        Chemicals that will be used to solve mass balance linear equations.
        The number of chemicals must be same as the number of input streams varied.
    variable_inlets : Iterable[Stream]
        Inlet streams that can vary in net flow rate to accomodate for the
        mass balance.
    constant_inlets: Iterable[Stream], optional
        Inlet streams that cannot vary in flow rates.
    constant_outlets: Iterable[Stream], optional
        Outlet streams that cannot vary in flow rates.
    is_exact=True : bool, optional
        True if exact flow rate solution is required for the specified IDs.
    balance='flow' : {'flow', 'composition'}, optional
          * 'flow': Satisfy output flow rates
          * 'composition': Satisfy net output molar composition

    Examples
    --------
    MassBalance are Unit objects that serve to alter flow rates of selected
    chemicals and input streams to satisfy the mass balance.
    The example below uses the MassBalance object to satisfy the target
    flow rate feeding the mixer M1:
    
    >>> from biosteam import System, Stream, settings, main_flowsheet
    >>> from biosteam.units import (Mixer, Splitter, StorageTank, Pump,
    ...                             Flash, MassBalance)
    >>> main_flowsheet.set_flowsheet('mass_balance_example')
    >>> settings.set_thermo(['Water', 'Ethanol'])
    >>> water = Stream('water',
    ...                Water=40,
    ...                units='lb/s',
    ...                T=350, P=101325)
    >>> ethanol = Stream('ethanol',
    ...                  Ethanol=190, Water=30,
    ...                  T=300, P=101325)
    >>> target = Stream('target',
    ...                 Ethanol=500, Water=500)
    >>> T1 = StorageTank('T1', outs='s1')
    >>> T2 = StorageTank('T2', outs='s2')
    >>> P1 = Pump('P1', P=101325, outs='s3')
    >>> P2 = Pump('P2', P=101325, outs='s4')
    >>> M1 = Mixer('M1', outs='s5')
    >>> S1 = Splitter('S1', outs=('s6', 's7'), split=0.5)
    >>> F1 = Flash('F1', outs=('s8', 's9'), V=0.5, P =101325)
    >>> MB1 = MassBalance('MB1', outs='s6_2',
    ...                   variable_inlets=[water, ethanol],
    ...                   constant_inlets=[S1-0],
    ...                   constant_outlets=[target],
    ...                   chemical_IDs=('Ethanol', 'Water'),
    ...                   description='Adjust flow rate of feed to mixer')
    >>> # Connect units
    >>> water-T1-P1
    <Pump: P1>
    >>> ethanol-T2-P2
    <Pump: P2>
    >>> [P1-0, P2-0, MB1-0]-M1-F1-1-S1-0-MB1
    <MassBalance: MB1>
    >>> sys = main_flowsheet.create_system('sys')
    >>> # Make diagram to view system
    >>> # sys.diagram()
    >>> sys.simulate();
    >>> target.show()
    Stream: target
     phase: 'l', T: 298.15 K, P: 101325 Pa
     flow (kmol/hr): Water    500
                     Ethanol  500
    
    """
    _graphics = ProcessSpecification._graphics
    power_utility = None
    heat_utilities = ()
    results = None
    _N_ins = _N_outs = 1

    def __init__(self, ID='', ins=None, outs=(), thermo=None,
                 chemical_IDs=None, variable_inlets=(),
                 constant_outlets=(), constant_inlets=(),
                 is_exact=True, balance='flow',
                 description=""):
        self._numerical_specification = None
        self._load_thermo(thermo)
        self._init_ins(ins)
        self._init_outs(outs)
        self._assert_compatible_property_package()
        self._register(ID)
        self.variable_inlets = variable_inlets
        self.constant_inlets = constant_inlets
        self.constant_outlets = constant_outlets
        self.chemical_IDs = tuple(chemical_IDs)
        self.is_exact = is_exact
        self.balance = balance
        self.description = description
        
    def _run(self):
        """Solve mass balance by iteration."""
        # SOLVING BY ITERATION TAKES 15 LOOPS FOR 2 STREAMS
        # SOLVING BY LEAST-SQUARES TAKES 40 LOOPS
        balance = self.balance
        solver = np.linalg.solve if self.is_exact else np.linalg.lstsq

        # Set up constant and variable streams
        vary = self.variable_inlets # Streams to vary in mass balance
        constant = self.constant_inlets # Constant streams
        index = self.chemicals.get_index(self.chemical_IDs)
        mol_out = sum([s.mol for s in self.constant_outlets])

        if balance == 'flow':
            # Perform the following calculation: Ax = b = f - g
            # Where:
            #    A = flow rate array
            #    x = factors
            #    b = target flow rates
            #    f = output flow rates
            #    g = constant input flow rates

            # Solve linear equations for mass balance
            A = np.array([s.mol for s in vary]).transpose()[index, :]
            f = mol_out[index]
            g = sum([s.mol[index] for s in constant])
            b = f - g
            x = solver(A, b)

            # Set flow rates for input streams
            for factor, s in zip(x, vary):
                s.mol[:] = s.mol * factor

        elif balance == 'composition':
            # Perform the following calculation:
            # Ax = b
            #    = sum( A_ * x_guess + g_ )f - g
            #    = A_ * x_guess * f - O
            # O  = sum(g_)*f - g
            # Where:
            # A_ is flow array for all species
            # g_ is constant flows for all species
            # Same variable definitions as in 'flow'

            # Set all variables
            A_ = np.array([s.mol for s in vary]).transpose()
            A = np.array([s.mol for s in vary]).transpose()[index, :]
            F_mol_out = mol_out.sum()
            z_mol_out = mol_out / F_mol_out if F_mol_out else mol_out
            f = z_mol_out[index]
            g_ = sum([s.mol for s in constant])
            g = g_[index]
            O = sum(g_) * f - g

            # Solve by iteration
            x_guess = np.ones_like(index)
            not_converged = True
            while not_converged:
                # Solve linear equations for mass balance
                b = (A_ * x_guess).sum()*f + O
                x_new = solver(A, b)
                not_converged = sum(((x_new - x_guess)/x_new)**2) > 0.0001
                x_guess = x_new

            # Set flow rates for input streams
            for factor, s in zip(x_new, vary):
                s.mol = s.mol * factor
        
        else:
            raise ValueError( "balance type must be one of the following: 'flow', 'composition'")


# %% Energy Balance Unit

# class EnergyBalance(Unit):
#     """Create a Unit object that changes a stream's temperature, flow rate, or vapor fraction to satisfy energy balance.

#     **Parameters**

#         **index:** [int] Index of stream that can vary in temperature, flow rate, or vapor fraction.
        
#         **Type:** [str] Should be one of the following
#             * 'T': Vary temperature of output stream
#             * 'F': Vary flow rate of input/output stream
#             * 'V': Vary vapor fraction of output stream
        
#         **Qin:** *[float]* Additional energy input.
        
#     .. Note:: This is not a mixer, input streams and output streams should match flow rates.

#     """
#     _kwargs = {'index': None,
#                'Type': 'T',
#                'Qin': 0}
#     line = 'Balance'
#     _has_cost = False
#     _graphics = MassBalance._graphics
#     _init_ins = MassBalance._init_ins
#     _init_outs = MassBalance._init_outs
    
#     def _run(self):        # Get arguments
#         ins = self.ins.copy()
#         outs = self.outs.copy()
#         kwargs = self._kwargs
#         index = kwargs['index']
#         Type = kwargs['Type']
#         Qin = kwargs['Qin']
        
#         # Pop out required streams
#         if Type == 'F':
#             s_in = ins.pop(index)
#             s_out = outs.pop(index)
#         else:
#             s = outs.pop(index)
        
#         # Find required enthalpy
#         H_in = sum(i.H for i in ins) + Qin
#         H_out = sum(o.H for o in outs)
#         H_s = H_out - H_in
        
#         # Set enthalpy
#         if Type == 'T':
#             s.H = -H_s
#         elif Type == 'V':
#             s.enable_phases()
#             s.VLE(Qin=s.H - H_s)
#         elif Type == 'F':
#             s.mol *= (s_out.H - s_in.H)/H_s
#         else:
#             raise ValueError(f"Type must be 'T', 'V' or 'F', not '{Type}'")
            
        
        