/** Adapter factory for the three M1 feedback sources. */
import { SageError } from "../../core/errors.js";
import type { AdapterDeps, FeedbackProvider, FeedbackSourceAdapter } from "../types.js";
import { GiteaFeedbackAdapter } from "./gitea.js";
import { GitHubFeedbackAdapter } from "./github.js";
import { LocalFeedbackAdapter } from "./local.js";

export { isFeedbackProvider } from "../types.js";

export function createFeedbackAdapter(
  provider: FeedbackProvider,
  deps: AdapterDeps = {},
): FeedbackSourceAdapter {
  switch (provider) {
    case "local":
      return new LocalFeedbackAdapter(deps);
    case "github":
      return new GitHubFeedbackAdapter(deps);
    case "gitea":
      return new GiteaFeedbackAdapter(deps);
    default:
      throw new SageError(`Unknown feedback source: ${String(provider)}`, "E_USAGE", 2);
  }
}
