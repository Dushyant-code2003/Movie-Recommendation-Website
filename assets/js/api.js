"use strict";

function getBackendOrigin() {
  const { origin } = window.location;
  if (origin && origin.startsWith("http")) {
    return origin;
  }
  return "http://127.0.0.1:5000";
}

const LOCAL_ORIGIN = getBackendOrigin();
const TMDB_BASE = "https://api.themoviedb.org/3";
const API_BASE = `${LOCAL_ORIGIN}/api/v3`;
const imageBaseURL = `${LOCAL_ORIGIN}/api/images/`;
const api_key = "local";

const rewriteUrl = function (url) {
  if (typeof url !== "string") return url;
  return url.replace(TMDB_BASE, API_BASE);
};

const fetchDataFromServer = function (url, callback, optionalParam) {
  fetch(rewriteUrl(url))
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => callback(data, optionalParam))
    .catch((error) => {
      console.error("MovieMate API error:", error);
    });
};

export { imageBaseURL, api_key, API_BASE, fetchDataFromServer, rewriteUrl, LOCAL_ORIGIN };
