/**
 * Webhook client for real-time updates from BOSS backend.
 * Manages polling and event notifications.
 */

type WebhookEvent = "new_email" | "email_processed";

interface WebhookPayload {
  event: WebhookEvent;
  email_id?: string;
  quote_id?: string;
  numero_offre?: string;
  from_address?: string;
  subject?: string;
  received_at?: string;
  timestamp: string;
}

type WebhookListener = (payload: WebhookPayload) => void;

class WebhookClient {
  private listeners: Map<WebhookEvent, Set<WebhookListener>> = new Map();
  private pollingInterval: NodeJS.Timeout | null = null;
  private lastCheckTime: number = Date.now();

  /**
   * Subscribe to webhook events
   */
  on(event: WebhookEvent, listener: WebhookListener): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(listener);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(listener);
    };
  }

  /**
   * Emit event to all listeners
   */
  private emit(event: WebhookEvent, payload: WebhookPayload): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach((listener) => listener(payload));
    }
  }

  /**
   * Start polling for updates (fallback if webhook is not available)
   */
  startPolling(interval: number = 5000): void {
    if (this.pollingInterval) {
      return; // Already polling
    }

    this.pollingInterval = setInterval(() => {
      this.checkForUpdates();
    }, interval);
  }

  /**
   * Stop polling
   */
  stopPolling(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  /**
   * Check for updates (used by polling)
   */
  private async checkForUpdates(): Promise<void> {
    try {
      // This would be called by the frontend to check if there are new emails
      // The actual implementation depends on your backend API
      const response = await fetch("/api/v1/emails?limit=1");
      if (response.ok) {
        const emails = await response.json();
        if (emails.length > 0) {
          const latestEmail = emails[0];
          // Emit event if this is a new email
          if (new Date(latestEmail.received_at).getTime() > this.lastCheckTime) {
            this.emit("new_email", {
              event: "new_email",
              email_id: latestEmail.id,
              from_address: latestEmail.from_address,
              subject: latestEmail.subject,
              received_at: latestEmail.received_at,
              timestamp: new Date().toISOString(),
            });
            this.lastCheckTime = Date.now();
          }
        }
      }
    } catch (error) {
      console.error("[WebhookClient] Error checking for updates:", error);
    }
  }

  /**
   * Get webhook endpoint URL
   */
  getWebhookUrl(): string {
    const baseUrl =
      typeof window !== "undefined"
        ? window.location.origin
        : process.env.NEXT_PUBLIC_VERCEL_URL
          ? `https://${process.env.NEXT_PUBLIC_VERCEL_URL}`
          : "http://localhost:3000";
    return `${baseUrl}/api/webhooks/boss`;
  }
}

// Export singleton instance
export const webhookClient = new WebhookClient();

/**
 * React hook for listening to webhook events
 */
export function useWebhookListener(
  event: WebhookEvent,
  callback: WebhookListener
): void {
  const React = require("react");

  React.useEffect(() => {
    const unsubscribe = webhookClient.on(event, callback);
    return unsubscribe;
  }, [event, callback]);
}

