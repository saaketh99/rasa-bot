import { type NextRequest, NextResponse } from "next/server"

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || "http://rasa-backend-alb-1743700668.eu-north-1.elb.amazonaws.com"

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  try {
    const response = await fetch(`${FASTAPI_BASE_URL}/conversations/${id}`)
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch conversation:", error)
    return NextResponse.json({ success: false, error: error instanceof Error ? error.message : String(error) })
  }
}
