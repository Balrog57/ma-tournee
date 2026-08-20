from app.services.city import extract_city


def test_extract_city_fr():
    assert extract_city("11 rue Verlaine, 57690 Zimming") == "Zimming"
    assert extract_city("2 rue de Metz, 57245 Peltre") == "Peltre"


def test_extract_city_de():
    assert "Saarbrücken" in extract_city(
        "Halbergstraße 112, 66121 Saarbrücken, Allemagne"
    )
