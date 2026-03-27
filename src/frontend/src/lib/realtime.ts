/**
 * Placeholder Web PubSub client setup.
 *
 * This module will eventually initialise and export a Web PubSub client
 * instance for the realtime provider.  For now it is a no-op stub.
 */

export const REALTIME_ENDPOINT =
  process.env.NEXT_PUBLIC_WEBPUBSUB_URL ?? "";

/**
 * Connect to Azure Web PubSub.
 *
 * @returns A cleanup function to close the connection.
 */
export function connectRealtime(_tenantId: string): () => void {
  if (process.env.NODE_ENV === "development") {
    console.log("[realtime] Web PubSub connection stub — not connected");
  }
  return () => {
    /* no-op */
  };
}
