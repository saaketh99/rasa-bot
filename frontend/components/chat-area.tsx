"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { Conversation } from "@/app/page"
import { useToast } from "@/hooks/use-toast";
import * as XLSX from "xlsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatAreaProps {
  conversation: Conversation | null
  onSendMessage: (message: string) => void
  onCreateConversation: (message: string) => void
  loading: boolean
  inputValue: string
  setInputValue: (v: string) => void
}

export function ChatArea({ conversation, onSendMessage, onCreateConversation, loading, inputValue, setInputValue }: ChatAreaProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast();

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [conversation?.messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || loading) return

    if (conversation) {
      onSendMessage(inputValue.trim())
    } else {
      onCreateConversation(inputValue.trim())
    }

    setInputValue("")
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

  // List of prompts/intents for which the download button should appear
  const downloadIntents = [
    "wakefit from", "orders going from", "shipments were delivered to", "all pending orders", "delivered orders within", "delivery summary", "long pending orders", "pending orders from the last", "top delivery pincodes", "delivered orders distributed across cities", "updating most of the delivery statuses", "pending orders from hyderabad", "pending orders for ola ele as per locations", "pending orders matrix by pickup location"
  ];

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
                  {message.sender === "bot" ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({node, ...props}) => <p className="whitespace-pre-wrap" {...props} />
                      }}
                    >
                      {message.text}
                    </ReactMarkdown>
                  ) : (
                    <div className="whitespace-pre-wrap">{message.text}</div>
                  )}
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
            {/* Download Button - now at the bottom, after all messages */}
            {conversation && conversation.messages.length > 0 && (() => {
              const lastBotMsg = [...conversation.messages].reverse().find(m => m.sender === "bot");
              if (!lastBotMsg) return null;
              // Check if the last bot message matches any of the download intents
              const lowerText = lastBotMsg.text.toLowerCase();
              const shouldShow = downloadIntents.some(intent => lowerText.includes(intent));
              if (!shouldShow) return null;

              // Try to extract an Excel file URL from the last bot message
              const excelUrlMatch = lastBotMsg.text.match(/https?:\/\/[^\s]+\.xlsx/);
              const excelUrl = excelUrlMatch ? excelUrlMatch[0] : null;

              return (
                <div className="flex justify-end mt-4">
                  <Button
                    className="bg-green-600 hover:bg-green-700 text-white"
                    onClick={async () => {
                      try {
                        if (excelUrl) {
                          toast({ title: "Download started", description: "Downloading full Excel file from backend..." });
                          const response = await fetch(excelUrl);
                          if (!response.ok) throw new Error("Failed to fetch Excel file");
                          const blob = await response.blob();
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = excelUrl.split("/").pop() || "orders.xlsx";
                          document.body.appendChild(a);
                          a.click();
                          a.remove();
                          window.URL.revokeObjectURL(url);
                        } else {
                          toast({ title: "Download started", description: "Generating Excel from conversation..." });
                          // Filter only bot messages
                          const botMessages = conversation.messages.filter(m => m.sender === "bot");
                          const data = botMessages.map(m => ({
                            Time: m.timestamp ? new Date(m.timestamp).toLocaleString() : "",
                            Message: m.text
                          }));
                          const worksheet = XLSX.utils.json_to_sheet(data);
                          const workbook = XLSX.utils.book_new();
                          XLSX.utils.book_append_sheet(workbook, worksheet, "Rasa Output");
                          const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
                          const blob = new Blob([excelBuffer], { type: "application/octet-stream" });
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = "conversation_rasa_output.xlsx";
                          document.body.appendChild(a);
                          a.click();
                          a.remove();
                          window.URL.revokeObjectURL(url);
                        }
                      } catch (err) {
                        toast({ title: "Download failed", description: "Could not download Excel file. Please try again later." });
                      }
                    }}
                  >
                    Download Orders (Excel)
                  </Button>
                </div>
              );
            })()}
          </div>
        </ScrollArea>
      )}

      {/* Input Area */}
      <div className="border-t border-gray-800 p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask anything..."
              disabled={loading}
              className="flex-1 bg-gray-800 border-gray-700 text-white placeholder-gray-400 focus:border-blue-500 focus:ring-blue-500"
            />
            <Button
              type="submit"
              disabled={!inputValue.trim() || loading}
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
