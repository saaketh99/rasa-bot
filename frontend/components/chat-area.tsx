"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { Conversation } from "@/app/page"

interface ChatAreaProps {
  conversation: Conversation | null
  onSendMessage: (message: string) => void
  onCreateConversation: (message: string) => void
  loading: boolean
}

export function ChatArea({ conversation, onSendMessage, onCreateConversation, loading }: ChatAreaProps) {
  const [input, setInput] = useState("")
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [conversation?.messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    if (conversation) {
      onSendMessage(input.trim())
    } else {
      onCreateConversation(input.trim())
    }

    setInput("")
  }

  const formatTime = (timestamp?: number) => {
    if (!timestamp) return ""
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const renderWelcomeScreen = () => (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-white mb-2">Welcome to Order Assistant</h1>
        <p className="text-gray-400 mb-6">
          Ask me anything about your orders, deliveries, and logistics. I can help you track shipments, check statuses,
          and analyze your data.
        </p>
        <div className="text-sm text-gray-500">Start by typing a message below</div>
      </div>
    </div>
  )

  return (
    <div className="flex-1 flex flex-col h-screen">
      {/* Header */}
      <div className="border-b border-gray-800 p-4 flex items-center gap-4">
        <SidebarTrigger className="text-gray-400 hover:text-white" />
        <h2 className="text-lg font-medium text-white">{conversation ? conversation.title : "New Conversation"}</h2>
      </div>

      {/* Messages Area */}
      {!conversation ? (
        renderWelcomeScreen()
      ) : (
        <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
          <div className="space-y-4 max-w-4xl mx-auto">
            {conversation.messages.map((message) => (
              <div key={message.id} className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[70%] rounded-lg px-4 py-2 ${
                    message.sender === "user" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-100"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.text}</div>
                  {message.timestamp && (
                    <div className={`text-xs mt-1 ${message.sender === "user" ? "text-blue-100" : "text-gray-500"}`}>
                      {formatTime(message.timestamp)}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 text-gray-100 rounded-lg px-4 py-2 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Thinking...</span>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      )}

      {/* Input Area */}
      <div className="border-t border-gray-800 p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything..."
              disabled={loading}
              className="flex-1 bg-gray-800 border-gray-700 text-white placeholder-gray-400 focus:border-blue-500 focus:ring-blue-500"
            />
            <Button
              type="submit"
              disabled={!input.trim() || loading}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
