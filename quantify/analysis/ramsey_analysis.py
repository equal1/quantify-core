# Repository: https://gitlab.com/quantify-os/quantify-core
# Licensed according to the LICENCE file on the master branch
import numpy as np
import matplotlib.pyplot as plt
from uncertainties import ufloat
from quantify.analysis import base_analysis as ba
from quantify.analysis import fitting_models as fm
from quantify.visualization import mpl_plotting as qpl
from quantify.visualization.SI_utilities import format_value_string


class RamseyAnalysis(ba.BaseAnalysis):
    """
    Fits a decaying cosine curve to Ramsey data (possibly with artificial detuning)
    and finds the true detuning, qubit frequency and T2* time.

    .. include:: ./docstring_examples/quantify.analysis.base_analysis.RamseyAnalysis.rst.txt
    """  # pylint: disable=line-too-long

    # Override the run method so that we can add the new optional arguments
    # pylint: disable=attribute-defined-outside-init
    def run(self, artificial_detuning: float = 0, qubit_frequency: float = None):
        # pylint: disable=arguments-differ

        self.artificial_detuning = artificial_detuning
        self.qubit_frequency = qubit_frequency
        return super().run()

    def process_data(self):
        # y0 = amplitude, no check for the amplitude unit as the name/label is
        # often different.
        # y1 = phase in deg, this unit should always be correct
        assert self.dataset.y1.units == "deg"

        mag = self.dataset.y0
        # TODO solve NaNs properly when #176 has a solution, pylint: disable=fixme
        valid_meas = np.logical_not(np.isnan(mag))
        self.dataset_processed["Magnitude"] = mag[valid_meas]
        self.dataset_processed["Magnitude"].attrs["name"] = "Magnitude"
        self.dataset_processed["Magnitude"].attrs["units"] = self.dataset.y0.units
        self.dataset_processed["Magnitude"].attrs[
            "long_name"
        ] = r"Magnitude, $|S_{21}|$"

        self.dataset_processed["x0"] = self.dataset.x0[valid_meas]
        self.dataset_processed = self.dataset_processed.set_coords("x0")
        # replace the default dim_0 with x0
        self.dataset_processed = self.dataset_processed.swap_dims({"dim_0": "x0"})

    def run_fitting(self):
        model = fm.DecayOscillationModel()

        magnitude = np.array(self.dataset_processed["Magnitude"])
        time = np.array(self.dataset_processed.x0)
        guess = model.guess(magnitude, time=time)
        fit_result = model.fit(magnitude, params=guess, t=time)

        self.fit_results.update({"Ramsey_decay": fit_result})

    def analyze_fit_results(self):
        """
        Extract the real detuning and qubit frequency based on the artificial detuning
        and fitted detuning
        """
        fit_warning = ba.check_lmfit(self.fit_results["Ramsey_decay"])

        fit_parameters = self.fit_results["Ramsey_decay"].params

        self.quantities_of_interest["T2*"] = ba.lmfit_par_to_ufloat(
            fit_parameters["tau"]
        )
        self.quantities_of_interest["fitted_detuning"] = ba.lmfit_par_to_ufloat(
            fit_parameters["frequency"]
        )
        self.quantities_of_interest["detuning"] = (
            self.quantities_of_interest["fitted_detuning"] - self.artificial_detuning
        )

        if self.qubit_frequency is not None:
            self.quantities_of_interest["qubit_frequency"] = (
                self.qubit_frequency - self.quantities_of_interest["detuning"]
            )

        # If there is a problem with the fit, display an error message in the text box.
        # Otherwise, display the parameters as normal.
        if fit_warning is None:
            self.quantities_of_interest["fit_success"] = True

            text_msg = "Summary\n"
            text_msg += format_value_string(
                r"$T_2^*$",
                self.quantities_of_interest["T2*"],
                unit="s",
                end_char="\n\n",
            )
            text_msg += format_value_string(
                "artificial detuning",
                ufloat(self.artificial_detuning, 0),
                unit="Hz",
                end_char="\n",
            )
            text_msg += format_value_string(
                "fitted detuning",
                self.quantities_of_interest["fitted_detuning"],
                unit="Hz",
                end_char="\n",
            )
            text_msg += format_value_string(
                "actual detuning",
                self.quantities_of_interest["detuning"],
                unit="Hz",
                end_char="\n",
            )

            if self.qubit_frequency is not None:
                text_msg += "\n"
                text_msg += format_value_string(
                    "initial qubit frequency",
                    ufloat(self.qubit_frequency, 0),
                    unit="Hz",
                    end_char="\n",
                )
                text_msg += format_value_string(
                    "fitted qubit frequency",
                    self.quantities_of_interest["qubit_frequency"],
                    unit="Hz",
                )
        else:
            text_msg = ba.wrap_text(fit_warning)
            self.quantities_of_interest["fit_success"] = False

        self.quantities_of_interest["fit_msg"] = text_msg

    def create_figures(self):
        self.create_fig_ramsey_decay()

    def create_fig_ramsey_decay(self):
        """Plot Ramsey decay figure"""

        fig_id = "Ramsey_decay"
        fig, ax = plt.subplots()
        self.figs_mpl[fig_id] = fig
        self.axs_mpl[fig_id] = ax

        # Add a textbox with the fit_message
        qpl.plot_textbox(ax, self.quantities_of_interest["fit_msg"])

        self.dataset_processed.Magnitude.plot(ax=ax, marker=".", linestyle="")

        qpl.plot_fit(
            ax=ax,
            fit_res=self.fit_results["Ramsey_decay"],
            plot_init=not self.quantities_of_interest["fit_success"],
            range_casting="real",
        )

        qpl.set_ylabel(ax, r"Output voltage", self.dataset_processed["Magnitude"].units)
        qpl.set_xlabel(
            ax,
            self.dataset_processed.x0.long_name,
            self.dataset_processed.x0.units,
        )

        qpl.set_suptitle_from_dataset(fig, self.dataset, "S21")
