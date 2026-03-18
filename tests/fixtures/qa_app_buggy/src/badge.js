export const BADGE_LABELS = {
  alert: "Needs attention",
  info: "Info",
  success: "Healthy",
};

export function badgeClass(variant) {
  switch (variant) {
    case "info":
      return "badge badge--info";
    case "success":
      return "badge badge--success";
    default:
      return "badge badge--info";
  }
}
