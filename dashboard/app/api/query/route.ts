import { NextResponse } from "next/server";

const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${AGENT_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      {
        error: "agent_unreachable",
        detail: err instanceof Error ? err.message : String(err),
        agent_url: AGENT_URL,
      },
      { status: 502 }
    );
  }
}
