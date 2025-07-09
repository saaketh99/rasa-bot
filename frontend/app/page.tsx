'use client'

import dynamic from 'next/dynamic'

const Chat = dynamic(() => import('@/components/chat').then(mod => ({ default: mod.Chat })), {
  ssr: false,
  loading: () => (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading chat interface...</p>
      </div>
    </div>
  ),
})

export default function Home() {
  return (
    <main className="min-h-screen">
      <Chat />
    </main>
  )
}
