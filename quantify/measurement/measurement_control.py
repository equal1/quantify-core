import numpy as np
import time
import json
from os.path import join
from qcodes import Instrument
from quantify.data.data_handling import initialize_dataset, \
    create_exp_folder, snapshot
from qcodes.instrument.parameter import ManualParameter, InstrumentRefParameter
from qcodes import validators as vals
from qcodes.utils.helpers import NumpyJSONEncoder


class MeasurementControl(Instrument):
    """
    Instrument responsible for controling the data acquisition loop.

    MeasurementControl (MC) is based on the notion that every experiment
    consists of the following step.

        1. Set some parameter(s)            (setable_pars)
        2. Measure some other parameter(s)  (getable_pars)
        3. Store the data.

    Example:

        .. code-block:: python

            MC.set_setpars(mw_source1.freq)
            MC.set_setpoints(np.arange(5e9, 5.2e9, 100e3))
            MC.set_getpars(pulsar_AQM.signal)
            dataset = MC.run(name='Frequency sweep')


    MC exists to enforce structure on experiments.
    Enforcing this structure allows

        - Standardization of data storage.
        - Providing basic real-time visualization.

    MC imposes minimal constraints and allows

    - Soft loops, experiments in which MC controlled acquisition loop.
    - Hard loops, experiments in which MC is not in control of acquisition.
    - Adaptive loops, setpoints are determined based on measured values.

    """

    def __init__(
            self,
            name: str):  # verbose: bool = True
        """
        Creates an instance of the Measurement Control.

        Args:
            name (str): name
        """
        super().__init__(name=name)

        # Paramaters are attributes that we include in logging
        # and intend the user to change.

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

        # variables that are set before the start
        # of any experiment.
        self._setable_pars = []
        self._setpoints = []
        self._getable_pars = []

        # Variables used for book keeping during acquisition loop.
        self._nr_acquired_values = 0
        self._begintime = time.time()
        self._last_upd = time.time()

        self._plot_info = {}

    ############################################
    # Methods used to control the measurements #
    ############################################

    def run(self, name: str = '',
            mode: str = '1D'):
        """
        Starts a data acquisition loop.

        Args:
            name (string):
                Name of the measurement. This name is included in the
                name of the data files.
            mode (str):
                Measurement mode. Can '1D', '2D', or 'adaptive'.

        Returns:
            dataset : an xarray Dataset object.
        """

        #######################################################
        # Reset all variables that change during acquisition
        self._nr_acquired_values = 0
        self._begintime = time.time()

        # initialize an empty dataset

        dataset = initialize_dataset(self._setable_pars,
                                     self._setpoints,
                                     self._getable_pars)

        # cannot add it as a separte (nested) dict so make it flat.
        dataset.attrs['name'] = name
        dataset.attrs.update(self._plot_info)

        exp_folder = create_exp_folder(tuid=dataset.attrs['tuid'],
                                       name=dataset.attrs['name'])
        # Write the empty dataset
        dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))
        # Save a snapshot of all
        snap = snapshot(update=False, clean=True)
        with open(join(exp_folder, 'snapshot.json'), 'w') as file:
            json.dump(snap, file, cls=NumpyJSONEncoder, indent=4)

        # TODO: Prepare statements
        plotmon_name = self.instr_plotmon()
        if plotmon_name is not None and plotmon_name != '':
            self.instr_plotmon.get_instr().tuid(dataset.attrs['tuid'])
            # if the timestamp has changed, this will initialize the monitor
            self.instr_plotmon.get_instr().update()

        ##################################################################
        # Iterate over all points to set
        for idx, spts in enumerate(self._setpoints):
            # set all individual setparams
            for spar, spt in zip(self._setable_pars, spts):
                # TODO add smartness to avoid setting if unchanged
                spar.set(spt)
            # acquire all data points
            for j, gpar in enumerate(self._getable_pars):
                val = gpar.get()
                dataset['y{}'.format(j)].values[idx] = val

            self._nr_acquired_values += 1

            # Saving and live plotting happens here
            # Here we do saving, plotting, checking for interupts etc.
            update = ((time.time()-self._last_upd > self.update_interval()) or
                      (idx+1 == len(self._setpoints)))
            if update:
                self.print_progress()
                # Update the
                dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))
                if plotmon_name is not None and plotmon_name != '':
                    self.instr_plotmon.get_instr().update()

                self._last_upd = time.time()

        # Wrap up experiment and store data
        dataset.to_netcdf(join(exp_folder, 'dataset.hdf5'))

        # reset the plot info for the next experiment.
        self._plot_info = {'2D-grid': False}
        return dataset

    ############################################
    # Methods used to control the measurements #
    ############################################

    def _get_fracdone(self):
        """
        Returns the fraction of the experiment that is completed.
        """
        fracdone = self._nr_acquired_values / (
            len(self._setpoints)*self.soft_avg())
        return fracdone

    def print_progress(self):
        percdone = self._get_fracdone()*100
        elapsed_time = time.time() - self._begintime
        progress_message = (
            "\r {percdone}% completed \telapsed time: "
            "{t_elapsed}s \ttime left: {t_left}s".format(
                percdone=int(percdone),
                t_elapsed=round(elapsed_time, 1),
                t_left=round((100.0 - percdone) / (percdone) * elapsed_time, 1)
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

    def set_setpars(self, setable_pars):
        """
        Define the setable parameters for the acquisition loop.

        Args:
            setable_pars: parameter(s) to be set during the acquisition loop.
                accepts:
                - list or tuple of multiple setable objects
                - a single setable object.
            A setable object is an object that has at least
                - unit (str) attribute
                - name (str) attribute
                - set method
                See also `is_getable`
        """
        # for native nD compatibility we treat this like a list of
        # setables.
        if not isinstance(setable_pars, (list, tuple)):
            setable_pars = [setable_pars]

        self._setable_pars = []
        for i, setable in enumerate(setable_pars):
            if is_setable(setable):
                self._setable_pars.append(setable)

    def set_setpoints(self, setpoints):
        """
        Set setpoints that determine values to be set in acquisition loop.

        Args:
            setpoints (np.array) : An array that defines the values to loop
                over in the experiment. The shape of the the array has to be
                either (N,) (N,1) for a 1D loop or (N, M) in the case of
                an MD loop.

        The setpoints are internally reshaped to (N, M) to be natively
        compatible with M-dimensional loops.

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

    def set_setpoints_nD(self, setpoints_x0, setpoints_xn):
        """
        Set a setpoint grid that determine values to be set in acquisition loop.
        Updates the setpoints in a grid by repeating the setpoints M times
        and filling the second column with tiled values.

        Args:
            setpoints_x0 (np.array) : An array that defines the values to loop
                over in the experiment. The shape of the the array has to be
                either (N,) (N,1) for a 1D loop
            setpoints_xn (list(np.array)) : An array of additional values to loop
                against in order
        The setpoints are internally reshaped to (N, M) to be natively
        compatible with M-dimensional loops.

        Example

            .. code-block:: python

                MC.set_setpars([t, amp])
                MC.set_setpoints_nD(t, [amp]) # beware! order matters
                MC.set_getpars(sig)
                dataset = MC.run('2D grid test')
        """
        self.set_setpoints(setpoints_x0)
        if len(setpoints_xn) == 1:
            self._plot_info['xlen'] = len(setpoints_x0)
            self._plot_info['ylen'] = len(setpoints_xn[0])
            self._plot_info['2D-grid'] = True
        self._setpoints = tile_setpoints_grid(self._setpoints, setpoints_xn)

    def set_getpars(self, getable_par):
        """
        Define the parameters to be acquired during the acquisition loop.

        Args:
            getable_pars: parameter(s) to be get during the acquisition loop.
                accepts:
                - list or tuple of multiple getable objects
                - a single getable object.
            A getable object is an object that has at least
                - unit (str) attribute
                - name (str) attribute
                - get method
                See also `is_getable`

        TODO: support fancier getables, i.e. ones that return
            - more than one quantity
            - multiple points at once (hard loop)

        """
        if is_getable(getable_par):
            self._getable_pars = [getable_par]


def is_setable(setable):
    """
    Test if an object is a valid setable.

    Args:
        setable (object)

    Return:
        is_setable (bool)

    TODO: Add desicription of what a valid setable is. (unit, get etc.)
    """
    if not hasattr(setable, 'set'):
        raise AttributeError("{} does not have 'set'.".format(setable))
    if not hasattr(setable, 'name'):
        raise AttributeError("{} does not have 'name'.".format(setable))
    if not hasattr(setable, 'unit'):
        raise AttributeError("{} does not have 'unit'.".format(setable))

    return True


def is_getable(getable):
    """
    Test if an object is a valid getable.

    Args:
        getable (object)

    Return:
        is_getable (bool)

    TODO: Add desicription of what a valid getable is. (unit, get etc.)
    """
    if not hasattr(getable, 'get'):
        raise AttributeError("{} does not have 'get'.".format(getable))
    if not hasattr(getable, 'name'):
        raise AttributeError("{} does not have 'name'.".format(getable))
    if not hasattr(getable, 'unit'):
        raise AttributeError("{} does not have 'unit'.".format(getable))

    return True


def tile_setpoints_grid(setpoints_curr, additional_setpoints):
    """
    Tile setpoints into an n-dimensional grid, where n is the len of additional_setpoints.

    Args:
        setpoints (np.array):                   an (N,1) array corresponding to x-values.
        additional_setpoints (list(np.array)):  an array of additional values for each axis.

    Returns:
        setpoints (np.array): an array with repeated x-values and
        tiled xn-values.

    .. warning ::

        using this method typecasts all values into the same type. This may
        lead to validator errors when setting e.g., a float instead of an int.
    """
    assert np.shape(setpoints_curr)[1] == 1
    for setpoints_n in additional_setpoints:
        curr_l = len(setpoints_curr)
        new_l = len(setpoints_n)
        col_stack = []
        for i in range(0, np.size(setpoints_curr, 1)):
            col_stack.append(np.tile(setpoints_curr[:, i], new_l))
        col_stack.append(np.repeat(setpoints_n, curr_l))
        setpoints_curr = np.column_stack(col_stack)
    return setpoints_curr
