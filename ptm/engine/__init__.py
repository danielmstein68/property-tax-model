"""Property tax rules engine: computes assessed value, exemptions and taxable value for any
unit (PUMS household or roll parcel) from the law spec (inputs/<state>_law.yaml, ptm.law).

Rates are a plug-in at the end (taxable x millage); the engine itself never needs them.
"""

from ptm.engine.exemptions import apply_exemptions  # noqa: F401
