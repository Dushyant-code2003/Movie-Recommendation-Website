"use strict";

import { api_key, imageBaseURL, fetchDataFromServer, API_BASE, LOCAL_ORIGIN } from "./api.js";

import { sidebar } from "./sidebar.js";

import { createMovieCard } from "./movie-card.js";

import { search } from "./search.js";

const urlMovieId = new URLSearchParams(window.location.search).get("id");
const movieId = urlMovieId || window.localStorage.getItem("movieId");

const pageContent = document.querySelector("[page-content]");
const ML_API_BASE_URL = LOCAL_ORIGIN;
const USER_PROFILE_KEY = "moviemateUserActivity";
const DEFAULT_USER = "Guest";

sidebar();

if (urlMovieId) {
  window.localStorage.setItem("movieId", urlMovieId);
}

const renderMessage = function (title, message) {
  pageContent.innerHTML = `
    <section class="movie-list genre-list">
      <div class="title-wrapper">
        <h1 class="heading">${title}</h1>
      </div>
      <p class="genre">${message}</p>
      <a href="./index.html" class="btn">Back To Home</a>
    </section>
  `;
};

const fetchJSON = async function (url, options) {
  const response = await fetch(url, options);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
};

const getUserProfile = function () {
  const savedProfile = window.localStorage.getItem(USER_PROFILE_KEY);

  if (!savedProfile) {
    return { user: DEFAULT_USER, watched: [] };
  }

  try {
    const profile = JSON.parse(savedProfile);
    return {
      user: profile.user || DEFAULT_USER,
      watched: Array.isArray(profile.watched) ? profile.watched : [],
    };
  } catch (error) {
    return { user: DEFAULT_USER, watched: [] };
  }
};

const saveWatchedMovie = function (movie) {
  const profile = getUserProfile();
  const watchedWithoutCurrent = profile.watched.filter(
    ({ id, title }) => id !== movie.id && title !== movie.title
  );

  profile.watched = [
    {
      id: movie.id,
      title: movie.title,
      genres: movie.genres.map(({ name }) => name),
      watchedAt: new Date().toISOString(),
    },
    ...watchedWithoutCurrent,
  ].slice(0, 20);

  window.localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));

  return profile;
};

const findMovieOnTmdb = async function (title) {
  const data = await fetchJSON(
    `${API_BASE}/search/movie?api_key=${api_key}&query=${encodeURIComponent(
      title
    )}&include_adult=false&page=1`
  );

  const exactMatch = data.results.find(
    (movie) => movie.title.toLowerCase() === title.toLowerCase()
  );

  return exactMatch || data.results[0];
};

const getTmdbMoviesFromTitles = async function (titles) {
  const movies = await Promise.all(
    titles.map((title) =>
      findMovieOnTmdb(title).catch((error) => {
        console.error(`Could not fetch TMDb details for ${title}:`, error);
        return null;
      })
    )
  );

  return movies.filter(Boolean);
};

const getGenres = function (genreList) {
  const newGenreList = [];

  for (const { name } of genreList) newGenreList.push(name);
  return newGenreList.join(", ");
};

const getCasts = function (castList) {
  const newCastList = [];

  for (let i = 0, len = castList.length; i < len && len && i < 10; i++) {
    const { name } = castList[i];
    newCastList.push(name);
  }
  return newCastList.join(", ");
};

const getDirectors = function (crewList) {
  const directors = crewList.filter(({ job }) => job === "Director");

  const directorList = [];
  for (const { name } of directors) directorList.push(name);
  return directorList.join(", ");
};

// returns only trailers and teasers as array
const filterVideos = function (videoList) {
  return videoList.filter(
    ({ type, site }) =>
      (type === "Trailer" || type === "Teaser") && site === "Youtube"
  );
};

if (!movieId) {
  renderMessage(
    "Movie Not Selected",
    "Please open a movie from the home page, search results, or a genre list."
  );
} else {
fetchDataFromServer(
  `${API_BASE}/movie/${movieId}?api_key=${api_key}&append_to_response=casts,videos,images,releases`,
  function (movie) {
    if (!movie || movie.success === false || !movie.id) {
      renderMessage(
        "Movie Details Not Found",
        "TMDb did not return details for this movie. Try opening another movie."
      );
      return;
    }

    const id = movie.id;
    const backdrop_path = movie.backdrop_path;
    const poster_path = movie.poster_path;
    const title = movie.title || movie.name || "Untitled";
    const release_date = movie.release_date || "";
    const runtime = movie.runtime ? `${movie.runtime}m` : "N/A";
    const vote_average = Number(movie.vote_average || 0).toFixed(1);
    const certification =
      movie.releases?.countries?.find(({ certification }) => certification)
        ?.certification || "NR";
    const genres = movie.genres || [];
    const overview = movie.overview || "No overview available.";
    const cast = movie.casts?.cast || [];
    const crew = movie.casts?.crew || [];
    const videos = movie.videos?.results || [];
    const backdropImage = backdrop_path || poster_path;
    const posterImage = poster_path
      ? `${imageBaseURL}w342${poster_path}`
      : "./assets/images/poster-bg-icon.png";
    const releaseYear = release_date ? release_date.split("-")[0] : "N/A";
    const userProfile = saveWatchedMovie({ id, title, genres });

    document.title = `${title} - MovieMate`;

    const movieDetail = document.createElement("div");
    movieDetail.classList.add("movie-detail");
    movieDetail.innerHTML = `
                <div 
                class="backdrop-image" 
                style="background-image: url('${
                  backdropImage
                    ? `${imageBaseURL}w1280${backdropImage}`
                    : "./assets/images/poster-bg-icon.png"
                }')">
                </div>

                <figure class="poster-box movie-poster">
                <img
                    src="${posterImage}"
                    alt="${title} poster"
                    class="img-cover"
                />
                </figure>

                <div class="detail-box">
                <div class="detail-content">
                    <h1 class="heading">${title}</h1>

                    <div class="meta-list">
                    <div class="meta-item">
                        <img
                        src="./assets/images/star.png"
                        width="20"
                        height="20"
                        alt="rating"
                        />
                        <span class="span">${vote_average}</span>
                    </div>

                    <div class="separator"></div>

                    <div class="meta-item">${runtime}</div>

                    <div class="separator"></div>

                    <div class="meta-item">${releaseYear}</div>

                    <div class="meta-item card-badge">${certification}</div>
                    </div>

                    <p class="genre">${getGenres(genres)}</p>

                    <p class="overview">${overview}</p>

                    <ul class="detail-list">
                    <div class="list-item">
                        <p class="list-name">Starring</p>
                        <p>${getCasts(cast)}</p>
                    </div>

                    <div class="list-item">
                        <p class="list-name">Directed By</p>
                        <p>${getDirectors(crew)}</p>
                    </div>
                    </ul>
                </div>

                

  <section class="trailer-section movie-list">
    <h2>Trailer and Clips</h2>
    <div id="trailer-container">
    </div>
  </section>

                <div class="slider-list">
                    <div class="slider-inner"></div>
                </div>
                </div>
    `;

    pageContent.appendChild(movieDetail);

function embedTrailer(key, movieTitle) {
  const trailerContainer = document.getElementById("trailer-container");
  if (!trailerContainer) return;

  trailerContainer.innerHTML = `
    <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:16px;max-width:780px;box-shadow:0 8px 24px rgba(0,0,0,0.5);margin-bottom:12px;">
      <iframe
        style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"
        src="https://www.youtube-nocookie.com/embed/${key}?rel=0&modestbranding=1"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
        title="${movieTitle} trailer">
      </iframe>
    </div>
    <div style="display:flex;align-items:center;gap:12px;margin-top:8px;">
      <a class="btn" href="https://www.youtube.com/watch?v=${key}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:8px;padding:8px 16px;font-size:14px;border-radius:8px;">
        <img src="./assets/images/play_circle.png" width="18" height="18" alt="play" />
        Watch on YouTube
      </a>
    </div>
  `;
}

function embedTrailerFallback(movieTitle) {
  const trailerContainer = document.getElementById("trailer-container");
  if (!trailerContainer) return;

  const query = encodeURIComponent(`${movieTitle} official trailer`);
  trailerContainer.innerHTML = `
    <div style="max-width:780px;border-radius:16px;overflow:hidden;background:#1a1a24;padding:24px;text-align:center;">
      <a class="btn" href="https://www.youtube.com/results?search_query=${query}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;justify-content:center;gap:12px;padding:12px 24px;">
        Watch ${movieTitle} Trailer on YouTube
      </a>
    </div>
  `;
}

async function fetchTrailer(movieTitle) {
  const trailerContainer = document.getElementById("trailer-container");
  if (trailerContainer) {
    trailerContainer.innerHTML = `<p class="genre">Loading trailer...</p>`;
  }

  try {
    const response = await fetch(
      `${API_BASE}/movie/${id}/videos?api_key=${api_key}&language=en-US`
    );

    if (!response.ok) throw new Error(`Trailer request failed: ${response.status}`);

    const data = await response.json();
    const trailer = data.results.find((video) => video.type === "Trailer") || data.results[0];
    if (trailer?.key) {
      embedTrailer(trailer.key, movieTitle);
      return;
    }
  } catch (error) {
    console.error("Error fetching trailer:", error);
  }

  embedTrailerFallback(movieTitle);
}

const initialTrailer = videos.find((v) => v.type === "Trailer") || videos[0];
if (initialTrailer?.key) {
  embedTrailer(initialTrailer.key, title);
} else {
  fetchTrailer(title);
}

    for (const { key, name } of filterVideos(videos)) {
      const videoCard = document.createElement("div");
      videoCard.classList.add("video-card");

      videoCard.innerHTML = `
        <iframe width="500" height="294" src="https://www.youtube.com/embed/${key}?&theme=dark&color=white&rel=0" frameborder="0" allowfullscreen="1" title="${name}" class="img-cover" loading="lazy"></iframe>
        `;

      movieDetail.querySelector(".slider-inner").appendChild(videoCard);
    }
    addHybridRecommendations(movie, userProfile);
  }
);
}

const addHybridRecommendations = async function (movie, userProfile) {
  try {
    const mlMovies = await fetchJSON(
      `${ML_API_BASE_URL}/recommend/${encodeURIComponent(movie.title)}?detailed=true`
    );

    if (!mlMovies.length) {
      throw new Error(`No ML recommendations found for ${movie.title}`);
    }

    addSuggestedMovies({
      results: mlMovies,
      title: `AI Picks Similar To ${movie.title}`,
      emptyMessage: "No ML recommendations found for this movie.",
    });
  } catch (error) {
    console.error("ML recommendations unavailable, using TMDb fallback:", error);

    fetchDataFromServer(
      `${API_BASE}/movie/${movieId}/recommendations?api_key=${api_key}&page=1`,
      function (data) {
        addSuggestedMovies({
          ...data,
          title: "You May Also Like",
          emptyMessage:
            "No recommendations found for this movie yet. Try another title.",
        });
      }
    );
  }

  if (userProfile.watched.length < 2) return;

  try {
    const historyMovies = await fetchJSON(`${ML_API_BASE_URL}/recommend/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: userProfile.user,
        watched: userProfile.watched.map(({ title }) => title),
        limit: 10,
        detailed: true,
      }),
    });

    addSuggestedMovies({
      results: historyMovies,
      title: "Based On Your Watch History",
      emptyMessage: "Watch a few more movies to improve personalization.",
    });
  } catch (error) {
    console.error("Personalized recommendations unavailable:", error);
  }
};

const addSuggestedMovies = function ({
  results: movieList,
  title = "You May Also Like",
  emptyMessage = "No movies found.",
}) {
  const movieListElem = document.createElement("section");
  movieListElem.classList.add("movie-list");
  movieListElem.ariaLabel = title;

  movieListElem.innerHTML = `
    <div class="title-wrapper">
      <h3 class="title-large">${title}</h3>
    </div>

    <div class="slider-list">
      <div class="slider-inner"></div>
    </div>
  `;

  if (!movieList.length) {
    movieListElem.querySelector(".slider-inner").innerHTML = `
      <p class="genre">${emptyMessage}</p>
    `;
    pageContent.appendChild(movieListElem);
    return;
  }

  for (const movie of movieList) {
    // Called from movie_card.js
    const movieCard = createMovieCard(movie);

    movieListElem.querySelector(".slider-inner").appendChild(movieCard);
  }
  pageContent.appendChild(movieListElem);
};

search();
