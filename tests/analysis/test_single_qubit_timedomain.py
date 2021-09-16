# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name  # in order to keep the fixture in the same file
import pytest
import numpy as np
from pytest import approx
from uncertainties.core import Variable, AffineScalarFunc
from quantify_core.data.handling import set_datadir

from quantify_core.analysis.single_qubit_timedomain import (
    rotate_to_calibrated_axis,
    T1Analysis,
    EchoAnalysis,
    RamseyAnalysis,
    AllXYAnalysis,
)


def test_rotate_to_calibrated_axis():

    ref_val_0 = 0.24 + 324 * 1j
    ref_val_1 = 0.89 + 0.324 * 1j
    data = np.array([ref_val_0, ref_val_1])

    corrected_data = np.real(
        rotate_to_calibrated_axis(data, ref_val_0=ref_val_0, ref_val_1=ref_val_1)
    )

    np.testing.assert_array_equal(corrected_data, np.array([0.0, 1.0]))


@pytest.fixture(scope="module", autouse=True)
def t1_analysis_no_cal_points(tmp_test_data_dir):
    """
    Used to run the analysis a single time and run unit tests against the created
    analysis object.
    """
    tuid = "20210322-205253-758-6689"
    set_datadir(tmp_test_data_dir)
    return T1Analysis(tuid=tuid).run(calibration_points=False)


def test_t1_figures_generated(t1_analysis_no_cal_points):
    """
    Test that the right figures get created.
    """
    assert set(t1_analysis_no_cal_points.figs_mpl.keys()) == {
        "T1_decay",
    }


def test_t1_quantities_of_interest(t1_analysis_no_cal_points):
    """
    Test that the fit returns the correct values
    """

    assert set(t1_analysis_no_cal_points.quantities_of_interest.keys()) == {
        "T1",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    exp_t1 = 1.07e-5
    assert isinstance(t1_analysis_no_cal_points.quantities_of_interest["T1"], Variable)
    # Tests that the fitted values are correct (to within 5 standard deviations)
    assert t1_analysis_no_cal_points.quantities_of_interest[
        "T1"
    ].nominal_value == approx(
        exp_t1, abs=5 * t1_analysis_no_cal_points.quantities_of_interest["T1"].std_dev
    )


def test_t1_analysis_with_cal_points(tmp_test_data_dir):
    """
    Used to run the analysis a single time and run unit tests against the created
    analysis object.
    """
    tuid = "20210827-174946-357-70a986"
    set_datadir(tmp_test_data_dir)
    analysis_obj = T1Analysis(tuid=tuid).run(calibration_points=True)

    assert set(analysis_obj.quantities_of_interest.keys()) == {
        "T1",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    exp_t1 = 7.716e-6
    assert isinstance(analysis_obj.quantities_of_interest["T1"], Variable)
    # Tests that the fitted values are correct (to within 5 standard deviations)
    meas_t1 = analysis_obj.quantities_of_interest["T1"].nominal_value

    # accurate to < 1 %
    assert meas_t1 == approx(exp_t1, rel=0.01)


def test_echo_analysis_no_cal(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)

    analysis_obj = EchoAnalysis(tuid="20210420-001339-580-97bdef").run(
        calibration_points=False
    )
    assert set(analysis_obj.figs_mpl.keys()) == {
        "Echo_decay",
    }

    exp_t2_echo = 10.00e-6
    assert set(analysis_obj.quantities_of_interest.keys()) == {
        "t2_echo",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    assert isinstance(analysis_obj.quantities_of_interest["t2_echo"], Variable)
    # Tests that the fitted values are correct (to within 5 standard deviations)
    meas_echo = analysis_obj.quantities_of_interest["t2_echo"].nominal_value

    # accurate to < 1 %
    assert meas_echo == approx(exp_t2_echo, rel=0.01)


def test_echo_analysis_with_cal(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)

    analysis_obj = EchoAnalysis(tuid="20210827-175021-521-251f28").run(
        calibration_points=True
    )
    assert set(analysis_obj.figs_mpl.keys()) == {
        "Echo_decay",
    }

    exp_t2_echo = 13.61e-6
    assert set(analysis_obj.quantities_of_interest.keys()) == {
        "t2_echo",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    assert isinstance(analysis_obj.quantities_of_interest["t2_echo"], Variable)
    # Tests that the fitted values are correct (to within 5 standard deviations)
    meas_echo = analysis_obj.quantities_of_interest["t2_echo"].nominal_value

    # accurate to < 1 %
    assert meas_echo == approx(exp_t2_echo, rel=0.01)


def test_ramsey_no_cal_generated(tmp_test_data_dir):
    """test that the right figures get created"""
    set_datadir(tmp_test_data_dir)
    analysis = RamseyAnalysis(tuid="20210422-104958-297-7d6034").run(
        artificial_detuning=250e3
    )
    assert set(analysis.figs_mpl.keys()) == {
        "Ramsey_decay",
    }

    assert set(analysis.quantities_of_interest.keys()) == {
        "T2*",
        "fitted_detuning",
        "detuning",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    values = {
        "T2*": 9.029460824594437e-06,
        "fitted_detuning": 260217.48366305148,
        "detuning": 10.217e3,
    }

    assert isinstance(analysis.quantities_of_interest["T2*"], Variable)
    assert isinstance(analysis.quantities_of_interest["fitted_detuning"], Variable)
    assert isinstance(analysis.quantities_of_interest["detuning"], AffineScalarFunc)

    # Tests that the fitted values are correct (to within 5 standard deviations)
    assert analysis.quantities_of_interest["T2*"].nominal_value == pytest.approx(
        values["T2*"],
        abs=5 * analysis.quantities_of_interest["T2*"].std_dev,
    )
    assert analysis.quantities_of_interest[
        "fitted_detuning"
    ].nominal_value == pytest.approx(
        values["fitted_detuning"],
        abs=5 * analysis.quantities_of_interest["fitted_detuning"].std_dev,
    )
    assert analysis.quantities_of_interest["detuning"].nominal_value == pytest.approx(
        values["detuning"],
        abs=5 * analysis.quantities_of_interest["detuning"].std_dev,
    )
    assert analysis.quantities_of_interest["fit_success"] is True


# Also test for the case where the user inputs a qubit frequency
@pytest.fixture(scope="module", autouse=True)
def ramsey_analysis_qubit_freq(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)
    analysis = RamseyAnalysis(tuid="20210422-104958-297-7d6034").run(
        artificial_detuning=250e3, qubit_frequency=4.7149e9, calibration_points=False
    )
    return analysis


def test_figures_generated_qubit_freq_qubit_freq(ramsey_analysis_qubit_freq):
    """test that the right figures get created"""
    assert set(ramsey_analysis_qubit_freq.figs_mpl.keys()) == {
        "Ramsey_decay",
    }


def test_quantities_of_interest_qubit_freq(ramsey_analysis_qubit_freq):
    """Test that the quantities of interest have the correct values"""
    assert set(ramsey_analysis_qubit_freq.quantities_of_interest.keys()) == {
        "T2*",
        "fitted_detuning",
        "detuning",
        "qubit_frequency",
        "fit_msg",
        "fit_result",
        "fit_success",
    }

    values = {
        "T2*": 9.029460824594437e-06,
        "fitted_detuning": 260217.48366305148,
        "detuning": 10.217e3,
        "qubit_frequency": 4.7149e9,
    }

    assert isinstance(
        ramsey_analysis_qubit_freq.quantities_of_interest["T2*"], Variable
    )
    assert isinstance(
        ramsey_analysis_qubit_freq.quantities_of_interest["fitted_detuning"], Variable
    )
    assert isinstance(
        ramsey_analysis_qubit_freq.quantities_of_interest["detuning"], AffineScalarFunc
    )
    assert isinstance(
        ramsey_analysis_qubit_freq.quantities_of_interest["qubit_frequency"],
        AffineScalarFunc,
    )

    # Tests that the fitted values are correct (to within 5 standard deviations)
    assert ramsey_analysis_qubit_freq.quantities_of_interest[
        "T2*"
    ].nominal_value == pytest.approx(
        values["T2*"],
        rel=0.01,
    )
    assert ramsey_analysis_qubit_freq.quantities_of_interest[
        "fitted_detuning"
    ].nominal_value == pytest.approx(
        values["fitted_detuning"],
        rel=0.01,
    )
    assert ramsey_analysis_qubit_freq.quantities_of_interest[
        "detuning"
    ].nominal_value == pytest.approx(
        values["detuning"],
        rel=0.01,
    )
    assert ramsey_analysis_qubit_freq.quantities_of_interest[
        "qubit_frequency"
    ].nominal_value == pytest.approx(
        values["qubit_frequency"],
        rel=0.01,
    )
    assert ramsey_analysis_qubit_freq.quantities_of_interest["fit_success"] is True


def test_ramsey_analysis_with_cal(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)

    analysis_obj = RamseyAnalysis(tuid="20210827-175004-087-ab1aab").run(
        calibration_points=True
    )
    assert set(analysis_obj.figs_mpl.keys()) == {
        "Ramsey_decay",
    }

    exp_t2_ramsey = 10.43e-06
    assert set(
        {"T2*", "detuning", "fit_msg", "fit_result", "fit_success", "fitted_detuning"}
    ) == set(analysis_obj.quantities_of_interest.keys())

    assert isinstance(analysis_obj.quantities_of_interest["T2*"], Variable)
    # Tests that the fitted values are correct (to within 5 standard deviations)
    meas_t2_ramsey = analysis_obj.quantities_of_interest["T2*"].nominal_value

    # accurate to < 1 %
    assert meas_t2_ramsey == approx(exp_t2_ramsey, rel=0.01)
    meas_detuning = analysis_obj.quantities_of_interest["detuning"].nominal_value
    assert meas_detuning == approx(166557, rel=0.01)


def test_ramsey_analysis_with_cal_qubit_freq_reporting(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)
    tuid = "20210901-132357-561-5c3ef7"
    qubit_frequency = 6140002015.621445

    a_obj = RamseyAnalysis(tuid=tuid)
    a_obj.run(artificial_detuning=150e3, qubit_frequency=qubit_frequency)

    exp_t2_ramsey = 7.239e-6
    exp_detuning = -244.65
    exp_fitted_detuning = 149609
    exp_qubit_frequency = 6.140002406e9

    t2_ramsey = a_obj.quantities_of_interest["T2*"].nominal_value
    detuning = a_obj.quantities_of_interest["detuning"].nominal_value
    fitted_detuning = a_obj.quantities_of_interest["fitted_detuning"].nominal_value
    qubit_frequency = a_obj.quantities_of_interest["qubit_frequency"].nominal_value

    assert t2_ramsey == approx(exp_t2_ramsey, rel=0.01)
    assert detuning == approx(exp_detuning, rel=0.01)
    assert fitted_detuning == approx(exp_fitted_detuning, rel=0.01)
    assert qubit_frequency == approx(exp_qubit_frequency, rel=0.01)


@pytest.fixture(scope="session", autouse=True)
def allxy_analysis_obj(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)
    allxy_analysis_obj = AllXYAnalysis(tuid="20210419-173649-456-23c5f3").run()
    return allxy_analysis_obj


def test_allxy_figures_generated(allxy_analysis_obj):
    """test that the right figures get created"""
    assert set(allxy_analysis_obj.figs_mpl.keys()) == {
        "AllXY",
    }


def test_allxy_quantities_of_interest(allxy_analysis_obj):
    """Test that the quantities of interest have the correct values"""
    assert set(allxy_analysis_obj.quantities_of_interest.keys()) == {
        "deviation",
    }

    exp_deviation = 0.0107

    assert isinstance(allxy_analysis_obj.quantities_of_interest["deviation"], float)

    # Tests that the fitted values are correct
    assert allxy_analysis_obj.quantities_of_interest["deviation"] == pytest.approx(
        exp_deviation,
        rel=0.01,
    )


def test_allxy_dataset_processed(allxy_analysis_obj):
    assert len(allxy_analysis_obj.dataset_processed.ideal_data)
    assert len(allxy_analysis_obj.dataset_processed.pop_exc)


# Test that the analysis returns an error when the number of datapoints
# is not a multiple of 21
def test_allxy_analysis_invalid_data(tmp_test_data_dir):
    set_datadir(tmp_test_data_dir)
    with pytest.raises(
        ValueError,
        match=(
            "Invalid dataset. The number of calibration points in an "
            "AllXY experiment must be a multiple of 21"
        ),
    ):
        AllXYAnalysis(tuid="20210422-104958-297-7d6034").run()