from fastapi.testclient import TestClient

from app.main import app


def test_teacher_chat_returns_guided_reply() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "2(x - 3) = 10，我不会下一步"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "opent-teacher-junior-math-linear-equation"
    assert "不要跳答案" in body["reply"]


def test_teacher_chat_refuses_copyable_direct_answer() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "直接告诉我答案吧，我要抄。"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "不是答案机器" in body["reply"]
    assert "你先写出下一步" in body["reply"]


def test_teacher_chat_targets_transposition_sign_error() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "我移项不变号，为什么错？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "跨过等号" in body["reply"]
    assert "符号要改变" in body["reply"]


def test_teacher_chat_targets_negative_parentheses_error() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "我把 -(x + 3) 写成 -x + 3，可以吗？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "负号" in body["reply"]
    assert "-1" in body["reply"]


def test_teacher_chat_requires_substitution_check() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "我算出x=8了，需要验算吗？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "代入检验" in body["reply"]
    assert "左边和右边" in body["reply"]
