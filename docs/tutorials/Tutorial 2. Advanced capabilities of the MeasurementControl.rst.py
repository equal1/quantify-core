# ---
# jupyter:
#   jupytext:
#     cell_markers: '"""'
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.13.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
rst_conf = {"jupyter_execute_options": [":hide-code:"]}
# pylint: disable=line-too-long
# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position
# pylint: disable=pointless-string-statement
# pylint: disable=pointless-statement
# pylint: disable=invalid-name
# pylint: disable=duplicate-code
# pylint: disable=no-self-use
# pylint: disable=too-few-public-methods

# %% [raw]
"""
Tutorial 2. Advanced capabilities of the MeasurementControl
============================================================
"""

# %% [raw]
"""
.. seealso::

    The complete source code of this tutorial can be found in

    :jupyter-download:notebook:`Tutorial 2. Advanced capabilities of the MeasurementControl.py`

    :jupyter-download:script:`Tutorial 2. Advanced capabilities of the MeasurementControl.py`
"""


# %% [raw]
"""
Following this Tutorial requires familiarity with the **core concepts** of Quantify, we **highly recommended** to consult the (short) :ref:`User guide` before proceeding (see Quantify documentation). If you have some difficulties following the tutorial it might be worth reviewing the :ref:`User guide`!
"""

# %% [raw]
"""
We **highly recommended** to begin with :ref:`Tutorial 1. Controlling a basic experiment using MeasurementControl` before proceeding.
"""

# %% [raw]
"""
In this tutorial, we will explore the more advanced features of Quantify. By the end of this tutorial, we will have covered:

- Using hardware to drive experiments
- Software averaging
- Interrupting an experiment
"""

# %%
import os
import signal
import sys
import time

import numpy as np
from lmfit import Model
from qcodes import ManualParameter

import quantify_core.visualization.pyqt_plotmon as pqm
from quantify_core.data.handling import set_datadir
from quantify_core.measurement.control import MeasurementControl
from quantify_core.utilities.examples_support import default_datadir
from quantify_core.visualization.instrument_monitor import InstrumentMonitor

rng = np.random.default_rng(seed=222222)  # random number generator

# %matplotlib inline

# %% [raw]
"""
.. include:: /tutorials/set_data_dir_notes.rst.txt
"""


# %%
set_datadir(default_datadir())  # change me!

# %%
meas_ctrl = MeasurementControl("meas_ctrl")
plotmon = pqm.PlotMonitor_pyqt("plotmon_meas_ctrl")
meas_ctrl.instr_plotmon(plotmon.name)
insmon = InstrumentMonitor("Instruments Monitor")

# %% [raw]
"""
A 1D Batched loop: Resonator Spectroscopy
-----------------------------------------
"""

# %% [raw]
"""
Defining a simple model
~~~~~~~~~~~~~~~~~~~~~~~
"""

# %% [raw]
"""
In this example, we want to find the resonance of some device. We expect to find it's resonance somewhere in the low 6 GHz range, but manufacturing imperfections makes it impossible to know exactly without inspection.
"""

# %% [raw]
"""
We first create `freq`: a :class:`.Settable` with a :class:`~qcodes.instrument.parameter.Parameter` to represent the frequency of the signal probing the resonator, followed by a custom :class:`.Gettable` to mock (i.e. emulate) the resonator.
The :class:`!Resonator` will return a Lorentzian shape centered on the resonant frequency. Our :class:`.Gettable` will read the setpoints from `freq`, in this case a 1D array.
"""

# %% [raw]
"""
.. note:: The `Resonator` :class:`.Gettable` has a new attribute `.batched` set to `True`. This property informs the :class:`.MeasurementControl` that it will not be in charge of iterating over the setpoints, instead the `Resonator` manages its own data acquisition. Similarly, the `freq` :class:`.Settable` must have a `.batched=True` so that the :class:`.MeasurementControl` hands over the setpoints correctly.
"""


# %%
# Note that in an actual experimental setup `freq` will be a QCoDeS parameter
# contained in a QCoDeS Instrument
freq = ManualParameter(name="frequency", unit="Hz", label="Frequency")
freq.batched = True  # Tells meas_ctrl that the setpoints are to be passed in batches


def lorenz(amplitude: float, fwhm: float, x: int, x_0: float):
    """Model of the frequency response."""
    return amplitude * ((fwhm / 2.0) ** 2) / ((x - x_0) ** 2 + (fwhm / 2.0) ** 2)


class Resonator:
    """
    Note that the Resonator is a valid Gettable not because of inheritance,
    but because it has the expected attributes and methods.
    """

    def __init__(self) -> None:
        self.name = "resonator"
        self.unit = "V"
        self.label = "Amplitude"
        self.batched = True
        self.delay = 0.0

        # hidden variables specifying the resonance
        self._test_resonance = 6.0001048e9  # in Hz
        self._test_width = 300  # FWHM in Hz

    def get(self) -> float:
        """Emulation of the frequency response."""
        time.sleep(self.delay)
        _lorenz = lambda x: lorenz(1, self._test_width, x, self._test_resonance)
        return 1 - np.array(list(map(_lorenz, freq())))

    def prepare(self) -> None:
        """Adding this print statement is not required but added for illustrative
        purposes."""
        print("\nPrepared Resonator...")

    def finish(self) -> None:
        """Adding this print statement is not required but added for illustrative
        purposes."""
        print("\nFinished Resonator...")


gettable_res = Resonator()


# %% [raw]
"""
Running the experiment
~~~~~~~~~~~~~~~~~~~~~~
"""

# %% [raw]
"""
Just like our Iterative 1D loop, our complete experiment is expressed in just four lines of code.
"""

# %% [raw]
"""
The main difference is defining the `batched` property of our :class:`.Gettable` to `True`.
The :class:`.MeasurementControl` will detect these settings and run in the appropriate mode.
"""


# %%
# At this point the `freq` parameter is empty
print(freq())


# %%
meas_ctrl.settables(freq)
meas_ctrl.setpoints(np.arange(6.0001e9, 6.00011e9, 5))
meas_ctrl.gettables(gettable_res)
dset = meas_ctrl.run()


# %%
plotmon.main_QtPlot

# %% [raw]
"""
As expected, we find a Lorentzian spike in the readout at the resonant frequency, finding the peak of which is trivial.
"""


# %% [raw]
"""
Memory-limited Settables/Gettables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
"""

# %% [raw]
"""
Instruments (either physical or virtual) operating in `batched` mode have an upper limit on how many datapoints can be processed at once.
When an experiment is comprised of more datapoints than the instrument can handle, the :class:`.MeasurementControl` takes care of fulfilling the measurement of all the requested setpoints by running and internal loop.
"""

# %% [raw]
"""
By default the :class:`.MeasurementControl` assumes no limitations and passes all setpoints to the `batched` settable. However, as a best practice, the instrument limitation must be reflected by the `.batch_size` attribute of the `batched` settables. This is illustrated below.
"""

# %%
# Tells meas_ctrl that only 256 datapoints can be processed at once
freq.batch_size = 256

gettable_res.delay = 0.05  # short delay for plotting
meas_ctrl.settables(freq)
meas_ctrl.setpoints(np.arange(6.0001e9, 6.00011e9, 5))
meas_ctrl.gettables(gettable_res)
dset = meas_ctrl.run()

# %%
plotmon.main_QtPlot

# %% [raw]
"""
Software Averaging: T1 Experiment
---------------------------------
"""

# %% [raw]
"""
In many cases it is desirable to run an experiment many times and average the result, such as when filtering noise on instruments or measuring probability.
For this purpose, the :meth:`.MeasurementControl.run` provides the `soft_avg` argument.
If set to *x*, the experiment will run *x* times whilst performing a running average over each setpoint.
"""

# %% [raw]
"""
In this example, we want to find the relaxation time (aka T1) of a Qubit. As before, we define a :class:`.Settable` and :class:`.Gettable`, representing the varying timescales we will probe through and a mock Qubit emulated in software.
The mock Qubit returns the expected decay sweep but with a small amount of noise (simulating the variable qubit characteristics). We set the qubit's T1 to 60 ms - obviously in a real experiment we would be trying to determine this, but for this illustration purposes in this tutorial we set it to a known value to verify our fit later on.
"""

# %% [raw]
"""
Note that in this example meas_ctrl is still running in Batched mode.
"""


# %%
def decay(t, tau):
    """T1 experiment decay model."""
    return np.exp(-t / tau)


time_par = ManualParameter(name="time", unit="s", label="Measurement Time")
# Tells meas_ctrl that the setpoints are to be passed in batches
time_par.batched = True


class MockQubit:
    """A mock qubit."""

    def __init__(self):
        self.name = "qubit"
        self.unit = "%"
        self.label = "High V"
        self.batched = True

        self.delay = 0.01  # sleep time in secs
        self.test_relaxation_time = 60e-6

    def get(self):
        """Adds a delay to be able to appreciate the data acquisition."""
        time.sleep(self.delay)
        rel_time = self.test_relaxation_time
        _func = lambda x: decay(x, rel_time) + rng.uniform(-0.1, 0.1)
        return np.array(list(map(_func, time_par())))


# %% [raw]
"""
We will then sweep through 0 to 300 ms, getting our data from the mock Qubit. Let's first observe what a single run looks like:
"""


# %%
meas_ctrl.settables(time_par)
meas_ctrl.setpoints(np.linspace(0.0, 300.0e-6, 300))
meas_ctrl.gettables(MockQubit())
meas_ctrl.run("noisy")  # by default `.run` uses `soft_avg=1`
plotmon.main_QtPlot

# %% [raw]
"""
Alas, the noise in the signal has made this result unusable! Let's set the `soft_avg` argument of the :meth:`.MeasurementControl.run` to 100, averaging the results and hopefully filtering out the noise.
"""

# %%
dset = meas_ctrl.run("averaged", soft_avg=100)
plotmon.main_QtPlot

# %% [raw]
"""
Success! We now have a smooth decay curve based on the characteristics of our qubit. All that remains is to run a fit against the expected values and we can solve for T1.
"""


# %%
model = Model(decay, independent_vars=["t"])
fit_res = model.fit(dset["y0"].values, t=dset["x0"].values, tau=1)

fit_res.plot_fit(show_init=True)
fit_res.values


# %% [raw]
"""
Interrupting
------------
"""

# %% [raw]
"""
Sometimes experiments unfortunately do not go as planned and it is desirable to interrupt and restart them with new parameters. In the following example, we have a long running experiment where our Gettable is taking a long time to return data (maybe due to misconfiguration).
Rather than waiting for this experiment to complete, instead we can interrupt any :class:`.MeasurementControl` loop using the standard interrupt signal.
In a terminal environment this is usually achieved with a ``ctrl`` + ``c`` press on the keyboard or equivalent, whilst in a Jupyter environment interrupting the kernel (stop button) will cause the same result.
"""

# %% [raw]
"""
When the :class:`.MeasurementControl` is interrupted, it will wait to obtain the results of current iteration (or batch) and perform a final save of the data it has gathered, call the `finish()` method on Settables & Gettables (if it exists) and return the partially completed dataset.
"""

# %% [raw]
"""
.. note::

    The exact means of triggering an interrupt will differ depending on your platform and environment; the important part is to cause a `KeyboardInterrupt` exception to be raised in the Python process.
"""

# %% [raw]
"""
.. warning::

    In case the current iteration is taking too long to complete (e.g. instruments not responding), you may force the execution of any python code to stop by signaling the same interrupt 5 times (e.g. pressing 5 times ``ctrl`` + ``c``). Mind that performing this too fast might result in the `KeyboardInterrupt` not being properly handled and corrupt the dataset!
"""


# %%
rst_conf = {"indent": "    ", "jupyter_execute_options": [":raises: KeyboardInterrupt"]}


class SlowGettable:
    """A mock slow gettables."""

    def __init__(self):
        self.name = "slow"
        self.label = "Amplitude"
        self.unit = "V"

    def get(self):
        """Get method."""
        time.sleep(1.0)
        if time_par() == 4:
            # This same exception rises when pressing `ctrl` + `c`
            # or the "Stop kernel" button is pressed in a Jupyter(Lab) notebook
            if sys.platform == "win32":
                # Emulating the kernel interrupt on windows might have side effects
                raise KeyboardInterrupt
            os.kill(os.getpid(), signal.SIGINT)
        return time_par()


time_par.batched = False
meas_ctrl.settables(time_par)
meas_ctrl.setpoints(np.arange(10))
meas_ctrl.gettables(SlowGettable())
# Try interrupting me!
dset = meas_ctrl.run("slow")


# %%
plotmon.main_QtPlot
