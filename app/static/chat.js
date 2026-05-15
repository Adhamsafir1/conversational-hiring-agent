/**
 * Advanced Conversational Chat UI for SHL Assessment Recommender
 * Features: Dark mode, card-based recommendations, filtering, animations
 */

const chatPanel = document.getElementById("chat-panel");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnReset = document.getElementById("btn-reset");
const themeToggle = document.getElementById("theme-toggle");
const charCount = document.getElementById("char-count");
const modal = document.getElementById("assessment-modal");
const modalClose = document.getElementById("modal-close");
const modalBody = document.getElementById("modal-body");

/** @type {{ role: 'user' | 'assistant', content: string }[]} */
let messages = [];
let conversationEnded = false;
let currentRecommendations = [];

// Theme Management
function initTheme() {
  const savedTheme = localStorage.getItem("theme") || "light";
  document.documentElement.classList.toggle("dark-mode", savedTheme === "dark");
  updateThemeIcon();
}

function updateThemeIcon() {
  const isDark = document.documentElement.classList.contains("dark-mode");
  themeToggle.innerHTML = isDark 
    ? '<i class="fas fa-sun"></i>' 
    : '<i class="fas fa-moon"></i>';
}

function toggleTheme() {
  document.documentElement.classList.toggle("dark-mode");
  const isDark = document.documentElement.classList.contains("dark-mode");
  localStorage.setItem("theme", isDark ? "dark" : "light");
  updateThemeIcon();
}

// Character Counter
userInput.addEventListener("input", (e) => {
  const len = e.target.value.length;
  charCount.textContent = `${len}/500`;
  userInput.style.height = "auto";
  userInput.style.height = `${Math.min(userInput.scrollHeight, 240)}px`;
  
  if (len > 500) {
    e.target.value = e.target.value.substring(0, 500);
  }
});

// Utility Functions
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getAssessmentType(type) {
  const typeMap = {
    K: { name: "Knowledge", class: "knowledge", icon: "fa-book" },
    C: { name: "Competency", class: "competency", icon: "fa-chart-line" },
    Q: { name: "Questionnaire", class: "questionnaire", icon: "fa-form" },
  };
  return typeMap[type] || { name: type, class: "default", icon: "fa-star" };
}

// Recommendations Rendering
function renderAssessmentCard(rec, index) {
  const typeInfo = getAssessmentType(rec.test_type);
  return `
    <div class="assessment-card ${typeInfo.class}" data-id="${index}">
      <div class="card-header">
        <h3 class="card-title">${escapeHtml(rec.name)}</h3>
        <span class="card-badge">${typeInfo.name}</span>
      </div>
      <p class="card-desc">
        <strong>${rec.test_type || "K"}</strong> | 
        <i class="fas fa-clock"></i> ${rec.duration || "Variable"} | 
        <i class="fas fa-globe"></i> ${rec.languages || "English"}
      </p>
      <div class="card-footer">
        <a href="${escapeHtml(rec.url)}" target="_blank" rel="noopener" class="card-link">
          <i class="fas fa-external-link-alt"></i> View Assessment
        </a>
        <div class="card-actions">
          <button class="card-action-btn" title="Save" data-action="save">
            <i class="fas fa-bookmark"></i>
          </button>
          <button class="card-action-btn" title="Details" data-action="details">
            <i class="fas fa-info-circle"></i>
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderRecommendations(recommendations) {
  if (!recommendations || recommendations.length === 0) return "";
  
  currentRecommendations = recommendations;
  
  const cards = recommendations
    .map((rec, i) => renderAssessmentCard(rec, i))
    .join("");

  return `
    <div class="recommendations">
      <div class="rec-header">
        <div class="rec-title">
          <i class="fas fa-check-circle"></i> 
          Recommended Assessments (${recommendations.length})
        </div>
        <div class="rec-controls">
          <select class="rec-filter" id="filter-type" aria-label="Filter by type">
            <option value="">All Types</option>
            <option value="knowledge">Knowledge</option>
            <option value="competency">Competency</option>
            <option value="questionnaire">Questionnaire</option>
          </select>
          <input type="text" class="rec-filter" id="search-recs" placeholder="Search..." style="width: 150px;" aria-label="Search recommendations" />
        </div>
      </div>
      <div class="rec-cards" id="rec-cards">
        ${cards}
      </div>
    </div>`;
}

function attachCardListeners() {
  // Card click for details
  document.querySelectorAll(".card-action-btn[data-action='details']").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const card = btn.closest(".assessment-card");
      const idx = parseInt(card.dataset.id);
      showAssessmentDetails(currentRecommendations[idx]);
    });
  });

  // Save bookmark
  document.querySelectorAll(".card-action-btn[data-action='save']").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const card = btn.closest(".assessment-card");
      const idx = parseInt(card.dataset.id);
      const rec = currentRecommendations[idx];
      btn.innerHTML = '<i class="fas fa-check"></i>';
      btn.style.color = "var(--success)";
      // In a real app, save to localStorage or backend
      console.log("Saved:", rec.name);
    });
  });

  // Filter by type
  const filterType = document.getElementById("filter-type");
  const searchInput = document.getElementById("search-recs");
  
  if (filterType) {
    filterType.addEventListener("change", filterAndSearchCards);
  }
  
  if (searchInput) {
    searchInput.addEventListener("input", filterAndSearchCards);
  }
}

function filterAndSearchCards() {
  const typeFilter = document.getElementById("filter-type")?.value || "";
  const searchTerm = document.getElementById("search-recs")?.value.toLowerCase() || "";
  
  const cards = document.querySelectorAll(".assessment-card");
  cards.forEach(card => {
    const typeMatch = !typeFilter || card.classList.contains(typeFilter);
    const title = card.querySelector(".card-title").textContent.toLowerCase();
    const searchMatch = !searchTerm || title.includes(searchTerm);
    
    card.style.display = (typeMatch && searchMatch) ? "block" : "none";
  });
}

function showAssessmentDetails(assessment) {
  const typeInfo = getAssessmentType(assessment.test_type);
  modalBody.innerHTML = `
    <h2 style="margin-top: 0; color: var(--primary);">
      <i class="fas ${typeInfo.icon}"></i> ${escapeHtml(assessment.name)}
    </h2>
    <p><strong>Type:</strong> ${typeInfo.name}</p>
    <p><strong>Test Type Code:</strong> <code>${assessment.test_type}</code></p>
    <p><strong>Category:</strong> ${assessment.category || "General Assessment"}</p>
    <p><strong>Description:</strong> ${assessment.description || "Professional assessment for evaluating candidate skills and competencies."}</p>
    <p style="margin: 1.5rem 0 0 0; display: flex; gap: 1rem; flex-wrap: wrap;">
      <a href="${escapeHtml(assessment.url)}" target="_blank" class="btn btn-primary" style="flex: 0 0 auto;">
        <i class="fas fa-external-link-alt"></i> Visit Assessment
      </a>
      <button class="btn btn-ghost" onclick="closeModal()" style="flex: 0 0 auto;">
        <i class="fas fa-times"></i> Close
      </button>
    </p>
  `;
  modal.style.display = "flex";
}

function closeModal() {
  modal.style.display = "none";
}

// Message Rendering
function appendMessage(role, content, recommendations = null) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role === "user" ? "user" : "agent"}`;
  
  const recHtml = role === "assistant" 
    ? renderRecommendations(recommendations) 
    : "";
  
  wrap.innerHTML = `
    <span class="role-label">${role === "user" ? "You" : "Agent"}</span>
    <div class="bubble">${escapeHtml(content)}</div>
    ${recHtml}
  `;
  
  chatPanel.appendChild(wrap);
  
  if (recHtml) {
    attachCardListeners();
  }
  
  setTimeout(() => {
    chatPanel.scrollTop = chatPanel.scrollHeight;
  }, 0);
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "message agent";
  el.id = "typing-indicator";
  el.innerHTML = `
    <span class="role-label">Agent</span>
    <div class="typing">
      <span></span>
      <span></span>
      <span></span>
    </div>
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
  el.innerHTML = `<i class="fas fa-exclamation-circle"></i> <span>${escapeHtml(msg)}</span>`;
  chatPanel.appendChild(el);
  chatPanel.scrollTop = chatPanel.scrollHeight;
}

const WELCOME_HTML = `
  <div class="welcome">
    <strong><i class="fas fa-sparkles"></i> Start a Hiring Conversation</strong>
    <p>Paste a job description, answer clarifying questions, refine the shortlist (e.g. "add AWS", "drop OPQ"), then confirm when you're done.</p>
  </div>
`;

function resetChat() {
  messages = [];
  conversationEnded = false;
  chatPanel.innerHTML = WELCOME_HTML;
  userInput.disabled = false;
  btnSend.disabled = false;
  userInput.value = "";
  charCount.textContent = "0/500";
  userInput.focus();
}

// Chat Functionality
async function sendMessage(text) {
  if (!text.trim() || conversationEnded) return;

  appendMessage("user", text.trim());
  messages.push({ role: "user", content: text.trim() });
  userInput.value = "";
  charCount.textContent = "0/500";
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
      showError(`Request failed (${res.status}). Please try again.`);
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
      badge.innerHTML = '<i class="fas fa-check"></i> <span>Conversation complete — start a new chat to continue</span>';
      chatPanel.appendChild(badge);
    }
  } catch (err) {
    hideTyping();
    showError("Could not reach the server. Check your connection and try again.");
    console.error("Chat error:", err);
    messages.pop();
  } finally {
    if (!conversationEnded) btnSend.disabled = false;
    userInput.focus();
  }
}

// Event Listeners
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

btnReset.addEventListener("click", resetChat);
themeToggle.addEventListener("click", toggleTheme);
modalClose.addEventListener("click", closeModal);

window.addEventListener("click", (e) => {
  if (e.target === modal) closeModal();
});

// Initialize
initTheme();
resetChat();
