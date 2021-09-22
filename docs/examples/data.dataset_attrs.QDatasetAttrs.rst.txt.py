# ---
# jupyter:
#   jupytext:
#     cell_markers: '\"\"\"'
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%

from quantify_core.utilities import examples_support
import pendulum

examples_support.mk_dataset_attrs(
    experiment_name="Bias scan",
    experiment_start=pendulum.now().to_iso8601_string(),
    experiment_end=pendulum.now().add(minutes=2).to_iso8601_string(),
    experiment_state="done",
)
