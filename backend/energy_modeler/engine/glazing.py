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


# Generic clear float glass optical record (3 mm) for the un-filmed outer pane
# and inner panes. Matches the IGSDB clear-glass reference.
_CLEAR_GLASS = {
    "thickness_m": 0.003,
    "tf_solar": 0.837, "rf_solar": 0.075, "rb_solar": 0.075,
    "tf_visible": 0.898, "rf_visible": 0.081, "rb_visible": 0.081,
    "emissivity_front": 0.84, "emissivity_back": 0.84, "conductivity": 1.0,
}


def _add_glazing_material(idf, name: str, optical: dict) -> None:
    idf.newidfobject(
        "WINDOWMATERIAL:GLAZING",
        Name=name,
        Optical_Data_Type="SpectralAverage",
        Thickness=optical.get("thickness_m", 0.003),
        Solar_Transmittance_at_Normal_Incidence=optical.get("tf_solar", 0.837),
        Front_Side_Solar_Reflectance_at_Normal_Incidence=optical.get("rf_solar", 0.075),
        Back_Side_Solar_Reflectance_at_Normal_Incidence=optical.get("rb_solar", 0.075),
        Visible_Transmittance_at_Normal_Incidence=optical.get("tf_visible", 0.898),
        Front_Side_Visible_Reflectance_at_Normal_Incidence=optical.get("rf_visible", 0.081),
        Back_Side_Visible_Reflectance_at_Normal_Incidence=optical.get("rb_visible", 0.081),
        Infrared_Transmittance_at_Normal_Incidence=0.0,
        Front_Side_Infrared_Hemispherical_Emissivity=optical.get("emissivity_front", 0.84),
        Back_Side_Infrared_Hemispherical_Emissivity=optical.get("emissivity_back", 0.84),
        Conductivity=optical.get("conductivity", 1.0),
    )


def build_film_construction(
    idf, name: str, base_glazing: dict, film: "FilmSpec | None"
) -> str:
    """Add the WindowMaterial:Glazing layers + a Construction to an eppy `idf`
    for this (base glazing, film) pairing; return the construction name.

    The film is applied by substituting the OUTER pane's glazing record with the
    (glass+film) optical record (spec Ch 5.4) at SpectralAverage, so EnergyPlus
    solves angular optics per timestep — capturing why an angle-stable film like
    3M Prestige outperforms dyed films on sloped / high-incidence glazing, which
    a single-SHGC method cannot represent."""
    layer_count = int(base_glazing.get("layer_count", 1))
    outer = f"{name}_outer"
    _add_glazing_material(idf, outer, film.optical if film else _CLEAR_GLASS)
    layers = [outer]
    if layer_count >= 2:
        idf.newidfobject("WINDOWMATERIAL:GAS", Name=f"{name}_gap", Gas_Type="Air", Thickness=0.013)
        _add_glazing_material(idf, f"{name}_inner", _CLEAR_GLASS)
        layers += [f"{name}_gap", f"{name}_inner"]
    con = idf.newidfobject("CONSTRUCTION", Name=name)
    con.Outside_Layer = layers[0]
    for i, layer in enumerate(layers[1:], start=2):
        setattr(con, f"Layer_{i}", layer)
    return name
