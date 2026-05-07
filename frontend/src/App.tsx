import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { BookOpen, History, Plus, RotateCcw, Send, Trash2, UserRound } from "lucide-react";

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
    content: "可以直接说“请开始教学”。我会从七年级数学第一章开始，先做一个小诊断，再进入讲解和练习。"
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

  return "收到。把题目原文和你已经写到的步骤发来，我会接着你的思路往下教。";
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
        lesson_goal: "围绕当前课程位置先诊断，再讲解、练习和复盘",
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

async function deleteLesson(sessionId: string): Promise<boolean> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/lessons/${sessionId}`, {
      method: "DELETE"
    });

    return response.ok;
  } catch {
    return false;
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

  async function refreshLessons(): Promise<LessonSessionSummary[]> {
    const nextLessons = await listLessons(context.student_id);
    setLessons(nextLessons);
    return nextLessons;
  }

  async function ensureLessonSession(message: string): Promise<string | undefined> {
    if (context.session_id) return context.session_id;

    if (looksLikeLessonContinuation(message)) {
      const availableLessons = lessons.length > 0 ? lessons : await refreshLessons();
      const latestLesson = availableLessons[0];
      if (latestLesson) {
        await handleOpenLesson(latestLesson.id);
        return latestLesson.id;
      }
    }

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
    const sessionId = await ensureLessonSession(text);
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

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;

    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  function looksLikeLessonContinuation(message: string): boolean {
    return [
      "上堂课",
      "上节课",
      "上一节",
      "上次",
      "刚才",
      "继续",
      "讲到哪",
      "讲到哪里",
      "讲了什么",
      "学了什么",
      "复习一下",
      "接着"
    ].some((token) => message.includes(token));
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

  async function handleDeleteLesson(sessionId: string) {
    const lesson = lessons.find((item) => item.id === sessionId);
    const confirmed = window.confirm(
      `删除「${lesson?.title ?? "这节课堂"}」的历史记录？已抽取的长期记忆会保留为学习背景。`
    );
    if (!confirmed) return;

    const deleted = await deleteLesson(sessionId);
    if (!deleted) return;

    if (context.session_id === sessionId) {
      setMessages(initialMessages);
      setMemoryEvents([]);
      setActiveSkill("未选择");
      setActiveLesson(null);
      setContext((current) => ({ ...current, session_id: undefined }));
    }
    await refreshLessons();
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
                <div
                  className={`lesson-item ${
                    context.session_id === lesson.id ? "active" : ""
                  }`}
                  key={lesson.id}
                >
                  <button
                    className="lesson-open-button"
                    type="button"
                    onClick={() => void handleOpenLesson(lesson.id)}
                  >
                    <span>
                      <History size={14} />
                      {lesson.title}
                    </span>
                    <small>{lesson.pending_student_action}</small>
                  </button>
                  <button
                    className="lesson-delete-button"
                    type="button"
                    aria-label={`删除${lesson.title}`}
                    title="删除课堂历史"
                    onClick={() => void handleDeleteLesson(lesson.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
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
              <li>暂无新的课堂记忆；开始互动后会在这里更新。</li>
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
            <span>{activeLesson?.pending_student_action ?? "准备继续当前课堂"}</span>
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
          {isThinking && <p className="thinking">老师正在组织下一句...</p>}
          <div ref={chatEndRef} />
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="例如：请开始教学 / 数轴是什么 / 绝对值我不懂"
            rows={3}
          />
          <button type="submit" disabled={isThinking || !input.trim()}>
            <Send size={18} />
            {isThinking ? "思考中" : "发送"}
          </button>
        </form>
      </section>
    </main>
  );
}
