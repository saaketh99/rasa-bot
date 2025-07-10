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
}

interface RasaResponse {
  text: string
  buttons?: Array<{ title: string; payload: string }>
  image?: string
  attachment?: any
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
  // Regex to match the download link
  const downloadRegex = /<a [^>]*href=["']([^"']+)["'][^>]*download[^>]*>([\s\S]*?)<\/a>/i;
  const match = text.match(downloadRegex);
  if (match) {
    const url = match[1];
    // Instead of rendering a button, just render the link text or nothing
    // return (
    //   <a href={url} download target="_blank" rel="noopener noreferrer">
    //     <button style={{ padding: "10px 20px", backgroundColor: "#4CAF50", color: "white", border: "none", borderRadius: "5px" }}>
    //       📥 Download Excel
    //     </button>
    //   </a>
    // );
    return null; // or return <span />; if you want to show nothing
  }
  // Fallback: render as plain text
  return <span>{text}</span>;
}

const SUGGESTIONS = [
  "Show my recent orders",
  "Delivery report between [date] and [date]",
  "Show pending orders",
  "Show delivered orders",
  "Show orders for customer John Doe",
  "Show orders for pincode 123456",
  "Download order report",
  "What is the status of order OLAHYD1077?",
  "Show orders created today",
  "Show orders by location"
];

// --- Session ID logic ---
function getOrCreateSessionId() {
  if (typeof window === 'undefined') return '';
  let sessionId = localStorage.getItem('chat_session_id');
  if (!sessionId) {
    sessionId = Math.random().toString(36).substr(2, 9) + Date.now();
    localStorage.setItem('chat_session_id', sessionId);
  }
  return sessionId;
}

export function Chat() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false)
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  // Show bot welcome message in UI, but do not save to backend
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
      sender: "bot",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([])
  const sessionId = getOrCreateSessionId();
  const [availableSessions, setAvailableSessions] = useState<{session_id: string, last_updated: number|null}[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>(sessionId);

  // Ensure component only renders on client side
  useEffect(() => {
    setMounted(true)
  }, [])

  // Fetch all conversations on mount
  useEffect(() => {
    fetch("http://51.20.18.59:8000/conversations")
      .then(res => res.json())
      .then(data => {
        if (data.conversations) setConversations(data.conversations);
      });
  }, []);

  // Load a conversation by ID
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

  // Create a new conversation (only on first user message)
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
          setMessages(prev => [prev[0], firstUserMessage]); // bot welcome + user message
          // Refresh conversation list
          fetch("http://51.20.18.59:8000/conversations")
            .then(res => res.json())
            .then(data => {
              if (data.conversations) setConversations(data.conversations);
            });
        }
      });
  };

  // Append a message to the current conversation
  const appendMessage = (message: ChatMessage) => {
    if (!currentConversationId) return;
    fetch(`http://51.20.18.59:8000/conversations/${currentConversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    }).then(() => {
      setMessages(prev => [...prev, message]);
      // Optionally refresh conversation list for updated timestamp
      fetch("http://51.20.18.59:8000/conversations")
        .then(res => res.json())
        .then(data => {
          if (data.conversations) setConversations(data.conversations);
        });
    });
  };

  // On first mount, start a new conversation
  useEffect(() => {
    if (conversations.length === 0 && !currentConversationId) {
      const welcomeMsg: ChatMessage = {
        id: "1",
        text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
        sender: "bot",
        timestamp: Date.now(),
      };
      startNewConversation(welcomeMsg);
    }
  }, [conversations, currentConversationId]);

  // Load session from backend on mount
  useEffect(() => {
    if (!mounted) return;
    fetch(`http://51.20.18.59:8000/get-session/${sessionId}`)
      .then(res => res.json())
      .then(data => {
        if (data.success && Array.isArray(data.messages) && data.messages.length > 0) {
          setMessages(data.messages);
        }
      })
      .catch(() => {});
  }, [mounted]);

  // Save session to backend whenever messages change (after mount)
  useEffect(() => {
    if (!mounted) return;
    fetch("http://51.20.18.59:8000/save-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        messages,
      })
    }).catch(() => {});
  }, [messages, mounted, currentSessionId]);

  // Fetch available sessions on mount
  useEffect(() => {
    fetch("http://51.20.18.59:8000/list-sessions")
      .then(res => res.json())
      .then(data => {
        if (data.sessions) setAvailableSessions(data.sessions);
      });
  }, []);

  // When user selects a session, load its messages
  const loadSession = (sid: string) => {
    if (sid === 'new') {
      const newId = Math.random().toString(36).substr(2, 9) + Date.now();
      setMessages([
        {
          id: "1",
          text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
          sender: "bot",
          timestamp: Date.now(),
        },
      ]);
      setCurrentSessionId(newId);
      localStorage.setItem('chat_session_id', newId);
      return;
    }
    fetch(`http://51.20.18.59:8000/get-session/${sid}`)
      .then(res => res.json())
      .then(data => {
        if (data.success && Array.isArray(data.messages)) {
          setMessages(data.messages);
          setCurrentSessionId(sid);
          localStorage.setItem('chat_session_id', sid);
        }
      });
  };

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

  // Set initial timestamp on client to avoid hydration error
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

  // Send message handler
  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: messageText,
      sender: "user",
      timestamp: Date.now(),
    };
    if (!currentConversationId) {
      // Only now create the conversation in the backend
      startNewConversation(userMessage);
      setInput("");
      setIsLoading(true);
      return;
    }
    appendMessage(userMessage);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageText,
          sender: "user_" + Date.now(),
        }),
      })

      const data = await response.json()

      if (data.success && data.responses) {
        const botMessages: ChatMessage[] = data.responses
          .filter((resp: RasaResponse) => resp.text && resp.text.trim())
          .map((resp: RasaResponse, index: number) => ({
            id: (Date.now() + index).toString(),
            text: resp.text,
            sender: "bot" as const,
            timestamp: Date.now(),
            buttons: resp.buttons,
            image: resp.image,
          }))

        if (botMessages.length > 0) {
          setMessages((prev) => [...prev, ...botMessages])
        } else {
          // Fallback if no valid responses
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
          text: "Sorry, I'm having trouble connecting. Please check if the Rasa server is running and try again.",
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

  // Helper to extract pincode/order data from a message string
  function extractPincodeOrders(text: string) {
    const regex = /Pincode:\s*(\d+)\s*→\s*(\d+) orders/g;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      result.push({ Pincode: match[1], Orders: parseInt(match[2], 10) });
    }
    return result;
  }

  // Helper to extract order details from a message string
  function extractOrderDetails(text: string) {
    // Matches lines like: - Order ID: ... | Customer: ... | Status: ... | Date: ...
    const regex = /- Order ID: ([^|]+) \| Customer: ([^|]+) \| Status: ([^|]+) \| Date: ([^\n]+)/g;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      result.push({
        "Order ID": match[1].trim(),
        "Customer": match[2].trim(),
        "Status": match[3].trim(),
        "Date": match[4].trim(),
      });
    }
    return result;
  }

  // Download handler (now supports both pincode/orders and order details)
  const handleDownloadExcel = () => {
    // Find the latest bot message with either pincode/order data or order details
    const lastBotMsg = [...messages].reverse().find(m => m.sender === "bot" && (/Pincode:/i.test(m.text) || /- Order ID:/i.test(m.text)));
    if (!lastBotMsg) {
      toast.error("No data found to download.");
      return;
    }
    let data: any[] = extractPincodeOrders(lastBotMsg.text);
    let sheetName = "Pincodes";
    if (!data.length) {
      data = extractOrderDetails(lastBotMsg.text);
      sheetName = "Orders";
    }
    if (!data.length) {
      toast.error("No data found to download.");
      return;
    }
    try {
      const worksheet = XLSX.utils.json_to_sheet(data);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
      const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
      const file = new Blob([excelBuffer], { type: "application/octet-stream" });
      saveAs(file, sheetName === "Pincodes" ? "top_pincodes.xlsx" : "pending_orders.xlsx");
      toast.success("Excel file downloaded!");
    } catch (err) {
      toast.error("Failed to download Excel file.");
    }
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
    <div className="flex min-h-screen">
      <div className="w-64 bg-gray-100 dark:bg-gray-900 p-4 overflow-y-auto">
        <button
          className="w-full mb-4 p-2 bg-blue-600 text-white rounded"
          onClick={() => {
            setCurrentConversationId(null);
            setMessages([
              {
                id: "1",
                text: "Hello! I'm your order management assistant. I can help you track orders, check delivery status, find orders by customer, date, location, and much more. How can I assist you today?",
                sender: "bot",
                timestamp: Date.now(),
              },
            ]);
          }}
        >
          + New Conversation
        </button>
        {conversations.map(conv => (
          <div
            key={conv.id}
            className={`p-2 mb-2 rounded cursor-pointer ${currentConversationId === conv.id ? 'bg-blue-200 dark:bg-blue-800' : 'hover:bg-gray-200 dark:hover:bg-gray-800'}`}
            onClick={() => loadConversation(conv.id)}
          >
            <div className="font-semibold truncate">{conv.title}</div>
            <div className="text-xs text-gray-500">{conv.updated_at ? new Date(conv.updated_at).toLocaleString() : ''}</div>
          </div>
        ))}
      </div>
      <Card className="w-full max-w-4xl h-[80vh] flex flex-col shadow-xl">
        <CardHeader className="bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-gray-800 dark:to-gray-900 text-white rounded-t-lg flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-6 w-6" />
              Order Management Assistant
            </CardTitle>
            <p className="text-blue-100 text-sm dark:text-gray-300">Ask me about orders, delivery status, customer information, and more</p>
          </div>
          <button
            aria-label="Toggle dark mode"
            className="ml-auto p-2 rounded-full hover:bg-blue-700 dark:hover:bg-gray-700 transition-colors"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun className="h-5 w-5 text-yellow-300" /> : <Moon className="h-5 w-5 text-gray-200" />}
          </button>
        </CardHeader>

        <CardContent className="flex-1 min-h-0 p-0">
          <ScrollArea className="h-full min-h-0 p-4" ref={scrollAreaRef}>
            <div className="space-y-4 bg-white rounded-lg p-4">
              <AnimatePresence initial={false}>
                {messages
                  .filter(message => !(message.sender === "bot" && (!message.text || !message.text.trim())))
                  .map((message, idx) => (
                    <motion.div
                      key={message.id}
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
                        <div className="whitespace-pre-wrap break-words">{renderMessageText(message.text)}</div>

                        {message.buttons && message.buttons.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {message.buttons.map((button, index) => (
                              <Button
                                key={index}
                                variant="outline"
                                size="sm"
                                className="mr-2 mb-1 bg-transparent"
                                onClick={() => handleButtonClick(button.payload, button.title)}
                              >
                                {button.title}
                              </Button>
                            ))}
                          </div>
                        )}

                        {message.image && (
                          <div className="mt-2">
                            <img
                              src={message.image || "/placeholder.svg"}
                              alt="Bot response"
                              className="max-w-full h-auto rounded"
                            />
                          </div>
                        )}

                        {/* Download Excel button: only show for the last bot message with pincode/order or order details data */}
                        {(() => {
                          // Only show for the last bot message with pincode/order or order details data
                          const isLastBotMsgWithData =
                            message.sender === "bot" &&
                            (/Pincode:/i.test(message.text) || /- Order ID:/i.test(message.text)) &&
                            messages.slice(idx + 1).every(m => !(m.sender === "bot" && (/Pincode:/i.test(m.text) || /- Order ID:/i.test(m.text))));
                          if (!isLastBotMsgWithData) return null;
                          return (
                            <button
                              onClick={handleDownloadExcel}
                              style={{ marginTop: 12, padding: "10px 20px", backgroundColor: "#4CAF50", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}
                            >
                              📥 Download Excel
                            </button>
                          );
                        })()}

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
          </ScrollArea>
        </CardContent>

        <CardFooter className="border-t bg-gray-50 dark:bg-gray-900">
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
              {filteredSuggestions.length > 0 && (
                <ul className="absolute left-0 right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded shadow z-40 max-h-40 overflow-y-auto">
                  {filteredSuggestions.map((s, i) => (
                    <li
                      key={i}
                      className="px-3 py-2 cursor-pointer hover:bg-blue-100 dark:hover:bg-gray-700"
                      onClick={() => setInput(s)}
                    >
                      {s}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <Button type="submit" disabled={isLoading || !input.trim()} className="bg-blue-600 hover:bg-blue-700">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </CardFooter>
      </Card>
    </div>
  )
}
