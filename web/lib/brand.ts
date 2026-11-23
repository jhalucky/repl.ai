export const PRODUCT_NAME = "Repl.ai";

/** Shown on the setup page. Pass ?name=Lucky later for another person. */
export const DEFAULT_OWNER_NAME = "Manav";

export function inboxSetupTitle(name: string = DEFAULT_OWNER_NAME): string {
  const owner = name.trim() || DEFAULT_OWNER_NAME;
  return `${owner}'s Inbox setup`;
}
