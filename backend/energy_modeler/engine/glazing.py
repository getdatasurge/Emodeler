"""Glazing construction logic (spec Ch 4.3 / 5.4).

In the real EnergyPlus path a film is applied by swapping the outer pane's
WindowMaterial:Glazing record for the IGSDB-measured glass+film system, then
letting EnergyPlus solve angular optical properties internally (per the 3M
"never a single SHGC" rule, spec Ch 2.1).

For UI quick-picks and the analytical fallback we also need scalar SHGC/U/VT for
a (film x base glass) pairing. applied_properties() derives those by scaling the
film's IGSDB-rated values (measured on a dual-pane-clear reference) onto the
project's actual base glazing."""
from __future__ import annotations

from dataclasses import dataclass

from .film_catalog import FilmSpec

# IGSDB reference IGU that 3M film SHGC/U/VT values are measured against.
REFERENCE_DBL_CLEAR_SHGC = 0.70
REFERENCE_DBL_CLEAR_VT = 0.78


@dataclass
class GlazingProperties:
    shgc: float
    u_factor_btuhrft2F: float
    vt: float


def base_properties(base_glazing: dict) -> GlazingProperties:
    return GlazingProperties(
        shgc=float(base_glazing["shgc"]),
        u_factor_btuhrft2F=float(base_glazing["u_factor_btuhrft2F"]),
        vt=float(base_glazing["vt"]),
    )


def applied_properties(base_glazing: dict, film: FilmSpec) -> GlazingProperties:
    """Scalar SHGC/U/VT for the film applied to this base glazing.

    SHGC and VT scale by the film's retention ratio relative to the IGSDB
    dual-pane-clear reference. Low-e films (front emissivity < 0.84) also
    improve the assembly U-factor.
    """
    base = base_properties(base_glazing)

    shgc_ratio = film.shgc_on_dbl_clear / REFERENCE_DBL_CLEAR_SHGC
    applied_shgc = round(base.shgc * shgc_ratio, 3)

    # Film visible transmittance (tvis_pct) attenuates the base assembly VT.
    applied_vt = round(base.vt * (film.tvis_pct / 100.0), 3)

    emissivity = film.optical.get("emissivity_front", 0.84)
    u_factor = base.u_factor_btuhrft2F
    if emissivity < 0.80:  # low-e (e.g. Thinsulate)
        u_factor = round(u_factor * 0.85, 3)

    return GlazingProperties(shgc=applied_shgc, u_factor_btuhrft2F=u_factor, vt=applied_vt)
