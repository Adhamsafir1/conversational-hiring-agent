/**
 * Conversational chat UI for SHL Assessment Recommender.
 * Maintains full message history and posts to POST /chat (stateless API).
 */

const chatPanel = document.getElementById("chat-panel");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnReset = document.getElementById("btn-reset");

/** @type {{ role: 'user' | 'assistant', content: string }[]} */
let messages = [];
let conversationEnded = false;

const WELCOME_HTML = `
  <div class="welcome">
    <strong>Start a hiring conversation</strong><br />
    Paste a job description, answer clarifying questions, refine the shortlist
    (e.g. “add AWS”, “drop OPQ”, “keep Verify G+”), then confirm when you’re done.
  </div>
`;

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderRecommendations(recommendations) {
  if (!recommendations || recommendations.length === 0) return "";

  const rows = recommendations
    .map(
      (rec, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(rec.name)}</td>
      <td>${escapeHtml(rec.test_type || "—")}</td>
      <td><a href="${escapeHtml(rec.url)}" target="_blank" rel="noopener">View</a></td>
    </tr>`
    )
    .join("");

  return `
    <div class="recommendations">
      <p class="rec-title">Recommended assessments</p>
      <div class="rec-table-wrap">
        <table class="rec-table">
          <thead>
            <tr><th>#</th><th>Name</th><th>Type</th><th>URL</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function appendMessage(role, content, recommendations = null) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role === "user" ? "user" : "agent"}`;
  wrap.innerHTML = `
    <span class="role-label">${role === "user" ? "You" : "Agent"}</span>
    <div class="bubble">${escapeHtml(content)}</div>
    ${role === "assistant" ? renderRecommendations(recommendations) : ""}
  `;
  chatPanel.appendChild(wrap);
  chatPanel.scrollTop = chatPanel.scrollHeight;
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "message agent";
  el.id = "typing-indicator";
  el.innerHTML = `
    <span class="role-label">Agent</span>
    <div class="typing"><span></span><span></span><span></span></div>
  `;
  chatPanel.appendChild(el);
  chatPanel.scrollTop = chatPanel.scrollHeight;
}

function hideTyping() {
  document.getElementById("typing-indicator")?.remove();
}

function showError(msg) {
  const el = document.createElement("div");
  el.className = "error-banner";
  el.textContent = msg;
  chatPanel.appendChild(el);
  chatPanel.scrollTop = chatPanel.scrollHeight;
}

function resetChat() {
  messages = [];
  conversationEnded = false;
  chatPanel.innerHTML = WELCOME_HTML;
  userInput.disabled = false;
  btnSend.disabled = false;
  userInput.focus();
}

async function sendMessage(text) {
  if (!text.trim() || conversationEnded) return;

  appendMessage("user", text.trim());
  messages.push({ role: "user", content: text.trim() });
  userInput.value = "";
  userInput.style.height = "auto";

  btnSend.disabled = true;
  showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });

    hideTyping();

    if (!res.ok) {
      showError(`Request failed (${res.status}). Try again in a moment.`);
      messages.pop();
      return;
    }

    const data = await res.json();
    const reply = data.reply || "";
    messages.push({ role: "assistant", content: reply });
    appendMessage("assistant", reply, data.recommendations);

    if (data.end_of_conversation) {
      conversationEnded = true;
      userInput.disabled = true;
      btnSend.disabled = true;
      const badge = document.createElement("div");
      badge.className = "end-badge";
      badge.textContent = "Conversation complete — start a new chat to continue";
      chatPanel.appendChild(badge);
    }
  } catch (err) {
    hideTyping();
    showError("Could not reach the server. Check your connection and try again.");
    messages.pop();
  } finally {
    if (!conversationEnded) btnSend.disabled = false;
    userInput.focus();
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(userInput.value);
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = `${Math.min(userInput.scrollHeight, 200)}px`;
});

btnReset.addEventListener("click", resetChat);

resetChat();
