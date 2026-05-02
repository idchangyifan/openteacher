import { FormEvent, useEffect, useRef, useState } from "react";
import { BookOpen, RotateCcw, Send, UserRound } from "lucide-react";

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
};

type TeacherResponse = {
  reply: string;
  skill_id: string;
  memory_events: { kind: string; summary: string }[];
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

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [context, setContext] = useState<StudentContext>(defaultContext);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [activeSkill, setActiveSkill] = useState("未选择");
  const [memoryEvents, setMemoryEvents] = useState<TeacherResponse["memory_events"]>([]);
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isThinking) return;

    setInput("");
    setIsThinking(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "student", content: text }
    ]);

    try {
      const teacherResponse = await askTeacher(text, context);
      setActiveSkill(teacherResponse.skill_id);
      setMemoryEvents(teacherResponse.memory_events);
      setApiState(teacherResponse.skill_id === "local-fallback" ? "offline" : "online");
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "teacher", content: teacherResponse.reply }
      ]);
    } finally {
      setIsThinking(false);
    }
  }

  function updateContext<Key extends keyof StudentContext>(key: Key, value: StudentContext[Key]) {
    setContext((current) => ({ ...current, [key]: value }));
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
            <p>初中数学 · 一元一次方程</p>
            <h2>王老师式严格引导 Skill</h2>
            <span className="skill-id">{activeSkill}</span>
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
