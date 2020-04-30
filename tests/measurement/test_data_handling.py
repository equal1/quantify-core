import os
import pytest
import xarray as xr
import numpy as np
import quantify.measurement.data_handling as dh
from datetime import datetime
from qcodes import ManualParameter
import quantify

test_datadir = os.path.join(os.path.split(
    quantify.__file__)[0], '..', 'tests', 'data')


def test_is_valid_dset():

    test_dset = xr.Dataset()
    assert dh.is_valid_dset(test_dset)


def test_gen_tuid():

    ts = datetime.now()

    tuid = dh.gen_tuid(ts)

    readable_ts = ts.strftime('%Y%m%d-%H%M%S')

    assert tuid[:15] == readable_ts
    assert len(tuid) == 22  # 6 random characters added at the end of tuid


def test_initialize_dataset():

    setpar = ManualParameter('x', unit='m', label='X position')
    getpar = ManualParameter('y', unit='V', label='Signal amplitude')
    setable_pars = [setpar]
    setpoints = np.arange(0, 100, 32)
    setpoints = setpoints.reshape((len(setpoints), 1))

    getable_pars = [getpar]
    dataset = dh.initialize_dataset(setable_pars, setpoints, getable_pars)

    assert isinstance(dataset, xr.Dataset)
    assert len(dataset.data_vars) == 2
    assert dataset.attrs.keys() == {'tuid'}
    assert dataset.variables.keys() == {'x0', 'y0'}

    x0 = dataset['x0']
    assert isinstance(x0, xr.DataArray)
    assert x0.attrs['unit'] == 'm'
    assert x0.attrs['name'] == 'x'
    assert x0.attrs['long_name'] == 'X position'

    y0 = dataset['y0']
    assert isinstance(y0, xr.DataArray)
    assert y0.attrs['unit'] == 'V'
    assert y0.attrs['name'] == 'y'
    assert y0.attrs['long_name'] == 'Signal amplitude'


def test_getset_datadir():
    # here to ensure we always start with default datadir
    dh.set_datadir(None)

    default_datadir = dh.get_datadir()
    dd = os.path.split(default_datadir)
    assert dd[-1] == 'data'
    assert os.path.split(dd[-2])[-1] == 'quantify'

    dh.set_datadir('my_ddir')
    assert dh.get_datadir() == 'my_ddir'

    # Test resetting to default
    dh.set_datadir(None)
    assert dh.get_datadir() == default_datadir


def test_load_dataset():
    dh.set_datadir(test_datadir)
    tuid = '20200430-170837-315f36'
    dataset = dh.load_dataset(tuid=tuid)
    assert dataset.attrs['tuid'] == tuid

    tuid_short = '20200430-170837'
    dataset = dh.load_dataset(tuid=tuid_short)
    assert dataset.attrs['tuid'] == tuid

    with pytest.raises(FileNotFoundError):
        tuid = '20200430-170837-3b5f36'
        dh.load_dataset(tuid=tuid)

    with pytest.raises(FileNotFoundError):
        tuid = '20200230-170837'
        dh.load_dataset(tuid=tuid)

