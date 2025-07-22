"use client"

import { useState, useEffect, useRef } from "react"
import { SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { ChatArea } from "@/components/chat-area"
import { Toaster } from "@/components/ui/toaster"

export interface Message {
  id: string
  text: string
  sender: "user" | "bot"
  timestamp?: number
}

export interface Conversation {
  id: string
  title: string
  created_at: number
  updated_at: number
  messages: Message[]
}

export default function ChatbotPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null)
  const [loading, setLoading] = useState(false)
  const [inputValue, setInputValue] = useState("")

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
  }, [])

  const loadConversations = async () => {
    try {
      const response = await fetch("/api/conversations")
      const data = await response.json()
      setConversations(data.conversations || [])
    } catch (error) {
      console.error("Failed to load conversations:", error)
    }
  }

  const createNewConversation = async (firstMessage: string) => {
    setLoading(true)
    try {
      const messageObj: Message = {
        id: Date.now().toString(),
        text: firstMessage,
        sender: "user",
        timestamp: Date.now(),
      }

      // Create conversation with first message
      const response = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageObj }),
      })

      const result = await response.json()
      if (result.success) {
        // Get bot responses from Rasa (array)
        const botResponses = await sendToRasa(firstMessage, result.conversation_id)
        // Add all bot messages to conversation
        for (const botMessage of botResponses) {
          await appendMessage(result.conversation_id, botMessage)
        }
        // Load the new conversation
        await loadConversationById(result.conversation_id)
        await loadConversations()
      }
    } catch (error) {
      console.error("Failed to create conversation:", error)
    } finally {
      setLoading(false)
    }
  }

  const appendMessage = async (conversationId: string, message: Message) => {
    try {
      await fetch(`/api/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      })
    } catch (error) {
      console.error("Failed to append message:", error)
    }
  }

  const sendToRasa = async (message: string, sessionId: string): Promise<Message[]> => {
    try {
      const response = await fetch("http://localhost:5005/webhooks/rest/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: sessionId,
          message: message,
        }),
      })

      const data = await response.json()
      if (data && data.length > 0) {
        return data
          .filter((item: any) => item.text)
          .map((item: any) => ({
            id: Date.now().toString() + Math.random(),
            text: item.text,
            sender: "bot",
            timestamp: Date.now(),
          }))
      }
    } catch (error) {
      console.error("Failed to get Rasa response:", error)
      return [{
        id: Date.now().toString(),
        text: "Sorry, I encountered an error. Please try again.",
        sender: "bot",
        timestamp: Date.now(),
      }]
    }
    return []
  }

  const loadConversationById = async (conversationId: string) => {
    try {
      const response = await fetch(`/api/conversations/${conversationId}`)
      const conversation = await response.json()
      if (conversation && !conversation.error) {
        setCurrentConversation(conversation)
      }
    } catch (error) {
      console.error("Failed to load conversation:", error)
    }
  }

  const sendMessage = async (message: string) => {
    if (!currentConversation) return

    setLoading(true)
    try {
      const userMessage: Message = {
        id: Date.now().toString(),
        text: message,
        sender: "user",
        timestamp: Date.now(),
      }

      // Add user message to conversation
      await appendMessage(currentConversation.id, userMessage)

      // Get bot responses (array)
      const botResponses = await sendToRasa(message, currentConversation.id)

      // Add all bot messages to conversation
      for (const botMessage of botResponses) {
        await appendMessage(currentConversation.id, botMessage)
      }

      // Reload conversation to show new messages
      await loadConversationById(currentConversation.id)
      await loadConversations()
    } catch (error) {
      console.error("Failed to send message:", error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <SidebarProvider defaultOpen={true}>
        <AppSidebar
          conversations={conversations}
          currentConversation={currentConversation}
          onSelectConversation={loadConversationById}
          onNewConversation={() => setCurrentConversation(null)}
          onIntentClick={setInputValue}
        />
        <main className="flex-1 flex flex-col">
          <ChatArea
            conversation={currentConversation}
            onSendMessage={sendMessage}
            onCreateConversation={createNewConversation}
            loading={loading}
            inputValue={inputValue}
            setInputValue={setInputValue}
          />
        </main>
      </SidebarProvider>
      <Toaster />
    </div>
  )
}
