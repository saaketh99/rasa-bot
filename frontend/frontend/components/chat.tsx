"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Send, Bot, User, Loader2, Sun, Moon } from "lucide-react"
import * as XLSX from "xlsx"
// @ts-ignore
import { saveAs } from "file-saver"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "sonner"
import { useTheme } from 'next-themes'
import data from '@emoji-mart/data'
import Picker from '@emoji-mart/react'

interface ChatMessage {
  id: string
  text: string
  sender: "user" | "bot"
  timestamp: number
  buttons?: Array<{ title: string; payload: string }>
  image?: string
  custom?: any;
}

interface RasaResponse {
  text: string
  buttons?: Array<{ title: string; payload: string }>
  image?: string
  attachment?: any
  custom?: any;
}

interface ConversationMeta {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

function ClientTime({ timestamp }: { timestamp: number }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <>{new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</>
  );
}

// Helper to render message text with download button if link is present
function renderMessageText(text: string) {
  // This function can remain as is, since the logic to render download links is separate
  // from the main table rendering.
  const markdownLinkRegex = /\[([^\]]+)\]\(([^)]+)\)/;
  const markdownMatch = text.match(markdownLinkRegex);
  if (markdownMatch) {
    const label = markdownMatch[1];
    const url = markdownMatch[2];
    if (url.match(/\.(png|jpg|jpeg|gif|svg)$/i)) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <img
            src={url}
            alt={label}
            style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #ddd', marginBottom: 8 }}
          />
          <a href={url} download target="_blank" rel="noopener noreferrer">
            <button
              style={{ padding: '8px 16px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: 5, cursor: 'pointer' }}
            >
              📈 Download Graph
            </button>
          </a>
        </div>
      );
    } else {
      return (
        <a href={url} target="_blank" rel="noopener noreferrer" download={url.endsWith('.xlsx') || url.endsWith('.xls')}>
          <button
            style={{ padding: '8px 16px', backgroundColor: '#1976d2', color: 'white', border: 'none', borderRadius: 5, cursor: 'pointer' }}
          >
            {label}
          </button>
        </a>
      );
    }
  }
  return <span>{text}</span>;
}

const SUGGESTIONS = [
  "Show me the orders for CUSTOMER_NAME from 2025-06-21 to 2025-07-31",
  "Get me the orders going from SENDER_CITY_NAME to RECIVER_CITY_NAME",
  "How many shipments were delivered to DESTINATION_CITY?",
  "Show all pending orders",
  "Order status for ORDER_ID",
  "Track order with invoice number INVOICE_NUMBER",
  "Show me all delivered orders within N days",
  "Is service available in pincode PINCODE?",
  "Delivery summary from 2025-06-21 to 2025-07-31",
  "Give me complete details for order ID ORDER_ID",
  "long pending orders",
  "Show pending orders from the last N days",
  "Top delivery pincodes for CUSTOMER_NAME",
  "how delivered orders distributed across cities",
  "Delivered report across cities for CUSTOMER_NAME",
  "Show me the order trend for CUSTOMER_NAME in the past N days",
  "What’s the delay trend in the past N days?",
  "Who is updating most of the delivery statuses?"
];

// Helper to generate unique IDs on the client only
function getClientUniqueId() {
  if (typeof window !== 'undefined') {
    return Date.now().toString() + Math.random().toString(36).substr(2, 5);
  }
  return '';
}

export function Chat() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false)
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const BOT_WELCOME: ChatMessage = {
    id: typeof window !== 'undefined' ? getClientUniqueId() : 'bot-welcome',
    text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
    sender: "bot",
    timestamp: typeof window !== 'undefined' ? Date.now() : 0,
  };
  const [messages, setMessages] = useState<ChatMessage[]>([BOT_WELCOME]);
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([])
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    fetch("http://51.20.18.59:8000/conversations")
      .then(res => res.json())
      .then(data => {
        if (data.conversations) setConversations(data.conversations);
      });
  }, []);

  const loadConversation = (id: string) => {
    fetch(`http://51.20.18.59:8000/conversations/${id}`)
      .then(res => res.json())
      .then(data => {
        if (data.messages) {
          setMessages(data.messages);
          setCurrentConversationId(id);
        }
      });
  };

  const startNewConversation = (firstUserMessage: ChatMessage) => {
    fetch("http://51.20.18.59:8000/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: firstUserMessage })
    })
      .then(res => res.json())
      .then(data => {
        if (data.success && data.conversation_id) {
          setCurrentConversationId(data.conversation_id);
          setMessages([firstUserMessage]);
          fetch("http://51.20.18.59:8000/conversations")
            .then(res => res.json())
            .then(data => {
              if (data.conversations) setConversations(data.conversations);
            });
        }
      });
  };

  const appendMessage = (message: ChatMessage) => {
    if (!currentConversationId) return;
    fetch(`http://51.20.18.59:8000/conversations/${currentConversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    }).then(() => {
      setMessages(prev => [...prev, message]);
      fetch("http://51.20.18.59:8000/conversations")
        .then(res => res.json())
        .then(data => {
          if (data.conversations) setConversations(data.conversations);
        });
    });
  };

  useEffect(() => {
    if (conversations.length === 0 && !currentConversationId) {
      startNewConversation(BOT_WELCOME);
    }
  }, [conversations, currentConversationId]);

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

  useEffect(() => {
    if (input.length > 1) {
      setFilteredSuggestions(
        SUGGESTIONS.filter(s => s.toLowerCase().includes(input.toLowerCase()) && s.toLowerCase() !== input.toLowerCase())
      );
    } else {
      setFilteredSuggestions([]);
    }
  }, [input]);

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;
    const id = getClientUniqueId();
    const timestamp = Date.now();

    const userMessage: ChatMessage = { id, text: messageText, sender: "user", timestamp };

    if (!currentConversationId) {
      startNewConversation(userMessage);
    } else {
      appendMessage(userMessage);
    }
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText, sender: "user_" + Date.now() }),
      });

      const data = await response.json();

      if (data.success && data.responses) {
        const botMessages: ChatMessage[] = data.responses
          // Filter out responses that are completely empty
          .filter((resp: RasaResponse) => (resp.text && resp.text.trim()) || resp.custom || resp.image)
          .map((resp: RasaResponse): ChatMessage => {
            // --- START: CORRECTED AND SIMPLIFIED LOGIC ---
            // Simply pass the data from the backend directly to the message object.
            // The backend is now responsible for sending a single, cohesive message.
            return {
              id: getClientUniqueId(),
              text: resp.text || "", // Use text if it exists, otherwise empty string
              sender: "bot" as const,
              timestamp: Date.now(),
              buttons: resp.buttons,
              image: resp.image,
              custom: resp.custom, // Pass the entire original custom object
            };
            // --- END: CORRECTED AND SIMPLIFIED LOGIC ---
          });

        if (botMessages.length > 0) {
          setMessages((prev) => [...prev, ...botMessages]);
        } else {
          // This case should be rare now, but kept as a fallback.
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              text: "I received your message but don't have a specific response. Could you try rephrasing?",
              sender: "bot",
              timestamp: Date.now(),
            },
          ]);
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
        ]);
      }
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: "Sorry, I'm having trouble connecting. Please check if the Rasa server is running.",
          sender: "bot",
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleButtonClick = (payload: string, title: string) => {
    sendMessage(payload);
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
    <div className="flex min-h-screen w-full h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      {/* Sidebar */}
      <aside className="w-72 bg-gray-900 text-white flex flex-col p-4 space-y-4 overflow-y-auto border-r border-gray-800">
        <button
          className="w-full mb-2 p-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 transition"
          onClick={() => {
            setCurrentConversationId(null);
            setMessages([BOT_WELCOME]);
          }}
        >
          + New Conversation
        </button>
        <div className="flex-1 overflow-y-auto space-y-2">
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`p-3 rounded cursor-pointer truncate ${currentConversationId === conv.id ? 'bg-blue-800 text-white' : 'hover:bg-gray-800'}`}
              onClick={() => loadConversation(conv.id)}
              title={conv.title}
            >
              <div className="font-medium truncate">{conv.title}</div>
              <div className="text-xs text-gray-400">{conv.updated_at ? new Date(conv.updated_at).toLocaleString() : ''}</div>
            </div>
          ))}
        </div>
      </aside>
      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 relative">
        {/* Suggestion Panel Button & Expandable Suggestions */}
        <div className="fixed right-6 bottom-32 z-50 flex flex-col items-end">
          <button
            className="bg-blue-600 text-white rounded-full p-3 shadow-lg hover:bg-blue-700 transition"
            onClick={() => setSuggestionsOpen((prev) => !prev)}
            aria-label="Show suggestions"
          >
            <svg width="24" height="24" fill="none" viewBox="0 0 24 24">
              <path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.5 4.5-3.5 5.5V17a1 1 0 0 1-2 0v-2.5C8.5 13.5 7 11.5 7 9a7 7 0 0 1 7-7z" fill="currentColor"/>
            </svg>
          </button>
          <div
            className={`overflow-hidden transition-all duration-300 ease-in-out ${
              suggestionsOpen ? "max-h-96 opacity-100 mt-2" : "max-h-0 opacity-0"
            }`}
            style={{ minWidth: "220px" }}
          >
            <div className="bg-white rounded-lg shadow-lg p-2 flex flex-col gap-2 max-h-80 overflow-y-auto">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="bg-blue-100 text-blue-800 rounded px-3 py-1 text-sm text-left hover:bg-blue-200 transition"
                  onClick={() => { setInput(s); setSuggestionsOpen(false); inputRef.current?.focus(); }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
        {/* Header */}
        <header className="flex items-center justify-between px-8 py-6 bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-gray-800 dark:to-gray-900 text-white shadow">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bot className="h-7 w-7" />
              Order Management Assistant
            </h1>
            <p className="text-blue-100 text-sm dark:text-gray-300">Ask me about orders, delivery status, customer information, and more</p>
          </div>
          <button
            aria-label="Toggle dark mode"
            className="ml-auto p-2 rounded-full hover:bg-blue-700 dark:hover:bg-gray-700 transition-colors"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun className="h-5 w-5 text-yellow-300" /> : <Moon className="h-5 w-5 text-gray-200" />}
          </button>
        </header>
        {/* Chat Content */}
        <section className="flex-1 flex flex-col px-8 py-6 overflow-y-auto">
            <div className="space-y-4 bg-white rounded-lg p-4">
              <AnimatePresence initial={false}>
                {messages
                  .filter(message => !(message.sender === "bot" && !message.text?.trim() && !message.custom && !message.image))
                  .map((message, idx) => (
                    <motion.div
                      key={message.id ? message.id + '-' + idx : idx}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 20 }}
                      transition={{ duration: 0.3 }}
                      className={`flex gap-3 ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {message.sender === "bot" && (
                        <Avatar className="h-8 w-8 bg-blue-100">
                          <AvatarFallback>
                            <Bot className="h-4 w-4 text-blue-600" />
                          </AvatarFallback>
                        </Avatar>
                      )}

                      <div
                        className={`max-w-[70%] rounded-lg px-4 py-2 ${
                          message.sender === "user" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
                        }`}
                      >
                        {/* Render text only if it's not empty */}
                        {message.text && message.text.trim() && (
                            <div className="whitespace-pre-wrap break-words">{renderMessageText(message.text)}</div>
                        )}
                        
                        {/* DYNAMIC TABLE RENDERING */}
                        {(() => {
                          const custom = message.custom;
                          if (!custom || !Array.isArray(custom.table_data) || custom.table_data.length === 0) return null;
                          
                          const tableArray = custom.table_data;
                          const columns = Object.keys(tableArray[0]);

                          return (
                            <div className="overflow-x-auto mt-2 text-black">
                              <div className="flex gap-2 mb-2">
                                {/* Client-side Excel Download (always available for tables) */}
                                <button
                                  onClick={() => {
                                    try {
                                      const worksheet = XLSX.utils.json_to_sheet(tableArray);
                                      const workbook = XLSX.utils.book_new();
                                      XLSX.utils.book_append_sheet(workbook, worksheet, "Data");
                                      const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
                                      const file = new Blob([excelBuffer], { type: "application/octet-stream" });
                                      saveAs(file, "exported_data.xlsx");
                                      toast.success("Excel file downloaded!");
                                    } catch (err) {
                                      toast.error("Failed to download Excel file.");
                                    }
                                  }}
                                  className="px-3 py-1 bg-green-600 text-white border-none rounded cursor-pointer hover:bg-green-700 transition"
                                >
                                  📥 Download as Excel
                                </button>
                                {/* Backend Excel Download (only if URL is provided) */}
                                {custom.excel_url && (
                                  <a
                                    href={custom.excel_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    download
                                    className="px-3 py-1 bg-blue-600 text-white border-none rounded cursor-pointer hover:bg-blue-700 transition no-underline"
                                  >
                                    📄 Download Report
                                  </a>
                                )}
                              </div>
                              <table className="min-w-full border text-sm bg-white">
                                <thead className="bg-gray-200">
                                  <tr>
                                    {columns.map((col) => (
                                      <th key={col} className="border px-2 py-1 font-semibold text-left">{col}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {tableArray.map((row: any, i: number) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                      {columns.map((col) => (
                                        <td key={col} className="border px-2 py-1">{String(row[col])}</td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}

                        {message.buttons && message.buttons.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {message.buttons.map((button, index) => (
                              <Button
                                key={index}
                                className="mr-2 mb-1 bg-transparent"
                                onClick={() => handleButtonClick(button.payload, button.title)}
                              >
                                {button.title}
                              </Button>
                            ))}
                          </div>
                        )}

                        {message.image && (
                          <div className="mt-2 flex flex-col items-center">
                            <img
                              src={message.image}
                              alt="Bot response graph"
                              className="max-w-full h-auto rounded border border-gray-300"
                            />
                          </div>
                        )}

                        <div className={`text-xs mt-1 ${message.sender === "user" ? "text-blue-200" : "text-gray-500"}`}>
                          <ClientTime timestamp={message.timestamp} />
                        </div>
                      </div>

                      {message.sender === "user" && (
                        <Avatar className="h-8 w-8 bg-blue-600">
                          <AvatarFallback>
                            <User className="h-4 w-4 text-white" />
                          </AvatarFallback>
                        </Avatar>
                      )}
                    </motion.div>
                  ))}
              </AnimatePresence>

              {isLoading && (
                <div className="flex gap-3 justify-start">
                  <Avatar className="h-8 w-8 bg-blue-100">
                    <AvatarFallback>
                      <Bot className="h-4 w-4 text-blue-600" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-gray-100 rounded-lg px-4 py-2">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-gray-600">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
        </section>
        {/* Input Area */}
        <footer className="px-8 py-4 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800">
          <form onSubmit={handleSubmit} className="flex w-full gap-2" suppressHydrationWarning>
            <div className="relative flex-1 flex items-center">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about orders, delivery status, customers..."
                className="flex-1 pr-10"
                disabled={isLoading}
                autoComplete="off"
              />
              <button
                type="button"
                aria-label="Add emoji"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xl"
                onClick={() => setShowEmojiPicker((v) => !v)}
                tabIndex={-1}
              >
                😊
              </button>
              {showEmojiPicker && (
                <div className="absolute bottom-12 right-0 z-50">
                  <Picker
                    data={data}
                    theme={theme === 'dark' ? 'dark' : 'light'}
                    onEmojiSelect={(emoji: any) => {
                      setInput(input + (emoji.native || emoji.colons || ''))
                      setShowEmojiPicker(false)
                    }}
                  />
                </div>
              )}
            </div>
            <Button type="submit" disabled={isLoading || !input.trim()} className="bg-blue-600 hover:bg-blue-700">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </footer>
      </main>
    </div>
  )
}