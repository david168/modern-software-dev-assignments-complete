def test_create_and_list_tags(client):
    r = client.post("/tags/", json={"name": "work"})
    assert r.status_code == 201, r.text
    tag = r.json()
    assert tag["name"] == "work"
    assert "created_at" in tag and "updated_at" in tag

    r = client.get("/tags/")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "work" in names


def test_create_duplicate_tag_conflicts(client):
    r = client.post("/tags/", json={"name": "duplicate"})
    assert r.status_code == 201

    r = client.post("/tags/", json={"name": "duplicate"})
    assert r.status_code == 409


def test_get_tag_not_found(client):
    r = client.get("/tags/999999")
    assert r.status_code == 404


def test_delete_tag(client):
    r = client.post("/tags/", json={"name": "temp"})
    tag_id = r.json()["id"]

    r = client.delete(f"/tags/{tag_id}")
    assert r.status_code == 204

    r = client.get(f"/tags/{tag_id}")
    assert r.status_code == 404


def test_attach_and_detach_tag_to_note(client):
    r = client.post("/notes/", json={"title": "Note", "content": "Body"})
    note_id = r.json()["id"]
    assert r.json()["tags"] == []

    r = client.post("/tags/", json={"name": "important"})
    tag_id = r.json()["id"]

    r = client.post(f"/notes/{note_id}/tags/{tag_id}")
    assert r.status_code == 200
    note = r.json()
    assert [t["name"] for t in note["tags"]] == ["important"]

    # Attaching the same tag again is idempotent.
    r = client.post(f"/notes/{note_id}/tags/{tag_id}")
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 1

    r = client.delete(f"/notes/{note_id}/tags/{tag_id}")
    assert r.status_code == 200
    assert r.json()["tags"] == []


def test_attach_tag_to_missing_note_returns_404(client):
    r = client.post("/tags/", json={"name": "orphan"})
    tag_id = r.json()["id"]

    r = client.post(f"/notes/999999/tags/{tag_id}")
    assert r.status_code == 404


def test_attach_missing_tag_to_note_returns_404(client):
    r = client.post("/notes/", json={"title": "Note", "content": "Body"})
    note_id = r.json()["id"]

    r = client.post(f"/notes/{note_id}/tags/999999")
    assert r.status_code == 404
