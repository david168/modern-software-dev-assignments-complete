def test_create_list_and_patch_notes(client):
    payload = {"title": "Test", "content": "Hello world"}
    r = client.post("/notes/", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Test"
    assert "created_at" in data and "updated_at" in data

    r = client.get("/notes/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1

    r = client.get("/notes/", params={"q": "Hello", "limit": 10, "sort": "-created_at"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1

    note_id = data["id"]
    r = client.patch(f"/notes/{note_id}", json={"title": "Updated"})
    assert r.status_code == 200
    patched = r.json()
    assert patched["title"] == "Updated"


def test_get_note_not_found(client):
    r = client.get("/notes/999999")
    assert r.status_code == 404


def test_create_note_validation_errors(client):
    r = client.post("/notes/", json={"title": "", "content": "Hello"})
    assert r.status_code == 422

    r = client.post("/notes/", json={"title": "Title", "content": ""})
    assert r.status_code == 422

    r = client.post("/notes/", json={"title": "Title"})
    assert r.status_code == 422


def test_patch_note_requires_at_least_one_field(client):
    r = client.post("/notes/", json={"title": "Test", "content": "Hello"})
    note_id = r.json()["id"]

    r = client.patch(f"/notes/{note_id}", json={})
    assert r.status_code == 422


def test_patch_note_not_found(client):
    r = client.patch("/notes/999999", json={"title": "Updated"})
    assert r.status_code == 404


def test_list_notes_invalid_sort_field(client):
    r = client.get("/notes/", params={"sort": "not_a_field"})
    assert r.status_code == 400


def test_list_notes_invalid_pagination(client):
    r = client.get("/notes/", params={"limit": 0})
    assert r.status_code == 422

    r = client.get("/notes/", params={"skip": -1})
    assert r.status_code == 422


def test_delete_note(client):
    r = client.post("/notes/", json={"title": "To delete", "content": "Bye"})
    note_id = r.json()["id"]

    r = client.delete(f"/notes/{note_id}")
    assert r.status_code == 204

    r = client.get(f"/notes/{note_id}")
    assert r.status_code == 404


def test_delete_note_not_found(client):
    r = client.delete("/notes/999999")
    assert r.status_code == 404


