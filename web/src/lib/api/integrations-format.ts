/** Pure formatters for integrations UI (safe for node:test without fetch). */

export function statusLabel(status: string): string {
  switch (status) {
    case "CONNECTED":
    case "SYNCED":
      return "Connected";
    case "CONNECTING":
      return "Connecting";
    case "SYNCING":
      return "Syncing";
    case "ERROR":
      return "Error";
    case "REAUTH_REQUIRED":
      return "Reauthorization required";
    case "DISABLED":
      return "Disabled";
    case "DISCONNECTED":
    default:
      return "Disconnected";
  }
}
