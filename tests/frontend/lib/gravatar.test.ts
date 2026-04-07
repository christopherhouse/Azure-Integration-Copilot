/**
 * Tests for the `getGravatarUrl` helper in @/lib/gravatar.
 *
 * Verifies that:
 * 1. Returns a correctly formatted Gravatar URL.
 * 2. Trims and lowercases the email before hashing.
 * 3. Uses the default size of 80 when none is specified.
 * 4. Accepts a custom size parameter.
 * 5. Accepts a custom fallback parameter.
 * 6. Produces deterministic hashes for the same email.
 */

// Polyfill globals that jsdom may not provide
import { webcrypto } from "node:crypto";
import { TextEncoder as NodeTextEncoder } from "node:util";

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", { value: webcrypto });
}
if (typeof globalThis.TextEncoder === "undefined") {
  Object.defineProperty(globalThis, "TextEncoder", { value: NodeTextEncoder });
}

import { getGravatarUrl } from "@/lib/gravatar";

describe("getGravatarUrl", () => {
  it("returns a URL in the correct Gravatar format", async () => {
    const url = await getGravatarUrl("user@example.com");

    expect(url).toMatch(
      /^https:\/\/www\.gravatar\.com\/avatar\/[a-f0-9]{64}\?s=\d+&d=\w+$/,
    );
  });

  it("uses default size of 80", async () => {
    const url = await getGravatarUrl("user@example.com");

    expect(url).toContain("?s=80&");
  });

  it("uses default fallback of identicon", async () => {
    const url = await getGravatarUrl("user@example.com");

    expect(url).toContain("&d=identicon");
  });

  it("accepts a custom size parameter", async () => {
    const url = await getGravatarUrl("user@example.com", 200);

    expect(url).toContain("?s=200&");
  });

  it("accepts a custom fallback parameter", async () => {
    const url = await getGravatarUrl("user@example.com", 80, "monsterid");

    expect(url).toContain("&d=monsterid");
  });

  it("trims whitespace from the email before hashing", async () => {
    const urlClean = await getGravatarUrl("user@example.com");
    const urlPadded = await getGravatarUrl("  user@example.com  ");

    expect(urlClean).toEqual(urlPadded);
  });

  it("lowercases the email before hashing", async () => {
    const urlLower = await getGravatarUrl("user@example.com");
    const urlMixed = await getGravatarUrl("User@Example.COM");

    expect(urlLower).toEqual(urlMixed);
  });

  it("produces deterministic hashes for the same email", async () => {
    const url1 = await getGravatarUrl("stable@test.io");
    const url2 = await getGravatarUrl("stable@test.io");

    expect(url1).toEqual(url2);
  });

  it("produces different hashes for different emails", async () => {
    const url1 = await getGravatarUrl("alice@example.com");
    const url2 = await getGravatarUrl("bob@example.com");

    // Extract the hash portion
    const hash1 = url1.split("/avatar/")[1].split("?")[0];
    const hash2 = url2.split("/avatar/")[1].split("?")[0];

    expect(hash1).not.toEqual(hash2);
  });
});
