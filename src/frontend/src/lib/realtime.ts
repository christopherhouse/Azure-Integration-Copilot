import { apiFetch } from "@/lib/api";

/**
 * Realtime message received from the Web PubSub WebSocket.
 *
 * The backend sends JSON messages with a `type` discriminator and an
 * arbitrary `data` object.
 */
export interface RealtimeMessage {
  type: string;
  data: unknown;
}

/** Callback registered via {@link RealtimeClient.on}. */
export type RealtimeListener = (payload: unknown) => void;

/**
 * Lightweight WebSocket client that connects to Azure Web PubSub via a
 * backend-issued negotiate endpoint.
 *
 * Supports automatic reconnection with exponential back-off and a
 * listener registry keyed by event type.
 */
export class RealtimeClient {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<RealtimeListener>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private maxReconnectDelay = 30_000; // 30 s ceiling
  private disposed = false;
  private _connected = false;

  /** Whether the WebSocket is currently open. */
  get connected(): boolean {
    return this._connected;
  }

  // -----------------------------------------------------------------------
  // Connection lifecycle
  // -----------------------------------------------------------------------

  /**
   * Negotiate a WebSocket URL from the backend, then open the connection.
   *
   * If negotiation fails (e.g. Web PubSub not configured) the client
   * stays in a disconnected state without breaking the application.
   */
  async connect(): Promise<void> {
    if (this.disposed) return;

    try {
      const res = await apiFetch("/api/v1/realtime/negotiate", {
        method: "POST",
      });
      if (!res.ok) {
        console.warn("[realtime] negotiate failed:", res.status);
        return;
      }
      const body = (await res.json()) as { data?: { url?: string } };
      const url = body.data?.url;
      if (!url) {
        console.warn("[realtime] negotiate returned no url");
        return;
      }
      this.openSocket(url);
    } catch (err) {
      console.warn("[realtime] negotiate error:", err);
    }
  }

  /** Close the connection and prevent further reconnects. */
  dispose(): void {
    this.disposed = true;
    this.clearReconnect();
    if (this.ws) {
      this.ws.onclose = null; // prevent reconnect handler
      this.ws.close();
      this.ws = null;
    }
    this._connected = false;
    this.listeners.clear();
  }

  // -----------------------------------------------------------------------
  // Listener registry
  // -----------------------------------------------------------------------

  /** Register a listener for a given event type. Returns an unsubscribe fn. */
  on(eventType: string, listener: RealtimeListener): () => void {
    let set = this.listeners.get(eventType);
    if (!set) {
      set = new Set();
      this.listeners.set(eventType, set);
    }
    set.add(listener);

    return () => {
      set?.delete(listener);
      if (set?.size === 0) {
        this.listeners.delete(eventType);
      }
    };
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  private openSocket(url: string): void {
    if (this.disposed) return;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this._connected = true;
      this.reconnectAttempt = 0;
      if (process.env.NODE_ENV === "development") {
        console.log("[realtime] connected");
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: RealtimeMessage = JSON.parse(event.data as string);
        this.dispatch(msg);
      } catch {
        // Ignore non-JSON frames (e.g. PubSub system messages)
      }
    };

    this.ws.onerror = () => {
      // onclose will fire next; we handle reconnect there.
    };

    this.ws.onclose = () => {
      this._connected = false;
      if (!this.disposed) {
        this.scheduleReconnect();
      }
    };
  }

  private dispatch(msg: RealtimeMessage): void {
    const set = this.listeners.get(msg.type);
    if (set) {
      for (const listener of set) {
        try {
          listener(msg.data);
        } catch (err) {
          console.error("[realtime] listener error:", err);
        }
      }
    }
    // Wildcard listeners for "*"
    const wildcard = this.listeners.get("*");
    if (wildcard) {
      for (const listener of wildcard) {
        try {
          listener(msg);
        } catch (err) {
          console.error("[realtime] wildcard listener error:", err);
        }
      }
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    const delay = Math.min(
      1000 * 2 ** this.reconnectAttempt,
      this.maxReconnectDelay,
    );
    this.reconnectAttempt++;
    if (process.env.NODE_ENV === "development") {
      console.log(`[realtime] reconnecting in ${delay}ms…`);
    }
    this.reconnectTimer = setTimeout(() => {
      void this.connect();
    }, delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
