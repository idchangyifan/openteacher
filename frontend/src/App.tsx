import { FormEvent, useEffect, useRef, useState } from "react";
import { BookOpen, History, Plus, RotateCcw, Send, UserRound } from "lucide-react";

type Role = "teacher" | "student";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
};

type StudentContext = {
  student_id: string;
  grade: string;
  subject: string;
  teacher_style: string;
  session_id?: string;
};

type TeacherResponse = {
  reply: string;
  skill_id: string;
  memory_events: { kind: string; summary: string }[];
};

type LessonSessionSummary = {
  id: string;
  title: string;
  subject: string;
  grade: string;
  status: string;
  current_phase: string;
  pending_student_action: string;
  summary: string;
  updated_at: string;
};

type LessonMessage = {
  id: string;
  role: "teacher" | "student" | "system";
  content: string;
  created_at: string;
};

type LessonSession = {
  id: string;
  student_id: string;
  grade: string;
  subject: string;
  title: string;
  lesson_goal: string;
  teacher_style: string;
  current_phase: string;
  pending_student_action: string;
  summary: string;
};

type LessonSessionDetail = {
  session: LessonSession;
  messages: LessonMessage[];
};

const defaultContext: StudentContext = {
  student_id: "demo-student",
  grade: "初一",
  subject: "数学",
  teacher_style: "严格但温暖"
};

const initialMessages: ChatMessage[] = [
  {
    id: "initial",
    role: "teacher",
    content: "把题目或你卡住的步骤发给我。注意，我不会直接给答案；我会先看你到底卡在哪里。"
  }
];

function localTeacherReply(message: string): string {
  if (/(答案|直接告诉|抄)/.test(message)) {
    return "不行。我是老师，不是答案机器。你先写出下一步，我会检查你的推理。";
  }

  if (/(笨|不会|学不会|太难)/.test(message)) {
    return "先别给自己下结论。你告诉我卡在读题、列式、去括号、移项、合并同类项，还是验算？";
  }

  if (/x|[()（）]/.test(message)) {
    return "先停在第一步，不要跳答案。请你写出去括号后的式子，并说明每一项的符号为什么这样变。";
  }

  return "收到。请补充题目原文和你已经写到的步骤，我会先判断你的卡点。";
}

async function askTeacher(message: string, context: StudentContext): Promise<TeacherResponse> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/teacher/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context })
    });

    if (!response.ok) {
      throw new Error("Teacher API request failed");
    }

    return (await response.json()) as TeacherResponse;
  } catch {
    return {
      reply: localTeacherReply(message),
      skill_id: "local-fallback",
      memory_events: [{ kind: "offline", summary: "后端不可用，前端使用本地兜底回复" }]
    };
  }
}

async function createLesson(context: StudentContext): Promise<LessonSession | null> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/lessons`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: context.student_id,
        grade: context.grade,
        subject: context.subject,
        title: `${context.subject}主动课堂`,
        lesson_goal: "先诊断当前水平，再进入一段讲解和练习",
        teacher_style: context.teacher_style,
        mode: "active_lesson"
      })
    });

    if (!response.ok) throw new Error("Create lesson failed");
    return (await response.json()) as LessonSession;
  } catch {
    return null;
  }
}

async function listLessons(studentId: string): Promise<LessonSessionSummary[]> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

  try {
    const response = await fetch(
      `${apiBaseUrl}/api/v1/lessons?student_id=${encodeURIComponent(studentId)}`
    );

    if (!response.ok) throw new Error("List lessons failed");
    return (await response.json()) as LessonSessionSummary[];
  } catch {
    return [];
  }
}

async function getLesson(sessionId: string): Promise<LessonSessionDetail | null> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/lessons/${sessionId}`);

    if (!response.ok) throw new Error("Get lesson failed");
    return (await response.json()) as LessonSessionDetail;
  } catch {
    return null;
  }
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [context, setContext] = useState<StudentContext>(defaultContext);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [activeSkill, setActiveSkill] = useState("未选择");
  const [memoryEvents, setMemoryEvents] = useState<TeacherResponse["memory_events"]>([]);
  const [lessons, setLessons] = useState<LessonSessionSummary[]>([]);
  const [activeLesson, setActiveLesson] = useState<LessonSession | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isThinking]);

  useEffect(() => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

    fetch(`${apiBaseUrl}/api/v1/health`)
      .then((response) => setApiState(response.ok ? "online" : "offline"))
      .catch(() => setApiState("offline"));
  }, []);

  useEffect(() => {
    void refreshLessons();
  }, [context.student_id]);

  async function refreshLessons() {
    const nextLessons = await listLessons(context.student_id);
    setLessons(nextLessons);
  }

  async function ensureLessonSession(): Promise<string | undefined> {
    if (context.session_id) return context.session_id;

    const lesson = await createLesson(context);
    if (!lesson) return undefined;

    setActiveLesson(lesson);
    setContext((current) => ({ ...current, session_id: lesson.id }));
    await refreshLessons();
    return lesson.id;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isThinking) return;

    setInput("");
    setIsThinking(true);
    const sessionId = await ensureLessonSession();
    const requestContext = { ...context, session_id: sessionId };
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "student", content: text }
    ]);

    try {
      const teacherResponse = await askTeacher(text, requestContext);
      setActiveSkill(teacherResponse.skill_id);
      setMemoryEvents(teacherResponse.memory_events);
      setApiState(teacherResponse.skill_id === "local-fallback" ? "offline" : "online");
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "teacher", content: teacherResponse.reply }
      ]);
      await refreshLessons();
    } finally {
      setIsThinking(false);
    }
  }

  function updateContext<Key extends keyof StudentContext>(key: Key, value: StudentContext[Key]) {
    setContext((current) => ({ ...current, [key]: value }));
  }

  async function handleNewLesson() {
    const lesson = await createLesson({ ...context, session_id: undefined });
    if (!lesson) return;

    setActiveLesson(lesson);
    setContext((current) => ({
      ...current,
      session_id: lesson.id,
      grade: lesson.grade,
      subject: lesson.subject,
      teacher_style: lesson.teacher_style
    }));
    setMessages([
      {
        id: "lesson-opening",
        role: "teacher",
        content: `今天这节课的目标是：${lesson.lesson_goal}。我会先诊断，再讲解和练习。`
      }
    ]);
    setMemoryEvents([]);
    setActiveSkill("等待课堂互动");
    await refreshLessons();
  }

  async function handleOpenLesson(sessionId: string) {
    const detail = await getLesson(sessionId);
    if (!detail) return;

    setActiveLesson(detail.session);
    setContext((current) => ({
      ...current,
      session_id: detail.session.id,
      grade: detail.session.grade,
      subject: detail.session.subject,
      teacher_style: detail.session.teacher_style
    }));
    setMessages(
      detail.messages
        .filter((message) => message.role === "teacher" || message.role === "student")
        .map((message) => ({
          id: message.id,
          role: message.role as Role,
          content: message.content
        }))
    );
    setActiveSkill("已恢复历史课堂");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="学生上下文">
        <div className="brand">
          <div className="brand-mark">OT</div>
          <div>
            <h1>OpenTeacher</h1>
            <p>开源 AI 教师</p>
          </div>
        </div>

        <section className="panel">
          <h2>学生画像</h2>
          <label>
            年级
            <select
              value={context.grade}
              onChange={(event) => updateContext("grade", event.target.value)}
            >
              <option>小学四年级</option>
              <option>初一</option>
              <option>初三</option>
              <option>高一</option>
            </select>
          </label>
          <label>
            科目
            <select
              value={context.subject}
              onChange={(event) => updateContext("subject", event.target.value)}
            >
              <option>数学</option>
              <option>语文</option>
              <option>英语</option>
              <option>物理</option>
            </select>
          </label>
          <label>
            教师风格
            <select
              value={context.teacher_style}
              onChange={(event) => updateContext("teacher_style", event.target.value)}
            >
              <option>严格但温暖</option>
              <option>耐心引导</option>
              <option>考试策略型</option>
            </select>
          </label>
        </section>

        <section className="panel">
          <div className="panel-title-row">
            <h2>课堂历史</h2>
            <button
              className="icon-button"
              type="button"
              aria-label="新建课堂"
              onClick={handleNewLesson}
            >
              <Plus size={16} />
            </button>
          </div>
          <div className="lesson-list">
            {lessons.length > 0 ? (
              lessons.slice(0, 5).map((lesson) => (
                <button
                  className={`lesson-item ${
                    context.session_id === lesson.id ? "active" : ""
                  }`}
                  key={lesson.id}
                  type="button"
                  onClick={() => void handleOpenLesson(lesson.id)}
                >
                  <span>
                    <History size={14} />
                    {lesson.title}
                  </span>
                  <small>{lesson.pending_student_action}</small>
                </button>
              ))
            ) : (
              <p className="empty-note">还没有历史课堂。发送第一条消息或新建课堂后会记录在这里。</p>
            )}
          </div>
        </section>

        <section className="panel">
          <h2>记忆摘要</h2>
          <ul className="memory-list">
            {memoryEvents.length > 0 ? (
              memoryEvents.map((event) => (
                <li key={`${event.kind}-${event.summary}`}>
                  <strong>{event.kind}</strong>
                  {event.summary}
                </li>
              ))
            ) : (
              <>
                <li>一元一次方程：移项符号容易错</li>
                <li>需要分步骤检查，不适合直接长讲解</li>
                <li>上次能独立完成去括号</li>
              </>
            )}
          </ul>
        </section>
      </aside>

      <section className="workspace" aria-label="AI 老师对话">
        <header className="topbar">
          <div>
            <p>{context.grade} · {context.subject}</p>
            <h2>{activeLesson?.title ?? "主动课堂"}</h2>
            <span className="skill-id">{activeSkill}</span>
          </div>
          <div className="lesson-status">
            <strong>{activeLesson?.current_phase ?? "lesson_start"}</strong>
            <span>{activeLesson?.pending_student_action ?? "回答老师的第一个诊断问题"}</span>
          </div>
          <div className="topbar-actions">
            <span className={`api-state ${apiState}`}>
              {apiState === "checking" ? "检查中" : apiState === "online" ? "API 在线" : "本地兜底"}
            </span>
            <button
              className="ghost-button"
              type="button"
              aria-label="重置对话"
              onClick={() => {
                setMessages(initialMessages);
                setMemoryEvents([]);
                setActiveSkill("未选择");
                setActiveLesson(null);
                setContext((current) => ({ ...current, session_id: undefined }));
              }}
            >
              <RotateCcw size={18} />
            </button>
          </div>
        </header>

        <div className="chat">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <span>
                {message.role === "teacher" ? <BookOpen size={15} /> : <UserRound size={15} />}
                {message.role === "teacher" ? "AI 老师" : "学生"}
              </span>
              <p>{message.content}</p>
            </article>
          ))}
          {isThinking && <p className="thinking">老师正在判断你的卡点...</p>}
          <div ref={chatEndRef} />
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="例如：2(x - 3) = 10，我不知道下一步怎么做"
            rows={3}
          />
          <button type="submit" disabled={isThinking}>
            <Send size={18} />
            {isThinking ? "判断中" : "发送"}
          </button>
        </form>
      </section>
    </main>
  );
}
