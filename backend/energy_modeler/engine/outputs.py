"""Output:Variable / Output:Meter IDF block (spec Ch 4.5).

Returned as IDF text and appended by idf_builder when generating real IDF files.
By default EnergyPlus reports almost nothing; these are the variables the parser
(Ch 6) needs for end-use totals, peak demand, and per-surface window gains."""
from __future__ import annotations

STANDARD_OUTPUTS_IDF = """\
! ----- Energy end uses (annual + hourly) -----
Output:Meter, Electricity:Facility, Hourly;
Output:Meter, Cooling:Electricity, Hourly;
Output:Meter, Heating:Electricity, Hourly;
Output:Meter, Heating:Gas, Hourly;
Output:Meter, Fans:Electricity, Hourly;
Output:Meter, Pumps:Electricity, Hourly;
Output:Meter, InteriorLights:Electricity, Hourly;

! ----- Peak demand -----
Output:Variable,*, Facility Total Electric Demand Power, Hourly;
Output:Variable,*, Facility Total Building Electric Demand Power, Hourly;

! ----- Window-specific outputs (per surface) -----
Output:Variable,*, Surface Window Heat Gain Energy, Hourly;
Output:Variable,*, Surface Window Heat Loss Energy, Hourly;
Output:Variable,*, Surface Window Transmitted Solar Radiation Rate, Hourly;
Output:Variable,*, Surface Window Solar Horizontal Profile Angle, Hourly;

! ----- Summary reports for audit bundle -----
Output:Table:SummaryReports,
  AnnualBuildingUtilityPerformanceSummary,
  InputVerificationandResultsSummary,
  DemandEndUseComponentsSummary,
  ClimaticDataSummary,
  EnvelopeSummary,
  EquipmentSummary;

OutputControl:Table:Style, HTML, JtoKWH;
"""


def standard_outputs_idf() -> str:
    return STANDARD_OUTPUTS_IDF
