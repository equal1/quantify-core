import time
import json
from os.path import join

import numpy as np
from qcodes import Instrument
from qcodes import validators as vals
from qcodes.instrument.parameter import ManualParameter, InstrumentRefParameter
from qcodes.utils.helpers import NumpyJSONEncoder
from quantify.data.handling import initialize_dataset, create_exp_folder, snapshot
from quantify.measurement.types import Settable, Gettable, is_internally_controlled


class MeasurementControl(Instrument):
    """
    Instrument responsible for controling the data acquisition loop.

    MeasurementControl (MC) is based on the notion that every experiment consists of the following step:

        1. Set some parameter(s)            (settable_pars)
        2. Measure some other parameter(s)  (gettable_pars)
        3. Store the data.

    Example:

        .. code-block:: python

            MC.set_setpars(mw_source1.freq)
            MC.set_setpoints(np.arange(5e9, 5.2e9, 100e3))
            MC.set_getpars(pulsar_AQM.signal)
            dataset = MC.run(name='Frequency sweep')


    MC exists to enforce structure on experiments. Enforcing this structure allows:

        - Standardization of data storage.
        - Providing basic real-time visualization.

    MC imposes minimal constraints and allows:

    - Soft loops, experiments in which MC controlled acquisition loop.
    - Hard loops, experiments in which MC is not in control of acquisition.
    - Adaptive loops, setpoints are determined based on measured values.

    """

    def __init__(self, name: str):
        """
        Creates an instance of the Measurement Control.

        Args:
            name (str): name
        """
        super().__init__(name=name)

        # Parameters are attributes that we include in logging and intend the user to change.

        self.add_parameter(
            "verbose",
            docstring="If set to True, prints to std_out during experiments.",
            parameter_class=ManualParameter,
            vals=vals.Bool(),
            initial_value=True,
        )

        self.add_parameter(
            "on_progress_callback",
            vals=vals.Callable(),
            docstring="A callback to communicate progress. This should be a "
            "Callable accepting ints between 0 and 100 indicating percdone.",
            parameter_class=ManualParameter,
            initial_value=None,
        )

        self.add_parameter(
            "soft_avg",
            label="Number of soft averages",
            parameter_class=ManualParameter,
            vals=vals.Ints(1, int(1e8)),
            initial_value=1,
        )

        self.add_parameter(
            'instr_plotmon',
            docstring='Instrument responsible for live plotting. '
            'Can be set to str(None) to disable live plotting.',
            parameter_class=InstrumentRefParameter)

        # TODO add update interval functionality.
        self.add_parameter(
            'update_interval',
            initial_value=0.1,
            docstring=(
                'Interval for updates during the data acquisition loop,' +
                ' everytime more than `update_interval` time has elapsed ' +
                'when acquiring new data points, data is written to file ' +
                'and the live monitoring is updated.'),
            parameter_class=ManualParameter,
            vals=vals.Numbers(min_value=0)
        )

        # variables that are set before the start of any experiment.

        # todo remove these notes
        # I feel like setpars and setpoints should be bound together in a tuple
        self._settable_pars = []  # detector_function(s)?
        self._setpoints = []  # sweep points?
        self._gettable_pars = []  # sweep_function(s)?
        # sweep_functions and detector_functions both have 'prepare'&'finish' in pyqed
        # todo remove these notes

        # variables used for book keeping during acquisition loop.
        self._nr_acquired_values = 0
        self._soft_iterations = 0
        self._begintime = time.time()
        self._last_upd = time.time()

        self._plot_info = {}

        self.GETTABLE_IDX = 0  # avoid magic numbers until/if we support multiple Gettables

    ############################################
    # Methods used to control the measurements #
    ############################################

    def run(self, name: str = ''):
        """
        Starts a data acquisition loop.

        Args:
            name (str): Name of the measurement. This name is included in the name of the data files.

        Returns:
            :class:`xarray.Dataset`: the dataset
        """

        # reset all variables that change during acquisition
        self._nr_acquired_values = 0
        self._soft_iterations = 0
        self._begintime = time.time()

        # todo, check for control mismatch

        # initialize an empty dataset
        # todo looks like this isnt taking into account multiple returns from hardware
        dataset = initialize_dataset(self._settable_pars, self._setpoints, self._gettable_pars)

        # cannot add it as a separate (nested) dict so make it flat.
        dataset.attrs['name'] = name
        dataset.attrs.update(self._plot_info)

        exp_folder = create_exp_folder(tuid=dataset.attrs['tuid'], name=dataset.attrs['name'])
        # Write the empty dataset
        dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))
        # Save a snapshot of all
        snap = snapshot(update=False, clean=True)
        with open(join(exp_folder, 'snapshot.json'), 'w') as file:
            json.dump(snap, file, cls=NumpyJSONEncoder, indent=4)

        plotmon_name = self.instr_plotmon()
        if plotmon_name is not None and plotmon_name != '':
            self.instr_plotmon.get_instr().tuid(dataset.attrs['tuid'])
            # if the timestamp has changed, this will initialize the monitor
            self.instr_plotmon.get_instr().update()

        if is_internally_controlled(self._settable_pars[0]) and is_internally_controlled(self._gettable_pars[0]):
            is_internal = True
        elif not is_internally_controlled(self._gettable_pars[0]):
            is_internal = False
        else:
            raise Exception("Control mismatch")  # todo improve

        self._prepare_settables()

        if is_internal:
            self._prepare_gettable()
            for idx, spts in enumerate(self._setpoints):
                # set all individual setparams
                for spar, spt in zip(self._settable_pars, spts):
                    # TODO add smartness to avoid setting if unchanged
                    spar.set(spt)
                # acquire all data points
                for j, gpar in enumerate(self._gettable_pars):
                    val = gpar.get()
                    dataset['y{}'.format(j)].values[idx] = val
                self._nr_acquired_values += 1
                self._update(dataset, plotmon_name, exp_folder)
        else:
            while self._get_fracdone() < 1.0:
                setpoint_idx = self._curr_setpoint_idx()
                for i, spar in enumerate(self._settable_pars):
                    swf_setpoints = self._setpoints[:, i]
                    spar.set(swf_setpoints[setpoint_idx])
                self._prepare_gettable(self._setpoints[setpoint_idx:, self.GETTABLE_IDX])

                new_data = self._gettable_pars[self.GETTABLE_IDX].get()  # can return (N, M)
                # if we get a simple array, shape it to (1, M)
                if len(np.shape(new_data)) == 1:
                    new_data = new_data.reshape(1, (len(new_data)))

                for i, row in enumerate(new_data):
                    old_vals = dataset['y{}'.format(i)].values  # get the full y axes
                    # todo must be a better way of summing nans with reals
                    old_vals[np.isnan(old_vals)] = 0  # will be full of nans on the first iteration, change to 0
                    # row might not be the full axes length, pad either side with 0s
                    padded_row = np.pad(row, [setpoint_idx, len(old_vals) - len(row) - setpoint_idx], "constant")
                    # sum the data vectors together, averaging if required
                    if self.soft_avg() == 1:
                        new_vals = old_vals + padded_row
                    else:
                        new_vals = (padded_row + old_vals * self._soft_iterations) / (1 + self._soft_iterations)
                    dataset['y{}'.format(i)].values = new_vals  # update the dataset
                self._nr_acquired_values += np.shape(new_data)[1]
                self._update(dataset, plotmon_name, exp_folder)

        # Wrap up experiment and store data
        dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))

        self._finish()
        # reset the plot info for the next experiment.
        self._plot_info = {'2D-grid': False}
        # reset software averages back to 1
        self.soft_avg(1)

        return dataset

    ############################################
    # Methods used to control the measurements #
    ############################################

    # Here we do saving, plotting, checking for interrupts etc.
    def _update(self, dataset, plotmon_name, exp_folder):
        update = time.time() - self._last_upd > self.update_interval() or self._nr_acquired_values == len(self._setpoints)
        if update:
            self.print_progress()
            dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))
            if plotmon_name is not None and plotmon_name != '':
                self.instr_plotmon.get_instr().update()
            self._last_upd = time.time()

    def _prepare_gettable(self, setpoints=None):
        try:
            if setpoints is not None:
                self._gettable_pars[self.GETTABLE_IDX].prepare(setpoints)
            else:
                self._gettable_pars[self.GETTABLE_IDX].prepare()
        except AttributeError as e:
            pass

    def _prepare_settables(self):
        for setpar in self._settable_pars:
            try:
                setpar.prepare()
            except AttributeError as e:
                pass

    def _finish(self):
        try:
            for p in self._gettable_pars and self._settable_pars:
                p.finish()
        except AttributeError as e:
            pass

    def _max_setpoints(self):
        return len(self._setpoints) * self.soft_avg()

    def _curr_setpoint_idx(self):
        """
        Returns the current position through the sweep
        Updates the _soft_iterations counter as it may have rolled over

        Returns:
            int: setpoint_idx
        """
        acquired = self._nr_acquired_values
        setpoint_idx = acquired % len(self._setpoints)
        self._soft_iterations = acquired // len(self._setpoints)
        return setpoint_idx

    def _get_fracdone(self):
        """
        Returns the fraction of the experiment that is completed.
        """
        return self._nr_acquired_values / self._max_setpoints()

    def print_progress(self):
        percdone = self._get_fracdone()*100
        elapsed_time = time.time() - self._begintime
        progress_message = (
            "\r {percdone}% completed \telapsed time: "
            "{t_elapsed}s \ttime left: {t_left}s".format(
                percdone=int(percdone),
                t_elapsed=round(elapsed_time, 1),
                t_left=round((100.0 - percdone) / percdone * elapsed_time, 1)
                if percdone != 0
                else "",
            )
        )
        if self.on_progress_callback() is not None:
            self.on_progress_callback()(percdone)
        if percdone != 100:
            end_char = ""
        else:
            end_char = "\n"
        if self.verbose():
            print("\r", progress_message, end=end_char)

    ####################################
    # Non-parameter get/set functions  #
    ####################################

    def set_setpars(self, settable_pars):
        """
        Define the settable parameters for the acquisition loop.

        Args:
            settable_pars: parameter(s) to be set during the acquisition loop, accepts:
                - list or tuple of multiple Settable objects
                - a single Settable object.

        The :class:`~quantify.measurement.Settable` helper class defines the requirements for a Settable object.
        """
        # for native nD compatibility we treat this like a list of settables.
        if not isinstance(settable_pars, (list, tuple)):
            settable_pars = [settable_pars]

        self._settable_pars = []
        for _, settable in enumerate(settable_pars):
            self._settable_pars.append(Settable(settable))

    def set_setpoints(self, setpoints):
        """
        Set setpoints that determine values to be set in acquisition loop.

        Args: setpoints (:class:`numpy.ndarray`) : An array that defines the values to loop over in the experiment.
        The shape of the array has to be either (N,) (N,1) for a 1D loop or (N, M) in the case of an MD loop.

        The setpoints are internally reshaped to (N, M) to be natively compatible with M-dimensional loops.

        .. tip::

            Use :code:`np.colstack((x0, x1))` to reshape multiple
            1D arrays when setting multiple setables.
        """
        if len(np.shape(setpoints)) == 1:
            setpoints = setpoints.reshape((len(setpoints), 1))
        self._setpoints = setpoints

        # set to False whenever new setpoints are defined.
        # this gets updated after calling set_setpoints_2D.
        self._plot_info['2D-grid'] = False

    def set_setpoints_grid(self, setpoints):
        """
        Set a setpoint grid that determine values to be set in the acquisition loop. Updates the setpoints in a grid
        by repeating the setpoints M times and filling the second column with tiled values.

        Args: setpoints (list(:class:`numpy.ndarray`)) : The values to loop over in the experiment. The grid is
        reshaped in this order.

        Example

            .. code-block:: python

                MC.set_setpars([t, amp])
                MC.set_setpoints_grid([times, amplitudes])
                MC.set_getpars(sig)
                dataset = MC.run('2D grid')
        """
        if len(setpoints) == 2:
            self._plot_info['xlen'] = len(setpoints[0])
            self._plot_info['ylen'] = len(setpoints[1])
            self._plot_info['2D-grid'] = True
        self._setpoints = tile_setpoints_grid(setpoints)

    def set_getpars(self, gettable_par):
        """
        Define the parameters to be acquired during the acquisition loop.

        Args:
            gettable_pars: parameter(s) to be get during the acquisition loop, accepts:
                 - list or tuple of multiple Gettable objects
                 - a single Gettable object

        The :class:`~quantify.measurement.Gettable` helper class defines the requirements for a Gettable object.

        TODO: support fancier getables, i.e. ones that return
            - more than one quantity
            - multiple points at once (hard loop)

        """
        self._gettable_pars = [Gettable(gettable_par)]


def tile_setpoints_grid(setpoints):
    """
    Tile setpoints into an n-dimensional grid.

    Args: setpoints (list(:class:`numpy.ndarray`)): A list of arrays that defines the values to loop over in the
    experiment. The grid is reshaped in this order.

    Returns:
        :class:`numpy.ndarray`: an array with repeated x-values and tiled xn-values.

    .. warning ::

        using this method typecasts all values into the same type. This may lead to validator errors when setting
        e.g., a float instead of an int.
    """
    xn = setpoints[0].reshape((len(setpoints[0]), 1))
    for setpoints_n in setpoints[1:]:
        curr_l = len(xn)
        new_l = len(setpoints_n)
        col_stack = []
        for i in range(0, np.size(xn, 1)):
            col_stack.append(np.tile(xn[:, i], new_l))
        col_stack.append(np.repeat(setpoints_n, curr_l))
        xn = np.column_stack(col_stack)
    return xn
