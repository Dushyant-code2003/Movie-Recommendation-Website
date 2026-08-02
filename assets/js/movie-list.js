"use strict";

import { api_key, fetchDataFromServer } from "./api.js";

import { sidebar } from "./sidebar.js";

import { createMovieCard } from "./movie-card.js";

import { search } from "./search.js";

const genreName = window.localStorage.getItem("genreName") || "Popular";
const urlParam = window.localStorage.getItem("urlParam") || "";

const pageContent = document.querySelector("[page-content]");

sidebar();

let currentPage = 1;
let totalPages = 0;

const renderError = function (message) {
  pageContent.innerHTML = `
    <section class="movie-list genre-list">
      <div class="title-wrapper">
        <h1 class="heading">Movies</h1>
      </div>
      <p class="genre">${message}</p>
    </section>
  `;
};

const appendMovies = function (movieListElem, movieList) {
  const gridList = movieListElem.querySelector(".grid-list");

  for (const movie of movieList) {
    const movieCard = createMovieCard(movie);
    gridList.appendChild(movieCard);
  }
};

const discoverUrl = function (page) {
  const params = new URLSearchParams({
    api_key,
    sort_by: "popularity.desc",
    include_adult: "false",
    page,
  });

  return `https://api.themoviedb.org/3/discover/movie?${params.toString()}&${urlParam}`;
};

fetchDataFromServer(discoverUrl(currentPage), function ({ results: movieList, total_pages }) {
  if (!movieList || !movieList.length) {
    renderError(`No ${genreName} movies found.`);
    return;
  }

  totalPages = total_pages;
  document.title = `${genreName} Movies - MovieMate`;

  const movieListElem = document.createElement("section");
  movieListElem.classList.add("movie-list", "genre-list");
  movieListElem.ariaLabel = `${genreName} Movies`;

  movieListElem.innerHTML = `
    <div class="title-wrapper">
      <h1 class="heading">All ${genreName} Movies</h1>
    </div>

    <div class="grid-list"></div>

    <button class="btn load-more" load-more>Load More</button>
  `;

  appendMovies(movieListElem, movieList);
  pageContent.appendChild(movieListElem);

  const loadMoreBtn = movieListElem.querySelector("[load-more]");

  loadMoreBtn.addEventListener("click", function () {
    if (currentPage >= totalPages) {
      this.style.display = "none";
      return;
    }

    currentPage++;
    this.classList.add("loading");

    fetchDataFromServer(discoverUrl(currentPage), ({ results }) => {
      this.classList.remove("loading");
      appendMovies(movieListElem, results || []);
    });
  });
});

search();
