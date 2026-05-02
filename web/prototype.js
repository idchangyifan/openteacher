const chat = document.querySelector("#chat");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#studentInput");
const resetButton = document.querySelector("#resetButton");

const initialTeacherText =
  "把题目或你卡住的步骤发给我。注意，我不会直接给答案；我会先看你到底卡在哪里。";

function addMessage(role, text, variant = "") {
  const article = document.createElement("article");
  article.className = `message ${role} ${variant}`.trim();

  const label = document.createElement("span");
  label.textContent = role === "student" ? "学生" : "AI 老师";

  const body = document.createElement("p");
  body.textContent = text;

  article.append(label, body);
  chat.append(article);
  chat.scrollTop = chat.scrollHeight;
}

function teacherReply(text) {
  const normalized = text.trim();

  if (!normalized) {
    return "先别急着空着发。把题目、你写到的步骤，或者你最不确定的一步发出来。";
  }

  if (/(答案|直接告诉|别讲|抄)/.test(normalized)) {
    return "不行。我的任务是教会你，不是帮你抄答案。你先写出下一步，我会帮你检查哪里错。";
  }

  if (/(笨|不会|学不会|太难)/.test(normalized)) {
    return "这不是笨。我们先定位问题。你现在卡在读题、去括号、移项、合并同类项，还是最后检查？只回答一个也可以。";
  }

  if (/[（(].*[）)]/.test(normalized) || /x/.test(normalized)) {
    return "好，先停在第一步。你不要跳到答案。请你先写出去括号后的式子，并说明每一项的符号为什么这样变。";
  }

  return "我看到了。现在请你补充两件事：题目原文，以及你已经写到哪一步。没有这两项，我不能负责任地判断你的卡点。";
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const text = input.value.trim();
  addMessage("student", text || "（空白输入）");
  addMessage("teacher", teacherReply(text));
  input.value = "";
  input.focus();
});

resetButton.addEventListener("click", () => {
  chat.innerHTML = "";
  addMessage("teacher", initialTeacherText);
  input.focus();
});

