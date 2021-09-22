# pylint: disable=line-too-long
# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position
# pylint: disable=pointless-string-statement

# ---
# jupyter:
#   jupytext:
#     cell_markers: '"""'
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.12.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
# %load_ext autoreload
# %autoreload 1
# %aimport quantify_core.data.dataset_attrs
# %aimport quantify_core.data.dataset_adapters
# %aimport quantify_core.utilities.examples_support

# %% [raw]
"""
.. _dataset-spec:

Quantify dataset specification
==============================

.. seealso::

    The complete source code of this tutorial can be found in

    :jupyter-download:notebook:`Quantify dataset - specification`

    :jupyter-download:script:`Quantify dataset - specification`
"""

# %% [raw]
"""
.. admonition:: Imports and auxiliary utilities
    :class: dropdown
"""

# %%
# rst-json-conf: {"indent": "    ", "jupyter_execute_options": [":hide-output:"]}

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from quantify_core.data import handling as dh
from quantify_core.measurement import grid_setpoints
from qcodes import ManualParameter
from rich import pretty
from pathlib import Path
from quantify_core.data.handling import get_datadir, set_datadir
import quantify_core.data.dataset_attrs as dd
import quantify_core.data.dataset_adapters as da
from quantify_core.utilities.examples_support import (
    mk_dataset_attrs,
    mk_exp_coord_attrs,
    mk_cal_coord_attrs,
    mk_exp_var_attrs,
    mk_cal_var_attrs,
    round_trip_dataset,
    par_to_attrs,
)

from typing import List, Tuple

from importlib import reload

pretty.install()

set_datadir(Path.home() / "quantify-data")  # change me!

# %% [raw]
"""
This document describes the Quantify dataset specification.
Here we focus on the concepts and terminology specific to the Quantify dataset.
It is based on the Xarray dataset, hence, we assume basic familiarity with the :class:`xarray.Dataset`.
If you are not familiar with it, we highly recommend to first have a look at our :ref:`xarray-intro` for a brief overview.
"""

# %% [raw]
"""
.. _sec-experiment-coordinates-and-variables:

Coordinates and Variables
-------------------------

The Quantify dataset is an xarray dataset that follows certain conventions. We define "subtypes" of xarray coordinates and variables:

.. _sec-experiment-coordinates:

Experiment coordinate(s)
^^^^^^^^^^^^^^^^^^^^^^^^

- Xarray **Coordinates** that have an attribute :attr:`~quantify_core.data.dataset_attrs.QCoordAttrs.is_experiment_coord` set to ``True``.
- Often correspond to physical coordinates, e.g., a signal frequency or amplitude.
- Often correspond to quantities set through :class:`~quantify_core.measurement.Settable`\s.
- See also :func:`~quantify_core.data.dataset_attrs.get_experiment_coords`.

.. _sec-calibration-coordinates:

Calibration coordinate(s)
^^^^^^^^^^^^^^^^^^^^^^^^^

- Similar to `experiment coordinates <sec-experiment-coordinates>`_\, but intended to serve as the coordinates of `calibration variables <sec-calibration-variables>`_\.
- Xarray **Coordinates** that have an attribute :attr:`~quantify_core.data.dataset_attrs.QCoordAttrs.is_calibration_coord` set to ``True``.
- See also :func:`~quantify_core.data.dataset_attrs.get_calibration_coords`.

.. _sec-experiment-variables:

Experiment variable(s)
^^^^^^^^^^^^^^^^^^^^^^

- Xarray **Variables** that have an attribute :attr:`~quantify_core.data.dataset_attrs.QVarAttrs.is_experiment_var` set to ``True``.
- Must have an attribute :attr:`~quantify_core.data.dataset_attrs.QVarAttrs.experiment_coords` indicating the names of its 'physical' coordinates. This ensures that the experiment coordinates of an experiment variables can be determined with no ambiguity.

    - Example: If a signal ``y1`` was measured as a function of ``time`` and ``amplitude`` experiment coordinates, then we will have ``y1.attrs["experiment_coords"] = ["time", "amplitude"]``.

- Often correspond to a physical quantity being measured, e.g., the signal magnitude at a specific frequency measured on a metal contact of a quantum chip.
- Often correspond to quantities returned by :class:`~quantify_core.measurement.Gettable`\s.
- See also :func:`~quantify_core.data.dataset_attrs.get_experiment_vars`.

.. _sec-calibration-variables:

Calibration variables(s)
^^^^^^^^^^^^^^^^^^^^^^^^

- Similar to `experiment variables <sec-experiment-variables>`_, but intended to serve as calibration data for other experiment variables.
- Xarray **Variables** that have an attribute :attr:`~quantify_core.data.dataset_attrs.QVarAttrs.is_calibration_var` set to ``True``.
- The "assignment" of calibration variables to experiment variables should be done using :attr:`~quantify_core.data.dataset_attrs.QDatasetAttrs.relationships`.
- See also :func:`~quantify_core.data.dataset_attrs.get_calibration_vars`.


.. note::

    In this document we show exemplary datasets to highlight the details of the Quantify dataset specification.
    However, for completeness, we always show a valid Quantify dataset with all the required properties.

In order to follow the rest of this specification more easily have a look at the example below.
It should give you a more concrete feeling of the details that are exposed afterwards.
"""

# %% [raw]
"""
.. admonition:: Generate dataset
    :class: dropdown
"""

# %%
# rst-json-conf: {"indent": "    "}

x0s = np.linspace(0.45, 0.55, 30)
x1s = np.linspace(0, 100e-9, 40)
time_par = ManualParameter(name="time", label="Time", unit="s")
amp_par = ManualParameter(name="amp", label="Flux amplitude", unit="V")
pop_q0_par = ManualParameter(name="pop_q0", label="Population Q0", unit="arb. unit")
pop_q1_par = ManualParameter(name="pop_q1", label="Population Q1", unit="arb. unit")

x0s, x1s = grid_setpoints([x0s, x1s], [amp_par, time_par]).T
x0s_norm = np.abs((x0s - x0s.mean()) / (x0s - x0s.mean()).max())
y0s = (1 - x0s_norm) * np.sin(
    2 * np.pi * x1s * 1 / 30e-9 * (x0s_norm + 0.5)
)  # ~chevron
y1s = -y0s  # mock inverted population for q1

y0s = y0s / 2 + 0.5  # shift to 0-1 range
y1s = y1s / 2 + 0.5

dataset = dataset_2d_example = xr.Dataset(
    data_vars={
        pop_q0_par.name: (
            ("repetitions", "dim_0"),
            [y0s + y0s * np.random.uniform(-1, 1, y0s.shape) / k for k in (100, 10, 5)],
            mk_exp_var_attrs(
                **par_to_attrs(pop_q0_par),
                experiment_coords=[amp_par.name, time_par.name]
            ),
        ),
        pop_q1_par.name: (
            ("repetitions", "dim_0"),
            [y1s + y1s * np.random.uniform(-1, 1, y1s.shape) / k for k in (100, 10, 5)],
            mk_exp_var_attrs(
                **par_to_attrs(pop_q1_par),
                experiment_coords=[amp_par.name, time_par.name]
            ),
        ),
    },
    coords={
        amp_par.name: ("dim_0", x0s, mk_exp_coord_attrs(**par_to_attrs(amp_par))),
        time_par.name: ("dim_0", x1s, mk_exp_coord_attrs(**par_to_attrs(time_par))),
    },
    attrs=mk_dataset_attrs(main_dims=["dim_0"], repetitions_dims=["repetitions"]),
)

assert dataset == round_trip_dataset(dataset)  # confirm read/write

# %% [raw]
"""
.. admonition:: Quantify dataset: 2D example
    :class: dropdown, toggle-shown

    In the dataset below we have two experiment coordinates ``amp`` and ``time``; and two experiment variables ``pop_q0`` and ``pop_q1``.
    Both experiment coordinates "lie" along a single xarray dimension, ``dim_0``.
    Both experiment variables lie along two xarray dimensions ``dim_0`` and ``repetitions``.
"""

# %%
# rst-json-conf: {"indent": "    "}

dataset

# %% [raw]
"""
    As seen above, in the Quantify dataset the experiment coordinates do not index the experiment variables because not all use-cases fit within this paradigm.
    However, when possible, the Quantify dataset can be reshaped to take advantage of the xarray built-in utilities. Note, however, that this reshaping will produce an xarray dataset that does not comply with the Quantify dataset specification.
"""

# %%
# rst-json-conf: {"indent": "    "}

dataset_gridded = dh.to_gridded_dataset(
    dataset_2d_example,
    dimension=dd.get_main_dims(dataset_2d_example)[0],
    coords_names=dd.get_experiment_coords(dataset_2d_example),
)
dataset_gridded.pop_q0.plot.pcolormesh(x="amp", col=dataset_gridded.pop_q0.dims[0])
_ = dataset_gridded.pop_q1.plot.pcolormesh(x="amp", col=dataset_gridded.pop_q1.dims[0])

# %% [raw]
"""
Dimensions
----------
"""

# %% [raw]
"""
The experiment variables and coordinates present in a Quantify dataset have the following required and optional xarray dimensions:

.. _sec-repetitions-dimensions:

Repetitions dimension(s) [Optional]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Repetition dimensions comply with the following:

- Any dimensions present in the dataset that are listed in the :attr:`QDatasetAttrs.repetitions_dims <quantify_core.data.dataset_attrs.QDatasetAttrs.repetitions_dims>` dataset attribute.
- Intuition for these xarray dimension: the equivalent would be to have ``dataset_reptition_0.hdf5``, ``dataset_reptition_1.hdf5``, etc. where each dataset was obtained from repeating exactly the same experiment. Instead we define an outer dimension for this.
- Default behavior of plotting tools will be to average the experiment variables along these dimensions.
- Can be the outermost dimension of :ref:`experiment (and calibration) variables <sec-experiment-coordinates-and-variables>`.
- The :ref:`experiment variables <sec-experiment-coordinates-and-variables>` can lie along one (and only one) repetition dimension.

Main experiment dimension(s) [Required]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The main experiment dimensions comply with the following:

- The outermost dimension of any experiment coordinate/variable, OR the second outermost dimension if the outermost one is a `repetitions dimension <sec-repetitions-dimensions>`_.
- Do not require to be explicitly specified in any metadata attributes, instead utilities for extracting them are provided. See :func:`~quantify_core.data.dataset_attrs.get_main_dims` which simply applies the rule above while inspecting all the experiment coordinates and variables present in the dataset.
- The dataset must have at least one main dimension.

.. admonition:: Note on nesting main dimensions

    Nesting main experiment dimensions is allowed in principle and such examples are
    provided but it should be considered an experimental feature.

    - Intuition: intended primarily for time series, also known as "time trace" or simply trace.
    - E.g., **each entry** a ``y3`` experiment variable corresponds to a one-microsecond-long digitized signal which later is processed to extract its frequencies.


Main calibration dimension(s) [Optional]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Equivalent to the main dimensions but used by the calibration coordinates and variables.
The calibration dimensions comply with the following:

- The outermost dimension of any calibration coordinate/variable, OR the second outermost dimension if the outermost one is a `repetitions dimension <sec-repetitions-dimensions>`_.
- Do not require to be explicitly specified in any metadata attributes, instead utilities for extracting them are provided. See :func:`~quantify_core.data.dataset_attrs.get_main_calibration_dims` which simply applies the rule above while inspecting all the calibration coordinates and variables present in the dataset.
"""

# %% [raw]
"""
.. admonition:: Examples datasets with repetition
    :class: dropdown

    As shown in the :ref:`xarray-intro` an xarray dimension can be indexed by a ``coordinate`` variable. In this example the ``repetitions`` dimension is indexed by the ``repetitions`` xarray coordinate variable:
"""

# %%
# rst-json-conf: {"indent": "    "}

dataset = xr.Dataset(
    data_vars={
        pop_q0_par.name: (
            ("repetitions", "dim_0"),
            [y0s + np.random.random(y0s.shape) / k for k in (100, 10, 5)],
            mk_exp_var_attrs(
                **par_to_attrs(pop_q0_par),
                experiment_coords=[amp_par.name, time_par.name]
            ),
        ),
        pop_q1_par.name: (
            ("repetitions", "dim_0"),
            [y1s + np.random.random(y1s.shape) / k for k in (100, 10, 5)],
            mk_exp_var_attrs(
                **par_to_attrs(pop_q1_par),
                experiment_coords=[amp_par.name, time_par.name]
            ),
        ),
    },
    coords={
        amp_par.name: ("dim_0", x0s, mk_exp_coord_attrs(**par_to_attrs(amp_par))),
        time_par.name: ("dim_0", x1s, mk_exp_coord_attrs(**par_to_attrs(time_par))),
        # here we choose to index the repetition dimension with an array of strings
        "repetitions": (
            "repetitions",
            ["noisy", "very noisy", "very very noisy"],
        ),
    },
    attrs=mk_dataset_attrs(repetitions_dims=["repetitions"]),
)

assert dataset == round_trip_dataset(dataset)  # confirm read/write

dataset

# %% [raw]
"""
    And as before, we can reshape the dataset to take advantage of the xarray builtin utilities.
"""

# %%
# rst-json-conf: {"indent": "    "}

dataset_gridded = dh.to_gridded_dataset(
    dataset,
    dimension=dd.get_main_dims(dataset)[0],
    coords_names=dd.get_experiment_coords(dataset),
)
dataset_gridded

# %% [raw]
"""
    It is now possible to retrieve (select) a specific entry along the ``repetitions`` dimension:
"""

# %%
# rst-json-conf: {"indent": "    "}

_ = dataset_gridded.pop_q0.sel(repetitions="very noisy").plot(x="amp")

# %% [raw]
"""
Dataset attributes
------------------

The mandatory attributes of the Quantify dataset are defined by the following dataclass.
It can be used to generate a default dictionary that is attached to a dataset under the :attr:`xarray.Dataset.attrs` attribute.

.. autoclass:: quantify_core.data.dataset_attrs.QDatasetAttrs
    :members:
    :noindex:
    :show-inheritance:

Additionally in order to express relationships between coordinates and/or variables the
the following template is provided:

.. autoclass:: quantify_core.data.dataset_attrs.QDatasetIntraRelationship
    :members:
    :noindex:
    :show-inheritance:
"""

# %%
from quantify_core.data.dataset_attrs import QDatasetAttrs

# tip: to_json and from_dict, from_json  are also available
dataset_2d_example.attrs = QDatasetAttrs().to_dict()
dataset_2d_example.attrs

# %% [raw]
"""
.. tip::

    Note that xarray automatically provides the attributes as python attributes:
"""

# %%
# rst-json-conf: {"indent": "    "}

dataset_2d_example.quantify_dataset_version, dataset_2d_example.tuid

# %% [raw]
"""
Experiment coordinates and variables attributes
-----------------------------------------------

Similar to the dataset attributes (:attr:`xarray.Dataset.attrs`), the experiment coordinates and variables have each their own mandatory attributes attached to them as dictionary under the :attr:`xarray.DataArray.attrs` attribute.
"""

# %% [raw]
"""
.. autoclass:: quantify_core.data.dataset_attrs.QCoordAttrs
    :members:
    :noindex:
    :show-inheritance:
"""

# %%
dataset_2d_example.amp.attrs


# %% [raw]
"""
.. autoclass:: quantify_core.data.dataset_attrs.QVarAttrs
    :members:
    :noindex:
    :show-inheritance:
"""

# %%
dataset_2d_example.pop_q0.attrs

# %% [raw]
"""
Storage format
--------------

The Quantify dataset is written to disk and loaded back making use of xarray-supported facilities.
Internally we write/load to/from disk using:
"""

# %%
# rst-json-conf: {"jupyter_execute_options": [":hide-code:"]}

import inspect
from IPython.display import Code

Code(inspect.getsource(dh.write_dataset), language="python")

# %%
# rst-json-conf: {"jupyter_execute_options": [":hide-code:"]}

Code(inspect.getsource(dh.load_dataset), language="python")

# %% [raw]
"""
Note that we use the ``h5netcdf`` engine that is more permissive than the default NetCDF engine to accommodate for arrays of complex numbers type.

.. note::

    Furthermore, in order to support a variety of attribute types (e.g. the `None` type) and shapes (e.g. nested dictionaries) in a seamless dataset round trip, some additional tooling is required. See source codes below.
"""

# %%
Code(inspect.getsource(da.AdapterH5NetCDF), language="python")
