import '@/styles/globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'HEART - Hobart Echo Appropriateness Review Tool',
  description: 'Clinical guidance web app for Royal Hobart Hospital',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <main className="container-fluid py-4">
          {children}
        </main>
        <footer className="py-4 text-center text-sm text-gray-500">
          <div className="container-fluid">
            {/* Copyright removed from global footer */}
          </div>
        </footer>
      </body>
    </html>
  )
} 