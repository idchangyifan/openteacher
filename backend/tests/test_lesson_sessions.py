from fastapi.testclient import TestClient

from app.main import app


def test_lesson_session_can_be_created_and_restored() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": "lesson-test-student",
            "grade": "初一",
            "subject": "数学",
            "title": "一元一次方程课堂",
            "lesson_goal": "学会解释去括号和移项",
            "knowledge_points": ["linear_equation"],
        },
    )

    assert create_response.status_code == 200
    session = create_response.json()
    assert session["id"].startswith("lesson-")
    assert session["mode"] == "active_lesson"
    assert session["current_phase"] == "lesson_start"

    list_response = client.get("/api/v1/lessons", params={"student_id": "lesson-test-student"})
    assert list_response.status_code == 200
    lessons = list_response.json()
    assert lessons[0]["id"] == session["id"]
    assert lessons[0]["title"] == "一元一次方程课堂"

    detail_response = client.get(f"/api/v1/lessons/{session['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["session"]["id"] == session["id"]
    assert detail["messages"][0]["role"] == "teacher"
    assert "今天这节课的目标" in detail["messages"][0]["content"]


def test_teacher_chat_appends_messages_to_lesson_session() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": "lesson-chat-student",
            "subject": "数学",
            "title": "课堂记录测试",
        },
    )
    session_id = create_response.json()["id"]

    chat_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "2(x - 3) = 10，我不会下一步",
            "context": {
                "student_id": "lesson-chat-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": session_id,
            },
        },
    )

    assert chat_response.status_code == 200

    detail_response = client.get(f"/api/v1/lessons/{session_id}")
    detail = detail_response.json()
    roles = [message["role"] for message in detail["messages"]]
    assert roles == ["teacher", "student", "teacher"]
    assert detail["messages"][1]["content"] == "2(x - 3) = 10，我不会下一步"
    assert "已进行 2 轮教师引导和 1 轮学生回应" in detail["session"]["summary"]


def test_unknown_lesson_session_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/lessons/not-found")

    assert response.status_code == 404
