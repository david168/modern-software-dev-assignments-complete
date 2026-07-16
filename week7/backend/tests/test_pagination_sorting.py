import pytest


def _create_notes(client, count):
    ids = []
    for i in range(count):
        r = client.post("/notes/", json={"title": f"Note {i:02d}", "content": f"Body {i}"})
        assert r.status_code == 201
        ids.append(r.json()["id"])
    return ids


def _create_action_items(client, count, completed_indices=frozenset()):
    ids = []
    for i in range(count):
        r = client.post("/action-items/", json={"description": f"Item {i:02d}"})
        assert r.status_code == 201
        item_id = r.json()["id"]
        if i in completed_indices:
            r = client.put(f"/action-items/{item_id}/complete")
            assert r.status_code == 200
        ids.append(item_id)
    return ids


# --- Notes: sorting ---------------------------------------------------


def test_list_notes_sort_by_title_ascending(client):
    _create_notes(client, 5)

    r = client.get("/notes/", params={"sort": "title", "limit": 200})
    assert r.status_code == 200
    titles = [n["title"] for n in r.json()]
    assert titles == sorted(titles)


def test_list_notes_sort_by_title_descending(client):
    _create_notes(client, 5)

    r = client.get("/notes/", params={"sort": "-title", "limit": 200})
    assert r.status_code == 200
    titles = [n["title"] for n in r.json()]
    assert titles == sorted(titles, reverse=True)


def test_list_notes_sort_by_id_ascending_matches_insertion_order(client):
    ids = _create_notes(client, 5)

    r = client.get("/notes/", params={"sort": "id", "limit": 200})
    assert r.status_code == 200
    returned_ids = [n["id"] for n in r.json() if n["id"] in ids]
    assert returned_ids == ids


def test_list_notes_default_sort_is_created_at_descending(client):
    ids = _create_notes(client, 3)

    r = client.get("/notes/", params={"limit": 200})
    assert r.status_code == 200
    returned_ids = [n["id"] for n in r.json() if n["id"] in ids]
    # Most recently created should come first.
    assert returned_ids == list(reversed(ids))


def test_list_notes_unknown_sort_field_falls_back_to_created_at_desc(client):
    ids = _create_notes(client, 3)

    r = client.get("/notes/", params={"sort": "not_a_real_field", "limit": 200})
    assert r.status_code == 200
    returned_ids = [n["id"] for n in r.json() if n["id"] in ids]
    assert returned_ids == list(reversed(ids))


# --- Notes: pagination --------------------------------------------------


def test_list_notes_pagination_respects_limit(client):
    _create_notes(client, 5)

    r = client.get("/notes/", params={"sort": "id", "limit": 2})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_notes_pagination_skip_and_limit_slice_correctly(client):
    ids = _create_notes(client, 5)

    r = client.get("/notes/", params={"sort": "id", "skip": 0, "limit": 2})
    page1 = [n["id"] for n in r.json()]
    r = client.get("/notes/", params={"sort": "id", "skip": 2, "limit": 2})
    page2 = [n["id"] for n in r.json()]
    r = client.get("/notes/", params={"sort": "id", "skip": 4, "limit": 2})
    page3 = [n["id"] for n in r.json()]

    assert page1 == ids[0:2]
    assert page2 == ids[2:4]
    assert page3 == ids[4:5]


def test_list_notes_pagination_pages_do_not_overlap_and_cover_all_items(client):
    ids = set(_create_notes(client, 12))

    seen = []
    skip = 0
    limit = 5
    while True:
        r = client.get("/notes/", params={"sort": "id", "skip": skip, "limit": limit})
        assert r.status_code == 200
        page_ids = [n["id"] for n in r.json() if n["id"] in ids]
        if not page_ids:
            break
        seen.extend(page_ids)
        skip += limit

    assert len(seen) == len(set(seen))  # no duplicates across pages
    assert set(seen) == ids


def test_list_notes_pagination_skip_beyond_available_returns_empty(client):
    _create_notes(client, 2)

    r = client.get("/notes/", params={"skip": 1000, "limit": 10})
    assert r.status_code == 200
    assert r.json() == []


def test_list_notes_limit_max_boundary_is_enforced(client):
    r = client.get("/notes/", params={"limit": 200})
    assert r.status_code == 200

    r = client.get("/notes/", params={"limit": 201})
    assert r.status_code == 422


# --- Action items: sorting ----------------------------------------------


def test_list_action_items_sort_by_description_ascending(client):
    _create_action_items(client, 5)

    r = client.get("/action-items/", params={"sort": "description", "limit": 200})
    assert r.status_code == 200
    descriptions = [i["description"] for i in r.json() if i["description"].startswith("Item ")]
    assert descriptions == sorted(descriptions)


def test_list_action_items_sort_by_description_descending(client):
    _create_action_items(client, 5)

    r = client.get("/action-items/", params={"sort": "-description", "limit": 200})
    assert r.status_code == 200
    descriptions = [i["description"] for i in r.json() if i["description"].startswith("Item ")]
    assert descriptions == sorted(descriptions, reverse=True)


def test_list_action_items_default_sort_is_created_at_descending(client):
    ids = _create_action_items(client, 3)

    r = client.get("/action-items/", params={"limit": 200})
    assert r.status_code == 200
    returned_ids = [i["id"] for i in r.json() if i["id"] in ids]
    assert returned_ids == list(reversed(ids))


def test_list_action_items_unknown_sort_field_falls_back_to_created_at_desc(client):
    ids = _create_action_items(client, 3)

    r = client.get("/action-items/", params={"sort": "bogus", "limit": 200})
    assert r.status_code == 200
    returned_ids = [i["id"] for i in r.json() if i["id"] in ids]
    assert returned_ids == list(reversed(ids))


# --- Action items: pagination + filtering --------------------------------


def test_list_action_items_pagination_slices_correctly(client):
    ids = _create_action_items(client, 5)

    r = client.get("/action-items/", params={"sort": "id", "skip": 1, "limit": 2})
    assert r.status_code == 200
    returned_ids = [i["id"] for i in r.json()]
    assert returned_ids == ids[1:3]


def test_list_action_items_completed_filter_combined_with_pagination(client):
    ids = _create_action_items(client, 6, completed_indices={1, 3, 5})

    r = client.get(
        "/action-items/", params={"completed": True, "sort": "id", "skip": 0, "limit": 2}
    )
    assert r.status_code == 200
    completed_ids = [i["id"] for i in r.json()]
    assert completed_ids == [ids[1], ids[3]]

    r = client.get(
        "/action-items/", params={"completed": False, "sort": "id", "limit": 200}
    )
    assert r.status_code == 200
    open_ids = {i["id"] for i in r.json() if i["id"] in ids}
    assert open_ids == {ids[0], ids[2], ids[4]}


def test_list_action_items_pagination_pages_do_not_overlap_and_cover_all_items(client):
    ids = set(_create_action_items(client, 10))

    seen = []
    skip = 0
    limit = 3
    while True:
        r = client.get("/action-items/", params={"sort": "id", "skip": skip, "limit": limit})
        assert r.status_code == 200
        page_ids = [i["id"] for i in r.json() if i["id"] in ids]
        if not page_ids:
            break
        seen.extend(page_ids)
        skip += limit

    assert len(seen) == len(set(seen))
    assert set(seen) == ids


@pytest.mark.parametrize("limit", [1, 50, 200])
def test_list_action_items_various_limits_never_exceed_requested(client, limit):
    _create_action_items(client, 10)

    r = client.get("/action-items/", params={"limit": limit})
    assert r.status_code == 200
    assert len(r.json()) <= limit
