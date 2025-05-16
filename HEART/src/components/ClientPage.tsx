// The purpose of this component is to provide a wrapper for client-side rendering in Next.js
// This is needed because the use of hooks and client-side features requires the "use client" directive

'use client'

import { ReactNode } from 'react'

interface ClientPageProps {
  children: ReactNode
}

export function ClientPage({ children }: ClientPageProps) {
  return <>{children}</>
} 