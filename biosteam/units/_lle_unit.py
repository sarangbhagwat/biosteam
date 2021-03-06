# -*- coding: utf-8 -*-
# BioSTEAM: The Biorefinery Simulation and Techno-Economic Analysis Modules
# Copyright (C) 2020, Yoel Cortes-Pena <yoelcortes@gmail.com>
# 
# This module is under the UIUC open-source license. See 
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.
"""
"""
import biosteam as bst
from thermosteam import separations

__all__ = ('LLEUnit',)

class LLEUnit(bst.Unit, isabstract=True):
    r"""
    Abstract class for simulating liquid-liquid equilibrium.

    Parameters
    ----------
    ins : stream
        Inlet fluid.
    outs : stream sequence
        * [0] 'liquid' phase fluid
        * [1] 'LIQUID' phase fluid
    top_chemical : str, optional
        Identifier of chemical that will be favored in the "liquid" phase.
        If none given, the "liquid" phase will the lightest and the "LIQUID"
        phase will be the heaviest.
    efficiency=1. : float, optional
        Fraction of feed in liquid-liquid equilibrium.
        The rest of the feed is divided equally between phases.
    cache_tolerance=1e-6 : float, optional
        Reuse previous partition coefficients to calculate LLE when 
        the change in molar fraction of all chemicals is below this 
        tolerance.
    forced_split_IDs : tuple[str], optional
        IDs of component with a user defined split.
    forced_split : 1d array, optional
        Component-wise split to 0th stream.
    
    Examples
    --------
    >>> from biorefineries.lipidcane import chemicals
    >>> from biosteam import units, settings, Stream
    >>> settings.set_thermo(chemicals)
    >>> feed = Stream('feed', T=333.15,
    ...               Lipid=0.996, Biodiesel=26.9,
    ...               Methanol=32.9, Glycerol=8.97)
    >>> C1 = units.LLEUnit('C1', ins=feed, outs=('light', 'heavy'))
    >>> C1.simulate()
    >>> C1.show()
    LLEUnit: C1
    ins...
    [0] feed
        phase: 'l', T: 333.15 K, P: 101325 Pa
        flow (kmol/hr): Methanol   32.9
                        Glycerol   8.97
                        Biodiesel  26.9
                        Lipid      0.996
    outs...
    [0] light
        phase: 'l', T: 333.15 K, P: 101325 Pa
        flow (kmol/hr): Methanol   10.2
                        Glycerol   0.0239
                        Biodiesel  26.9
                        Lipid      0.996
    [1] heavy
        phase: 'l', T: 333.15 K, P: 101325 Pa
        flow (kmol/hr): Methanol   22.7
                        Glycerol   8.95
                        Biodiesel  0.0031
    
    """
    _N_outs = 2
    
    def __init__(self, ID='', ins=None, outs=(), thermo=None,
                 top_chemical=None, efficiency=1.0, cache_tolerance=1e-6,
                 forced_split_IDs=None, forced_split=None):
        bst.Unit.__init__(self, ID, ins, outs, thermo)
        #: [str] Identifier of chemical that will be favored in the "liquid" phase.
        #: If none given, the "liquid" phase will the lightest and the "LIQUID"
        #: phase will be the heaviest.
        self.top_chemical = top_chemical
        #: [float] Fraction of feed in liquid-liquid equilibrium.
        #: The rest of the feed is divided equally between phases.
        self.efficiency = efficiency 
        #: [float] The change in molar fraction of individual chemicals must be 
        #: below this tolerance to reuse partition coefficients.
        self.cache_tolerance = cache_tolerance
        #: array[float] Forced splits to 0th stream for given IDs. 
        self.forced_split = forced_split
        #: tuple[str] IDs corresponding to forced splits. 
        self.forced_split_IDs = forced_split_IDs
        self.multi_stream = bst.MultiStream(phases='lL', thermo=self.thermo)
        
    def _run(self):
        separations.lle(*self.ins, *self.outs, self.top_chemical, self.efficiency, self.multi_stream)
        IDs = self.forced_split_IDs
        if IDs:
            feed, = self.ins
            liquid, LIQUID = self.outs
            mol = feed.imol[IDs]
            liquid.imol[IDs] = mol_liquid = mol * self.forced_split
            LIQUID.imol[IDs] = mol - mol_liquid
            
