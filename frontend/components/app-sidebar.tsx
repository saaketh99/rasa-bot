"use client"

import { Home, Layers, Lightbulb, Plus, MessageSquare } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Conversation } from "@/app/page"

const SUGGESTED_INTENTS = [
  "Show me the orders for Wakefit from 2025-06-21 to 2025-07-31",
  "Get me the orders going from Hyderabad to Visakhapatnam",
  "How many shipments were delivered to Coimbatore?",
  "Show all pending orders",
  "Find orders with wallet payment method",
  "Order status for OLAELE04199",
  "Track order with invoice number 9849577711",
  "Show me all delivered orders within 2 days",
  "Is service available in pincode 530013?",
  "Delivery summary from 2025-06-21 to 2025-07-31",
  "Give me complete details for order ID OLAELE04199 ",
  "long pending orders",
  "Show pending orders from the last 5 days",
  "Top delivery pincodes for Ola Ele",
  "how delivered orders distributed across cities",
  "Delivered report across cities for Ola ELE",
  "Show me the order trend for the past 30 days",
  "What’s the delay trend in the past 15 days?",
  "Who is updating most of the delivery statuses?"
];

interface AppSidebarProps {
  conversations: Conversation[]
  currentConversation: Conversation | null
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onIntentClick: (intent: string) => void;
}

export function AppSidebar({
  conversations,
  currentConversation,
  onSelectConversation,
  onNewConversation,
  onIntentClick,
}: AppSidebarProps) {
  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffTime = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return "Today"
    if (diffDays === 1) return "Yesterday"
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  const truncateTitle = (title: string, maxLength = 30) => {
    return title.length > maxLength ? title.substring(0, maxLength) + "..." : title
  }

  return (
    <Sidebar className="border-r border-gray-800 bg-gray-900">
      <SidebarHeader className="p-4">
        <Button onClick={onNewConversation} className="w-full bg-blue-600 hover:bg-blue-700 text-white">
          <Plus className="w-4 h-4 mr-2" />
          New Session
        </Button>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-gray-400 text-xs uppercase tracking-wide">Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton className="text-gray-300 hover:text-white hover:bg-gray-800">
                  <Home className="w-4 h-4" />
                  <span>Home</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton className="text-gray-300 hover:text-white hover:bg-gray-800">
                  <Layers className="w-4 h-4" />
                  <span>Spaces</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton className="text-gray-300 hover:text-white hover:bg-gray-800">
                  <Lightbulb className="w-4 h-4" />
                  <span>Intents</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-gray-400 text-xs uppercase tracking-wide">Intents</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {SUGGESTED_INTENTS.map((intent, idx) => (
                <SidebarMenuItem key={idx}>
                  <SidebarMenuButton
                    className="text-gray-300 hover:text-white hover:bg-gray-800"
                    onClick={() => onIntentClick(intent)}
                  >
                    <span>{intent}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-gray-400 text-xs uppercase tracking-wide">
            Recent Sessions
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <ScrollArea className="h-[400px]">
              <SidebarMenu>
                {/* Sort conversations by updated_at descending (most recent first) */}
                {[...conversations].sort((a, b) => b.updated_at - a.updated_at).map((conversation) => (
                  <SidebarMenuItem key={conversation.id}>
                    <SidebarMenuButton
                      onClick={() => onSelectConversation(conversation.id)}
                      isActive={currentConversation?.id === conversation.id}
                      className="text-gray-300 hover:text-white hover:bg-gray-800 data-[active=true]:bg-gray-800 data-[active=true]:text-white"
                    >
                      <MessageSquare className="w-4 h-4" />
                      <div className="flex flex-col items-start flex-1 min-w-0">
                        <span className="truncate text-sm">{truncateTitle(conversation.title)}</span>
                        <span className="text-xs text-gray-500">{formatDate(conversation.updated_at)}</span>
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </ScrollArea>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t border-gray-800">
        <div className="text-xs text-gray-500 text-center">Powered by Rasa & FastAPI</div>
      </SidebarFooter>
    </Sidebar>
  )
}
