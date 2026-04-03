"use client";

import { useEffect } from "react";
import Clarity from "@microsoft/clarity";

/**
 * Client component that initialises Microsoft Clarity analytics.
 *
 * The Clarity project ID is read from `window.__RUNTIME_CONFIG__` which is
 * injected at request-time by the {@link RuntimeConfig} server component.
 * If no project ID is configured, Clarity is not initialised.
 */
export function ClarityAnalytics() {
  useEffect(() => {
    const projectId = window.__RUNTIME_CONFIG__?.clarityProjectId;
    if (projectId) {
      Clarity.init(projectId);
    }
  }, []);

  return null;
}
