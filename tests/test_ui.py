from pathlib import Path


STATIC = Path(__file__).parents[1] / "app" / "static"


def test_mobile_list_toggle_and_map_selection_are_wired():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")

    assert 'aria-controls="school-sidebar"' in html
    assert ".layout.list-collapsed" in css
    select_from_map = js[js.index("function selectSchoolFromMap"):js.index("function renderList")]
    assert select_from_map.index("setListCollapsed(false)") < select_from_map.index("scrollIntoView")
