"use strict";

import { LOCAL_ORIGIN, imageBaseURL } from "./api.js";

const QUICK_PROMPTS = [
  "What are the latest 2026 upcoming movies?",
  "Show me top trending movies right now",
  "Recommend a feel-good comedy under 90 minutes",
  "I want an intense sci-fi thriller",
];

const styles = `
  .mm-chat-toggle {
    position: fixed;
    right: 2rem;
    bottom: 2rem;
    z-index: 999;
    width: 5.6rem;
    height: 5.6rem;
    border: none;
    border-radius: 50%;
    background: linear-gradient(135deg, #00d7fd, #05ccef);
    color: #000;
    font-size: 2.2rem;
    font-weight: bold;
    cursor: pointer;
    box-shadow: 0 8px 28px rgba(0, 215, 253, 0.4);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .mm-chat-toggle:hover {
    transform: scale(1.05);
    box-shadow: 0 10px 32px rgba(0, 215, 253, 0.5);
  }
  .mm-chat-panel {
    position: fixed;
    right: 2rem;
    bottom: 8.6rem;
    z-index: 999;
    width: min(420px, calc(100vw - 3rem));
    height: min(600px, calc(100vh - 11rem));
    display: none;
    flex-direction: column;
    background: rgba(18, 18, 26, 0.96);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(0, 215, 253, 0.25);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  }
  .mm-chat-panel.active { display: flex; }
  .mm-chat-header {
    padding: 1.4rem 1.8rem;
    background: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .mm-chat-header h3 {
    color: #fff;
    font-size: 1.7rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
    letter-spacing: 0.5px;
  }
  .mm-chat-header p {
    color: rgba(255, 255, 255, 0.6);
    font-size: 1.2rem;
  }
  .mm-chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1.4rem 1.6rem;
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
  }
  .mm-chat-messages::-webkit-scrollbar {
    width: 6px;
  }
  .mm-chat-messages::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 6px;
  }
  .mm-chat-msg {
    max-width: 90%;
    padding: 1rem 1.4rem;
    border-radius: 14px;
    font-size: 1.35rem;
    line-height: 1.55;
    word-break: break-word;
  }
  .mm-chat-msg.bot {
    align-self: flex-start;
    background: rgba(30, 30, 45, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    border-bottom-left-radius: 4px;
  }
  .mm-chat-msg.user {
    align-self: flex-end;
    background: rgba(0, 215, 253, 0.18);
    border: 1px solid rgba(0, 215, 253, 0.35);
    color: #ffffff;
    border-bottom-right-radius: 4px;
  }
  .mm-chat-cards {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    margin-top: 1rem;
    width: 100%;
  }
  .mm-chat-card-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 0.7rem 0.9rem;
    text-decoration: none;
    color: #fff;
    transition: all 0.2s ease;
  }
  .mm-chat-card-item:hover {
    background: rgba(0, 215, 253, 0.12);
    border-color: rgba(0, 215, 253, 0.4);
    transform: translateY(-2px);
  }
  .mm-chat-card-img {
    width: 44px;
    height: 64px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
    background: #111;
  }
  .mm-chat-card-info {
    flex: 1;
    min-width: 0;
  }
  .mm-chat-card-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 0.4rem;
  }
  .mm-chat-card-meta {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    font-size: 1.1rem;
  }
  .mm-chat-card-badge {
    background: rgba(0, 215, 253, 0.2);
    color: #00d7fd;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-weight: 600;
  }
  .mm-chat-card-rating {
    color: #ffc107;
    font-weight: 600;
  }
  .mm-chat-quick {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    padding: 0.8rem 1.6rem;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(0, 0, 0, 0.15);
  }
  .mm-chat-quick button {
    border: 1px solid rgba(0, 215, 253, 0.35);
    background: rgba(0, 215, 253, 0.06);
    color: #00d7fd;
    border-radius: 999px;
    padding: 0.4rem 0.9rem;
    font-size: 1.15rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .mm-chat-quick button:hover {
    background: rgba(0, 215, 253, 0.2);
    border-color: #00d7fd;
  }
  .mm-chat-form {
    display: flex;
    gap: 0.8rem;
    padding: 1.2rem 1.6rem;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.3);
  }
  .mm-chat-form input {
    flex: 1;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #fff;
    padding: 0.8rem 1.2rem;
    font-size: 1.35rem;
    outline: none;
    transition: border-color 0.2s ease;
  }
  .mm-chat-form input:focus {
    border-color: #00d7fd;
  }
  .mm-chat-form button {
    border: none;
    border-radius: 10px;
    background: #00d7fd;
    color: #000;
    font-weight: 700;
    padding: 0 1.4rem;
    font-size: 1.3rem;
    cursor: pointer;
    transition: background 0.2s ease;
  }
  .mm-chat-form button:hover {
    background: #05ccef;
  }
`;

function injectStyles() {
  if (document.getElementById("mm-chat-styles")) return;
  const node = document.createElement("style");
  node.id = "mm-chat-styles";
  node.textContent = styles;
  document.head.appendChild(node);
}

function createChatMovieCard(movie) {
  const { poster_path, title, vote_average, release_date, id } = movie;
  let posterImage = "./assets/images/poster-bg-icon.png";
  if (poster_path) {
    posterImage = poster_path.startsWith("/tmdb")
      ? `${imageBaseURL}w154${poster_path}`
      : `${imageBaseURL}w154${poster_path}`;
  }
  const rating = Number(vote_average || 0).toFixed(1);
  const releaseYear = release_date ? release_date.split("-")[0] : "2026";

  const card = document.createElement("a");
  card.href = `./detail.html?id=${id}`;
  card.className = "mm-chat-card-item";
  card.title = title;

  card.innerHTML = `
    <img src="${posterImage}" alt="${title}" class="mm-chat-card-img" loading="lazy" />
    <div class="mm-chat-card-info">
      <h5 class="mm-chat-card-title">${title}</h5>
      <div class="mm-chat-card-meta">
        <span class="mm-chat-card-badge">${releaseYear}</span>
        <span class="mm-chat-card-rating">⭐ ${rating}</span>
      </div>
    </div>
  `;

  return card;
}

function createWidget() {
  injectStyles();

  const toggle = document.createElement("button");
  toggle.className = "mm-chat-toggle";
  toggle.type = "button";
  toggle.title = "MovieMate AI";
  toggle.textContent = "AI";

  const panel = document.createElement("section");
  panel.className = "mm-chat-panel";
  panel.innerHTML = `
    <div class="mm-chat-header">
      <h3>MovieMate AI</h3>
      <p>AI Concierge · Live TMDb & Machine Learning Recommendations</p>
    </div>
    <div class="mm-chat-messages"></div>
    <div class="mm-chat-quick"></div>
    <form class="mm-chat-form">
      <input type="text" placeholder="Ask for a movie or ask about 2026 upcoming releases..." autocomplete="off" />
      <button type="submit">Send</button>
    </form>
  `;

  document.body.appendChild(toggle);
  document.body.appendChild(panel);

  const messages = panel.querySelector(".mm-chat-messages");
  const quick = panel.querySelector(".mm-chat-quick");
  const form = panel.querySelector(".mm-chat-form");
  const input = form.querySelector("input");

  toggle.addEventListener("click", () => {
    panel.classList.toggle("active");
    if (panel.classList.contains("active") && !messages.dataset.ready) {
      appendMessage(
        messages,
        "bot",
        "Hi! Ask me for movie recommendations by mood, genre, or runtime, or ask me about 2026 upcoming movies and trending releases!"
      );
      messages.dataset.ready = "true";
    }
  });

  for (const prompt of QUICK_PROMPTS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = prompt;
    btn.addEventListener("click", () => sendMessage(prompt));
    quick.appendChild(btn);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value.trim());
    input.value = "";
  });

  async function sendMessage(text) {
    if (!text) return;
    appendMessage(messages, "user", text);
    appendMessage(messages, "bot", "Searching the catalog...");

    try {
      const response = await fetch(`${LOCAL_ORIGIN}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await response.json();
      messages.lastElementChild?.remove();
      appendMessage(messages, "bot", data.answer || "No answer returned.", data.movies || []);
    } catch (error) {
      messages.lastElementChild?.remove();
      appendMessage(
        messages,
        "bot",
        "Could not reach MovieMate AI. Make sure the Flask backend is running."
      );
    }

    messages.scrollTop = messages.scrollHeight;
  }
}

function appendMessage(container, role, text, movies = []) {
  const bubble = document.createElement("div");
  bubble.className = `mm-chat-msg ${role}`;
  bubble.textContent = text.replace(/\*\*(.*?)\*\*/g, "$1");

  if (movies && movies.length) {
    const grid = document.createElement("div");
    grid.className = "mm-chat-cards";
    for (const movie of movies) {
      grid.appendChild(createChatMovieCard(movie));
    }
    bubble.appendChild(grid);
  }

  container.appendChild(bubble);
}

createWidget();
