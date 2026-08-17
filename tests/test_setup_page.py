from agent.setup_page import build_setup_page


def test_setup_page_has_configuration_controls():
    page = build_setup_page("Analog DVR Edge", "1.0")
    assert 'id="configForm"' in page
    assert 'id="customer_select"' in page
    assert 'id="site_select"' in page
    assert '/api/provision/customers' in page
    assert "Apply and Start" in page
    assert "Leave blank to keep saved password" in page
