import json

import pytest

from pendulum_kit.spoolman import (InsufficientMaterial, SpoolmanClient, SpoolmanError,
                                   SpoolmanNotFound, SpoolmanUnavailable)
from pendulum_kit.stock import load_stock_file, register_stock


@pytest.fixture
def stocked(spoolman_url):
    client = SpoolmanClient(spoolman_url)
    report = register_stock(client, load_stock_file())
    return client, report


def test_health(spoolman_url, dead_url):
    assert SpoolmanClient(spoolman_url).is_available()
    assert not SpoolmanClient(dead_url, timeout=1, retries=0).is_available()


def test_service_down_gives_clear_error(dead_url):
    with pytest.raises(SpoolmanUnavailable, match="does not answer"):
        SpoolmanClient(dead_url, timeout=1, retries=0).list_filaments()


def test_server_error_is_unavailable(spoolman_url):
    with pytest.raises(SpoolmanUnavailable):
        SpoolmanClient(spoolman_url, retries=0)._get("/broken")


def test_not_found(spoolman_url):
    with pytest.raises(SpoolmanNotFound):
        SpoolmanClient(spoolman_url).get_filament(999)


def test_bad_post_is_rejected(spoolman_url):
    with pytest.raises(SpoolmanError, match="rejected"):
        SpoolmanClient(spoolman_url).create_filament({"name": "no density"})


def test_register_stock(stocked):
    client, report = stocked
    assert len(report) == len(load_stock_file()["filaments"])
    fil = client.get_filament(report[0]["filament_id"])
    assert fil["density"] == 1.24
    assert client.remaining_g(fil["id"]) == 1000


def test_register_stock_twice_creates_nothing_new(stocked):
    client, _ = stocked
    again = register_stock(client, load_stock_file())
    assert not any(r["filament_created"] or r["spool_created"] for r in again)
    assert len(client.list_filaments()) == len(again)


def test_reserve_and_use(stocked):
    client, report = stocked
    fid = report[0]["filament_id"]
    allocation = client.reserve({fid: 42.5})
    client.register_use(allocation)
    assert client.remaining_g(fid) == pytest.approx(1000 - 42.5)


def test_best_fit_spool(stocked):
    client, report = stocked
    fid = report[0]["filament_id"]
    small = client.create_spool(fid, 100)            # second, nearly empty spool
    assert client.reserve({fid: 50})[0].spool_id == small["id"]
    assert client.reserve({fid: 500})[0].spool_id != small["id"]


def test_insufficient_material_changes_nothing(stocked):
    client, report = stocked
    a, b = report[0]["filament_id"], report[1]["filament_id"]
    with pytest.raises(InsufficientMaterial) as err:
        client.reserve({a: 10, b: 5000, 999: 1})
    assert set(err.value.shortages) == {b, 999}
    assert client.remaining_g(a) == 1000


def test_stock_file_validation(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"filaments": [{"name": "x", "density": 1.2}]}))
    with pytest.raises(ValueError, match="missing"):
        load_stock_file(bad)
