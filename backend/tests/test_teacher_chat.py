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
