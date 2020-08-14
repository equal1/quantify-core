"""
-----------------------------------------------------------------------------
Description:    General utilities.
Repository:     https://gitlab.com/qblox/packages/software/quantify/
Copyright (C) Qblox BV (2020)
-----------------------------------------------------------------------------
"""
from qcodes import Instrument
from quantify.data.types import TUID
from quantify.data.handling import load_snapshot


def load_settings_onto_instrument(instrument: Instrument, tuid: TUID, datadir: str = None):
    """
    Loads settings from a previous experiment onto a current :class:`~qcodes.Instrument`. This information as taken
    from the 'snapshot.json' file in the provided experiment directory.

    Args:
        instrument (:class:`~qcodes.Instrument`): the instrument to configure
        tuid (:class:`~quantify.data.types.TUID`): the TUID of the experiment
        datadir (str): path of the data directory. If `None`, uses `get_datadir()` to determine the data directory.

    Raises:
    """
    instruments = load_snapshot(tuid, datadir)['instruments']
    if instrument.name not in instruments:
        raise ValueError('Instrument "{}" not found in snapshot {}:{}'.format(instrument.name, datadir, tuid))
    for parname, par in instruments[instrument.name]["parameters"].items():
        val = par["value"]
        if val:  # qcodes doesn't like setting to none
            instrument.set(parname, par["value"])
