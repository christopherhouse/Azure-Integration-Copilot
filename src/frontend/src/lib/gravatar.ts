/**
 * Compute a SHA-256 hash of the given string using the Web Crypto API.
 * Used for constructing Gravatar URLs.
 */
async function sha256(input: string): Promise<string> {
  const data = new TextEncoder().encode(input.trim().toLowerCase());
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Build a Gravatar image URL for the given email address.
 *
 * @param email - Email address to hash for Gravatar lookup
 * @param size - Image size in pixels (default 80)
 * @param fallback - Gravatar default image style (default "identicon")
 * @returns Promise resolving to the Gravatar URL
 */
export async function getGravatarUrl(
  email: string,
  size = 80,
  fallback = "identicon",
): Promise<string> {
  const hash = await sha256(email);
  return `https://www.gravatar.com/avatar/${hash}?s=${size}&d=${fallback}`;
}
