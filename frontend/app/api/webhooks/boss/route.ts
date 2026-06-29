import { NextRequest, NextResponse } from "next/server";

/**
 * Webhook endpoint for BOSS backend notifications.
 * Receives events when:
 * - A new email arrives (new_email)
 * - An email is processed by the AI agent (email_processed)
 */

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate webhook payload
    if (!body.event || !["new_email", "email_processed"].includes(body.event)) {
      return NextResponse.json(
        { error: "Invalid event type" },
        { status: 400 }
      );
    }

    // Log the webhook event
    console.log(`[BOSS Webhook] ${body.event}:`, {
      email_id: body.email_id,
      quote_id: body.quote_id,
      numero_offre: body.numero_offre,
      timestamp: body.timestamp,
    });

    // TODO: Implement real-time updates
    // Options:
    // 1. Broadcast to connected clients via WebSocket
    // 2. Store event in database and let frontend poll
    // 3. Use Server-Sent Events (SSE) to push updates
    // 4. Trigger a revalidation of the dashboard data

    // For now, just acknowledge receipt
    return NextResponse.json(
      {
        success: true,
        event: body.event,
        message: "Webhook received and processed",
      },
      { status: 200 }
    );
  } catch (error) {
    console.error("[BOSS Webhook] Error:", error);
    return NextResponse.json(
      { error: "Failed to process webhook" },
      { status: 500 }
    );
  }
}

// Health check endpoint
export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      endpoint: "/api/webhooks/boss",
      events: ["new_email", "email_processed"],
    },
    { status: 200 }
  );
}

