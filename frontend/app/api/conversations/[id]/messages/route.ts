import { type NextRequest, NextResponse } from "next/server"

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || "http://rasa-backend-alb-1743700668.eu-north-1.elb.amazonaws.com"

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  try {
    const body = await request.json()
    const response = await fetch(`${FASTAPI_BASE_URL}/conversations/${id}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to append message:", error)
    return NextResponse.json({ success: false, error: error instanceof Error ? error.message : String(error) })
  }
}
