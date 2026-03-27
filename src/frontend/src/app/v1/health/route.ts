import { NextResponse } from "next/server";

/**
 * Frontend health check endpoint.
 *
 * Returns 200 with a simple status payload. In the future this will also
 * verify connectivity to the backend API.
 */
function healthResponse() {
  return NextResponse.json({ status: "ok" });
}

export async function GET() {
  return healthResponse();
}

export async function HEAD() {
  return new NextResponse(null, { status: 200 });
}
