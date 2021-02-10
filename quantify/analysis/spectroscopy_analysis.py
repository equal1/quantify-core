import numpy as np
import matplotlib.pyplot as plt
from quantify.analysis import base_analysis as ba
from uncertainties import ufloat
from quantify.analysis import fitting_models as fm


class ResonatorSpectroscopyAnalysis(ba.BaseAnalysis):
    def process_data(self):

        # y0 = amplitude, no check for the amplitude unit as the name/label is
        # often different.
        # y1 = phase in deg, this unit should always be correct
        assert self.dset["y1"].attrs["units"] == "deg"

        S21 = self.dset["y0"] * np.cos(np.deg2rad(self.dset["y1"])) + 1j * self.dset[
            "y0"
        ] * np.sin(np.deg2rad(self.dset["y1"]))
        self.dset["S21"] = S21
        self.dset["S21"].attrs["name"] = "S21"
        self.dset["S21"].attrs["units"] = self.dset["y0"].attrs["units"]
        self.dset["S21"].attrs["long_name"] = "Transmission, $S_{21}$"

    def run_fitting(self):

        mod = fm.ResonatorModel()

        S21 = np.array(self.dset["S21"])
        f = np.array(self.dset["x0"])
        guess = mod.guess(S21, f=f)
        fit_res = mod.fit(S21, params=guess, f=f)

        self.fit_res = {"hanger_func_complex_SI": fit_res}

        fp = fit_res.params
        self.quantities_of_interest["Qi"] = ufloat(fp["Qi"].value, fp["Qi"].stderr)
        self.quantities_of_interest["Qe"] = ufloat(fp["Qe"].value, fp["Qe"].stderr)
        self.quantities_of_interest["Ql"] = ufloat(fp["Ql"].value, fp["Ql"].stderr)
        self.quantities_of_interest["Qc"] = ufloat(fp["Qc"].value, fp["Qc"].stderr)
        self.quantities_of_interest["fr"] = ufloat(fp["fr"].value, fp["fr"].stderr)

    def create_figures(self):

        # TODO missing complex plot (phase)

        f, ax = plt.subplots()
        fig_id = "S21"
        self.figs_mpl[fig_id] = f
        self.axs_mpl[fig_id] = ax
        f.suptitle(f"S21 {self.dset.attrs['name']}\ntuid: {self.dset.attrs['tuid']}")

        ba.plot_basic1D(
            ax=ax,
            x=self.dset["x0"].values,
            xlabel=self.dset["x0"].attrs["long_name"],
            xunit=self.dset["x0"].attrs["units"],
            y=self.dset["S21"].values,
            ylabel=self.dset["S21"].attrs["long_name"],
            yunit=self.dset["S21"].attrs["units"],
            plot_kw={"marker": ".", "label": "data"},
        )

        ba.plot_fit(
            ax=ax, fit_res=self.fit_res["hanger_func_complex_SI"], plot_init=True
        )
