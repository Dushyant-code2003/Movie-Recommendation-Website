"use strict";

import { imageBaseURL } from "./api.js";

// movie card

export function createMovieCard(movie) {
  const { poster_path, title, vote_average, release_date, id } = movie;
  const posterImage = poster_path
    ? `${imageBaseURL}w342${poster_path}`
    : "./assets/images/poster-bg-icon.png";
  const rating = Number(vote_average || 0).toFixed(1);
  const releaseYear = (release_date && release_date !== "nan") ? release_date.split("-")[0] : "2026";

  const card = document.createElement("div");
  card.classList.add("movie-card");

  card.innerHTML = `
    <figure class="poster-box card-banner">
      <img
        src="${posterImage}"
        alt="${title}"
        class="img-cover"
        loading="lazy"
      />
    </figure>

    <h4 class="title">${title}</h4>

    <div class="meta-list">
      <div class="meta-item">
        <img
          src="./assets/images/star.png"
          width="20"
          height="20"
          loading="lazy"
          alt="rating"
        />
        <span class="span">${rating}</span>
      </div>

      <div class="card-badge">${releaseYear}</div>
    </div>

    <a href="./detail.html?id=${id}" class="card-btn" title="${title}" onclick="getMovieDetail(${id})"></a>
  `;

  return card;
}
