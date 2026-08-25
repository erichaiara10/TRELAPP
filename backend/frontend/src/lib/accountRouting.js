// Current-phase account routing. Add future public subcategories here only
// after their categories, approval rules and dashboards have been agreed.
export const ACCOUNT_WORKSPACES = Object.freeze({
  STAFF: "/admin",
  PROPERTY_ADVERTISER: "/advertiser",
});

export function workspaceForUser(user) {
  return ACCOUNT_WORKSPACES[user?.account_category] || "/";
}

export function destinationForUser(user, requestedPath = "") {
  const workspace = workspaceForUser(user);
  if (workspace === "/") return "/";
  const belongsToWorkspace = requestedPath === workspace
    || requestedPath.startsWith(`${workspace}/`)
    || requestedPath.startsWith(`${workspace}?`);
  return belongsToWorkspace ? requestedPath : workspace;
}
