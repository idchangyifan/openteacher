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


def test_teacher_chat_acknowledges_correct_answer_before_requesting_reason() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "2(x-3)=10，我算出来 x=8"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "正确" in body["reply"]
    assert "不需要从头重写" in body["reply"]
    assert "一句话" in body["reply"]
    assert "去括号后的式子" not in body["reply"]


def test_teacher_chat_advances_after_correct_answer_with_check() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={"message": "2(x-3)=10，我算出来 x=8，代入左边右边都是10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "正确" in body["reply"]
    assert "代入检验也通过" in body["reply"]
    assert "换一道同类型题" in body["reply"]


def test_teacher_chat_does_not_force_physics_question_into_math_skill() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "我想开始学浮力，不是做题",
            "context": {
                "student_id": "subject-inference-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "opent-teacher-general"


def test_teacher_chat_keeps_current_generated_skill_for_short_followup() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": "short-context-student",
            "grade": "初一",
            "subject": "数学",
            "title": "七上第一章课堂",
            "lesson_goal": "学习正数和负数",
        },
    )
    session_id = create_response.json()["id"]

    start_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "请开始教学",
            "context": {
                "student_id": "short-context-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": session_id,
            },
        },
    )
    followup_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "我不知道",
            "context": {
                "student_id": "short-context-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": session_id,
            },
        },
    )

    assert start_response.status_code == 200
    assert followup_response.status_code == 200
    assert start_response.json()["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert followup_response.json()["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert followup_response.json()["skill_id"] != "opent-teacher-junior-math-linear-equation"

    detail_response = client.get(f"/api/v1/lessons/{session_id}")
    session = detail_response.json()["session"]
    assert session["current_skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert session["current_knowledge_point_id"] == "kp-positive-negative-numbers"
    assert session["current_chapter_id"] == "ch1"


def test_teacher_chat_uses_recent_lesson_for_last_class_recall_without_session() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": "last-class-recall-student",
            "grade": "初一",
            "subject": "数学",
            "title": "正负数课堂",
            "lesson_goal": "理解正数和负数表示相反意义的量",
        },
    )
    session_id = create_response.json()["id"]
    start_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "请开始教学",
            "context": {
                "student_id": "last-class-recall-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": session_id,
            },
        },
    )

    recall_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "上堂课我们讲到哪儿了？",
            "context": {
                "student_id": "last-class-recall-student",
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
            },
        },
    )

    assert start_response.status_code == 200
    assert recall_response.status_code == 200
    assert recall_response.json()["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert recall_response.json()["skill_id"] != "opent-teacher-junior-math-linear-equation"

    detail_response = client.get(f"/api/v1/lessons/{session_id}")
    messages = detail_response.json()["messages"]
    assert messages[-2]["content"] == "上堂课我们讲到哪儿了？"


def test_teacher_chat_uses_recent_lesson_skill_for_empty_new_session_recall() -> None:
    client = TestClient(app)
    student_id = "empty-new-session-recall-student"
    previous_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": student_id,
            "grade": "初一",
            "subject": "数学",
            "title": "正负数课堂",
            "lesson_goal": "理解正数和负数表示相反意义的量",
        },
    )
    previous_session_id = previous_response.json()["id"]
    start_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "请开始教学",
            "context": {
                "student_id": student_id,
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": previous_session_id,
            },
        },
    )
    new_response = client.post(
        "/api/v1/lessons",
        json={
            "student_id": student_id,
            "grade": "初一",
            "subject": "数学",
            "title": "数学主动课堂",
            "lesson_goal": "围绕当前课程位置先诊断，再讲解、练习和复盘",
        },
    )
    new_session_id = new_response.json()["id"]

    recall_response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "上节课讲哪儿啦？",
            "context": {
                "student_id": student_id,
                "grade": "初一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
                "session_id": new_session_id,
            },
        },
    )

    assert start_response.status_code == 200
    assert recall_response.status_code == 200
    assert recall_response.json()["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert recall_response.json()["skill_id"] != "opent-teacher-junior-math-linear-equation"

    detail_response = client.get(f"/api/v1/lessons/{new_session_id}")
    session = detail_response.json()["session"]
    assert session["current_skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert session["current_knowledge_point_id"] == "kp-positive-negative-numbers"


def test_teacher_chat_asks_placement_when_grade_is_not_covered() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "请开始教学",
            "context": {
                "student_id": "placement-grade-student",
                "grade": "高一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert "完全没学过正数和负数" in body["reply"]
    assert "已经会了想学后面的内容" in body["reply"]


def test_teacher_chat_responds_to_negative_number_sequence_question_with_placement() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/teacher/chat",
        json={
            "message": "不是应该先教负数吗？",
            "context": {
                "student_id": "placement-question-student",
                "grade": "高一",
                "subject": "数学",
                "teacher_style": "严格但温暖",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert "你问得对" in body["reply"]
    assert "完全没学过正数和负数" in body["reply"]
