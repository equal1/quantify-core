"""
This module should contain different analyses corresponding to discrete experiments
"""
import json
import sys
from collections import OrderedDict
from qcodes.utils.helpers import NumpyJSONEncoder
import lmfit
import numpy as np
import matplotlib.pyplot as plt
import os
from abc import ABC
from quantify.visualization import mpl_plotting as qpl
from quantify.data.handling import (
    load_dataset,
    get_latest_tuid,
    _locate_experiment_file,
    get_datadir,
)
from quantify.visualization.SI_utilities import set_xlabel, set_ylabel

# this is a pointer to the module object instance itself.
this = sys.modules[__name__]

# global configurations at the level of the analysis module
this.settings = {
    "DPI": 450,  # define resolution of some matplotlib output formats
    "fig_formats": ("png", "svg"),
    "presentation_mode": False,
    "transparent_background": False,
}


class BaseAnalysis(ABC):
    """
    Abstract base class for data analysis. Provides a template from which to
    inherit when doing any analysis.
    """

    def __init__(self, label: str = "", tuid: str = None, close_figs: bool = True):
        """
        Initializes the variables that are used in the analysis and to which data is
        stored.

        Parameters
        ------------------
        label: str
            Will look for a dataset that contains "label" in the name.
        tuid: str
            If specified, will look for the dataset with the matching tuid.
        close_figs: bool
            If True, closes matplotlib figures after saving
        """

        self.label = label
        self.tuid = tuid
        self.close_figs = close_figs

        # This will be overwritten
        self.dset = None
        # To be populated by a subclass
        self.figs_mpl = OrderedDict()
        self.axs_mpl = OrderedDict()
        self.quantities_of_interest = OrderedDict()
        self.fit_res = OrderedDict()
        self.run_analysis()

    @property
    def name(self):
        # used to store data and figures resulting from the analysis. Can be overwritten
        return self.__class__.__name__

    def extract_data(self):
        """
        Populates `self.dset` with data from the experiment matching the tuid/label.

        This method should be overwritten if an analysis does not relate to a single
        datafile.
        """

        # if no TUID is specified use the label to search for the latest file with a match.
        if self.tuid is None:
            self.tuid = get_latest_tuid(contains=self.label)

        self.dset = load_dataset(tuid=self.tuid)

    @property
    def analysis_dir(self):
        """
        Analysis dir based on the tuid. Will create a directory if it does not exist yet.
        """
        if self.tuid is None:
            raise ValueError("TUID unknown, cannot determine analysis dir")
        # This is a property as it depends
        exp_folder = _locate_experiment_file(self.tuid, get_datadir(), "")
        analysis_dir = os.path.join(exp_folder, f"analysis_{self.name}")
        if not os.path.isdir(analysis_dir):
            os.makedirs(analysis_dir)

        return analysis_dir

    def run_analysis(self):
        """
        This function is at the core of all analysis and defines the flow.

        This function is typically called after the __init__.
        """
        self.extract_data()  # extract data specified in params dict

        self.process_data()  # binning, filtering etc

        self.prepare_fitting()  # set up fit_dicts
        self.run_fitting()  # fitting to models
        self.analyze_fit_results()  # analyzing the results of the fits
        self.create_figures()
        self.adjust_figures()
        self.save_figures()
        self.save_quantities_of_interest()
        self.save_processed_dataset()

    def process_data(self):
        """
        This method can be used to process, e.g., reshape, filter etc. the data
        before starting the analysis. By default this method is empty (pass).
        """
        pass

    def prepare_fitting(self):
        pass

    def run_fitting(self):
        pass

    def _add_fit_res_to_qoi(self):
        if len(self.fit_res) > 0:
            self.quantities_of_interest["fit_res"] = OrderedDict()
            for fr_name, fr in self.fit_res.items():
                self.quantities_of_interest["fit_res"][
                    fr_name
                ] = flatten_lmfit_modelresult(fr)

    def analyze_fit_results(self):
        pass

    def save_quantities_of_interest(self):

        self._add_fit_res_to_qoi()

        with open(
            os.path.join(self.analysis_dir, "quantities_of_interest.json"), "w"
        ) as file:
            json.dump(self.quantities_of_interest, file, cls=NumpyJSONEncoder, indent=4)

    def create_figures(self):
        pass

    def adjust_figures(self):
        """
        Perform global adjustments after creating the figures but
        before saving them
        """
        for fig in self.figs_mpl.values():
            if this.settings["presentation_mode"]:
                # Remove the experiment name and tuid from figures
                fig.suptitle(r"")
            if this.settings["transparent_background"]:
                # Set transparent background on figures
                fig.patch.set_alpha(0)

    def save_processed_dataset(self):
        """
        Saves a copy of self.dset in the analysis folder of the experiment.
        """

        # if statement exist to be compatible with child classes that do not load data
        # onto the self.dset object.

        pass  # see issue #150
        # if self.dset is not None:
        #     netcdf encoding of datasets does not support complex numbers.
        #     see issue #150
        #     self.dset.to_netcdf(
        #         os.path.join(self.analysis_dir, "processed_dataset.hdf5"),
        #         engine="h5netcdf",
        #         invalid_netcdf=True,
        #     )

    def save_figures(self):
        """
        Saves all the figures in the :code:`figs_mpl` dict
        """
        DPI = this.settings["DPI"]
        formats = this.settings["fig_formats"]

        if len(self.figs_mpl) != 0:
            mpl_figdir = os.path.join(self.analysis_dir, "figs_mpl")
            if not os.path.isdir(mpl_figdir):
                os.makedirs(mpl_figdir)

            for figname, fig in self.figs_mpl.items():
                filename = os.path.join(mpl_figdir, f"{figname}")
                for form in formats:
                    fig.savefig(f"{filename}.{form}", bbox_inches="tight", dpi=DPI)
                if self.close_figs:
                    plt.close(fig)


class Basic1DAnalysis(BaseAnalysis):
    """
    A basic analysis that extracts the data from the latest file matching the label
    and plots and stores the data in the experiment container.
    """

    def create_figures(self):

        ys = set(self.dset.keys())
        ys.discard("x0")
        for yi in ys:
            f, ax = plt.subplots()
            fig_id = f"Line plot x0-{yi}"
            self.figs_mpl[fig_id] = f
            self.axs_mpl[fig_id] = ax

            plot_basic1D(
                ax=ax,
                x=self.dset["x0"].values,
                xlabel=self.dset["x0"].attrs["long_name"],
                xunit=self.dset["x0"].attrs["units"],
                y=self.dset[f"{yi}"].values,
                ylabel=self.dset[f"{yi}"].attrs["long_name"],
                yunit=self.dset[f"{yi}"].attrs["units"],
            )

            f.suptitle(
                f"x0-{yi} {self.dset.attrs['name']}\ntuid: {self.dset.attrs['tuid']}"
            )


class Basic2DAnalysis(BaseAnalysis):
    """
    A basic analysis that extracts the data from the latest file matching the label
    and plots and stores the data in the experiment container.
    """

    def create_figures(self):
        ys = set(self.dset.keys())
        ys.discard("x0")
        ys.discard("x1")

        for yi in ys:
            f, ax = plt.subplots()
            fig_id = f"Heatmap x0x1-{yi}"

            self.figs_mpl[fig_id] = f
            self.axs_mpl[fig_id] = ax

            qpl.plot_2D_grid(
                x=self.dset["x0"],
                y=self.dset["x1"],
                z=self.dset[f"{yi}"],
                xlabel=self.dset["x0"].attrs["long_name"],
                xunit=self.dset["x0"].attrs["units"],
                ylabel=self.dset["x1"].attrs["long_name"],
                yunit=self.dset["x1"].attrs["units"],
                zlabel=self.dset[f"{yi}"].attrs["long_name"],
                zunit=self.dset[f"{yi}"].attrs["units"],
                ax=ax,
            )

            f.suptitle(
                f"x0x1-{yi} {self.dset.attrs['name']}\ntuid: {self.dset.attrs['tuid']}"
            )


def plot_basic1D(
    x,
    y,
    xlabel: str,
    xunit: str,
    ylabel: str,
    yunit: str,
    ax,
    title: str = None,
    plot_kw: dict = {},
    **kw,
):
    ax.plot(x, y, **plot_kw)
    if title is not None:
        ax.set_title(title)
    set_xlabel(ax, xlabel, xunit)
    set_ylabel(ax, ylabel, yunit)


def plot_fit(ax, fit_res, plot_init: bool = True, plot_numpoints: int = 1000, **kw):
    model = fit_res.model

    if len(model.independent_vars) == 1:
        independent_var = model.independent_vars[0]
    else:
        raise ValueError(
            "Fit can only be plotted if the model function"
            " has one independent variable."
        )

    x_arr = fit_res.userkws[independent_var]
    x = np.linspace(np.min(x_arr), np.max(x_arr), plot_numpoints)
    y = model.eval(fit_res.params, **{independent_var: x})
    ax.plot(x, y, label="Fit", c="C3")

    if plot_init:
        x = np.linspace(np.min(x_arr), np.max(x_arr), plot_numpoints)
        y = model.eval(fit_res.init_params, **{independent_var: x})
        ax.plot(x, y, ls="--", c="grey", label="Guess")


def flatten_lmfit_modelresult(model):
    """
    Flatten an lmfit model result to a dictionary in order to be able to save it to disk.

    Notes
    -----
    We use this method as opposed to :func:`lmfit.model.save_modelresult` as the
    corresponding :func:`lmfit.model.load_modelresult` cannot handle loading data with
    a custom fit function.
    """
    assert (
        type(model) is lmfit.model.ModelResult
        or type(model) is lmfit.minimizer.MinimizerResult
    )
    dic = OrderedDict()
    dic["success"] = model.success
    dic["message"] = model.message
    dic["params"] = {}
    for param_name in model.params:
        dic["params"][param_name] = {}
        param = model.params[param_name]
        for k in param.__dict__:
            if not k.startswith("_") and k not in [
                "from_internal",
            ]:
                dic["params"][param_name][k] = getattr(param, k)
        dic["params"][param_name]["value"] = getattr(param, "value")
    return dic
