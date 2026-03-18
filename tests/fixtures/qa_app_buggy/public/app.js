import { BADGE_LABELS, badgeClass } from "/src/badge.js";

const preview = document.querySelector("#badge-preview");
const safeButton = document.querySelector("#preview-success");
const riskyButton = document.querySelector("#preview-alert");

if (preview && safeButton) {
  safeButton.addEventListener("click", () => {
    preview.className = badgeClass("success");
    preview.textContent = BADGE_LABELS.success;
  });
}

if (preview && riskyButton) {
  riskyButton.addEventListener("click", () => {
    preview.className = badgeClass("alert");
    preview.textContent = BADGE_LABELS.alert;
  });
}
