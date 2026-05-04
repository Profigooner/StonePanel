def test_list_root(client, auth_headers):
    resp = client.get("/api/files/list?path=/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "/"
    names = [item["name"] for item in data["items"]]
    assert "test.txt" in names
    assert "subdir" in names


def test_list_subdir(client, auth_headers):
    resp = client.get("/api/files/list?path=/subdir", headers=auth_headers)
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()["items"]]
    assert "nested.txt" in names


def test_list_dirs_before_files(client, auth_headers):
    resp = client.get("/api/files/list?path=/", headers=auth_headers)
    items = resp.json()["items"]
    dirs = [i for i in items if i["is_dir"]]
    files = [i for i in items if not i["is_dir"]]
    if dirs and files:
        # All dirs should come before all files in the list
        last_dir_idx = max(items.index(d) for d in dirs)
        first_file_idx = min(items.index(f) for f in files)
        assert last_dir_idx < first_file_idx


def test_list_nonexistent_dir(client, auth_headers):
    resp = client.get("/api/files/list?path=/nope", headers=auth_headers)
    assert resp.status_code == 404


def test_read_file(client, auth_headers):
    resp = client.get("/api/files/read?path=/test.txt", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["content"] == "hello world"


def test_read_nested_file(client, auth_headers):
    resp = client.get(
        "/api/files/read?path=/subdir/nested.txt", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "nested content"


def test_read_nonexistent_file(client, auth_headers):
    resp = client.get("/api/files/read?path=/nope.txt", headers=auth_headers)
    assert resp.status_code == 404


def test_write_file(client, auth_headers):
    resp = client.put(
        "/api/files/write",
        json={"path": "/new_file.txt", "content": "new content"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp = client.get("/api/files/read?path=/new_file.txt", headers=auth_headers)
    assert resp.json()["content"] == "new content"


def test_write_file_in_new_subdir(client, auth_headers):
    resp = client.put(
        "/api/files/write",
        json={"path": "/deep/nested/file.txt", "content": "deep"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp = client.get(
        "/api/files/read?path=/deep/nested/file.txt", headers=auth_headers
    )
    assert resp.json()["content"] == "deep"


def test_delete_file(client, auth_headers):
    resp = client.delete("/api/files/delete?path=/test.txt", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/api/files/read?path=/test.txt", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_directory(client, auth_headers):
    resp = client.delete("/api/files/delete?path=/subdir", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/api/files/list?path=/subdir", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_nonexistent(client, auth_headers):
    resp = client.delete("/api/files/delete?path=/nope", headers=auth_headers)
    assert resp.status_code == 404


def test_mkdir(client, auth_headers):
    resp = client.post(
        "/api/files/mkdir", json={"path": "/newdir"}, headers=auth_headers
    )
    assert resp.status_code == 200

    resp = client.get("/api/files/list?path=/newdir", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_rename_file(client, auth_headers):
    resp = client.post(
        "/api/files/rename",
        json={"old_path": "/test.txt", "new_path": "/renamed.txt"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp = client.get("/api/files/read?path=/renamed.txt", headers=auth_headers)
    assert resp.json()["content"] == "hello world"

    resp = client.get("/api/files/read?path=/test.txt", headers=auth_headers)
    assert resp.status_code == 404


def test_rename_nonexistent(client, auth_headers):
    resp = client.post(
        "/api/files/rename",
        json={"old_path": "/nope.txt", "new_path": "/x.txt"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_file_info(client, auth_headers):
    resp = client.get("/api/files/info?path=/test.txt", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test.txt"
    assert data["is_dir"] is False
    assert data["size"] == len("hello world")


def test_file_info_directory(client, auth_headers):
    resp = client.get("/api/files/info?path=/subdir", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_dir"] is True


def test_upload_file(client, auth_headers):
    resp = client.post(
        "/api/files/upload?path=/uploaded.txt",
        files={"file": ("uploaded.txt", b"uploaded content", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp = client.get("/api/files/read?path=/uploaded.txt", headers=auth_headers)
    assert resp.json()["content"] == "uploaded content"


def test_download_file(client, auth_headers):
    resp = client.get(
        "/api/files/download?path=/test.txt", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.content == b"hello world"


def test_path_traversal_blocked(client, auth_headers):
    resp = client.get(
        "/api/files/list?path=/../../../etc", headers=auth_headers
    )
    assert resp.status_code == 403


def test_path_traversal_read_blocked(client, auth_headers):
    resp = client.get(
        "/api/files/read?path=/../../../etc/passwd", headers=auth_headers
    )
    assert resp.status_code == 403


def test_no_auth_rejected(client):
    resp = client.get("/api/files/list?path=/")
    assert resp.status_code == 401
