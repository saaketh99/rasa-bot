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

interface AppSidebarProps {
  conversations: Conversation[]
  currentConversation: Conversation | null
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
}

export function AppSidebar({
  conversations,
  currentConversation,
  onSelectConversation,
  onNewConversation,
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
          <SidebarGroupLabel className="text-gray-400 text-xs uppercase tracking-wide">
            Recent Sessions
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <ScrollArea className="h-[400px]">
              <SidebarMenu>
                {conversations.map((conversation) => (
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
