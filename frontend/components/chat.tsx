"use client"

import type React from "react"
import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Send, Bot, User, Loader2 } from "lucide-react"
import * as XLSX from "xlsx"
import { saveAs } from "file-saver"
import { v4 as uuidv4 } from "uuid"

interface ChatMessage {
  id: string
  text: string
  sender: "user" | "bot"
  timestamp: number
  buttons?: Array<{ title: string; payload: string }>
  image?: string
}

interface RasaResponse {
  text: string
  buttons?: Array<{ title: string; payload: string }>
  image?: string
  attachment?: any
}

function ClientTime({ timestamp }: { timestamp: number }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <>{new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</>
  );
}

function renderMessageText(text: string) {
  const downloadRegex = /<a [^>]*href=["']([^"']+)["'][^>]*download[^>]*>([\s\S]*?)<\/a>/i;
  const match = text.match(downloadRegex);
  if (match) {
    const url = match[1];
    return null;
  }
  return <span>{text}</span>;
}

export function Chat() {
  const [mounted, setMounted] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
      sender: "bot",
      timestamp: 0,
    },
  ])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [sessionId] = useState(() => {
    const existing = sessionStorage.getItem("session_id")
    if (existing) return existing
    const newId = uuidv4()
    sessionStorage.setItem("session_id", newId)
    return newId
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector("[data-radix-scroll-area-viewport]")
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (mounted) {
      setMessages((msgs) =>
        msgs.map((msg) =>
          msg.timestamp === 0 ? { ...msg, timestamp: Date.now() } : msg
        )
      );
    }
  }, [mounted]);

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: messageText,
      sender: "user",
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageText,
          sender: "user",
          session_id: sessionId,
        }),
      })

      const data = await response.json()

      if (data.success && data.responses) {
        const botMessages: ChatMessage[] = data.responses
          .filter((resp: RasaResponse) => resp.text && resp.text.trim())
          .map((resp: RasaResponse, index: number) => ({
            id: (Date.now() + index).toString(),
            text: resp.text,
            sender: "bot",
            timestamp: Date.now(),
            buttons: resp.buttons,
            image: resp.image,
          }))

        if (botMessages.length > 0) {
          setMessages((prev) => [...prev, ...botMessages])
        } else {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              text: "I received your message but don't have a response right now. Please try rephrasing your question.",
              sender: "bot",
              timestamp: Date.now(),
            },
          ])
        }
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            text: data.responses?.[0]?.text || "Sorry, I encountered an error. Please try again.",
            sender: "bot",
            timestamp: Date.now(),
          },
        ])
      }
    } catch (error) {
      console.error("Error sending message:", error)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: "Sorry, I'm having trouble connecting. Please check if the backend is running and try again.",
          sender: "bot",
          timestamp: Date.now(),
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleButtonClick = (payload: string, title: string) => {
    sendMessage(payload)
  }

  function extractPincodeOrders(text: string) {
    const regex = /Pincode:\s*(\d+)\s*→\s*(\d+) orders/g;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      result.push({ Pincode: match[1], Orders: parseInt(match[2], 10) });
    }
    return result;
  }

  function extractOrderDetails(text: string) {
    const fullRegex = /- Order ID: ([^|]+) \| Status: ([^|]+) \| To: ([^|]+) \| Created: ([^\n]+)/g;
    const simpleRegex = /- Order ID: ([^|]+) \| Status: ([^\n]+)/g;
    const result = [];
    let match;
    while ((match = fullRegex.exec(text)) !== null) {
      result.push({
        "Order ID": match[1].trim(),
        "Status": match[2].trim(),
        "To": match[3].trim(),
        "Created": match[4].trim(),
      });
    }
    if (result.length === 0) {
      while ((match = simpleRegex.exec(text)) !== null) {
        result.push({
          "Order ID": match[1].trim(),
          "Status": match[2].trim(),
        });
      }
    }
    return result;
  }

  const handleDownloadExcel = () => {
    const lastBotMsg = [...messages].reverse().find(m => m.sender === "bot" && (/Pincode:/i.test(m.text) || /- Order ID:/i.test(m.text)));
    if (!lastBotMsg) return;
    let data: any[] = extractPincodeOrders(lastBotMsg.text);
    let sheetName = "Pincodes";
    if (!data.length) {
      data = extractOrderDetails(lastBotMsg.text);
      sheetName = "Orders";
    }
    if (!data.length) return;
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const file = new Blob([excelBuffer], { type: "application/octet-stream" });
    saveAs(file, sheetName === "Pincodes" ? "top_pincodes.xlsx" : "pending_orders.xlsx");
  };

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading chat interface...</p>
        </div>
      </div>
    );
  }

return (
  <div>
    <h1>Hello from Chat Component</h1>
  </div>
);

}
