from energy_modeler import carbon


def test_co2_avoided_uses_subregion_factor():
    # Tampa 33540 -> FRCC (801.9 lb/MWh). 100,000 kWh = 100 MWh.
    lb = carbon.lb_co2_avoided(100_000, "33540")
    assert abs(lb - 100 * 801.9) < 1.0


def test_co2_avoided_national_fallback_for_unknown_zip():
    lb = carbon.lb_co2_avoided(100_000, "00000")
    assert abs(lb - 100 * carbon.NATIONAL_CO2_LB_PER_MWH) < 1.0


def test_co2e_kg_conversion():
    kg = carbon.co2e_kg_avoided(100_000, "33540")
    assert kg > 0
    # CO2e (lb) * 0.453592 kg/lb
    assert abs(kg - 100 * 804.5 * carbon.KG_PER_LB) < 1.0


def test_equivalent_vehicle_years():
    assert carbon.equivalent_vehicle_years(carbon.LB_CO2_PER_VEHICLE_YEAR) == 1.0


def test_subregion_for_zip():
    info = carbon.subregion_for_zip("33540")
    assert info["subregion"] == "FRCC"
    assert info["co2_lb_per_mwh"] == 801.9
