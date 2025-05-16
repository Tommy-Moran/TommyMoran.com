'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { logToAudit } from '@/lib/audit-logger'

export default function LoadingScreen() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAIResponse = async () => {
      try {
        if (typeof window === 'undefined') return
        
        // Clear any previous AI response to ensure we don't use cached results
        sessionStorage.removeItem('ai_response')
        sessionStorage.removeItem('case_id')
        
        const clinicalContext = sessionStorage.getItem('clinical_context') || ''
        const clinicalQuestion = sessionStorage.getItem('clinical_question') || ''
        const timestamp = sessionStorage.getItem('submission_timestamp') || new Date().toISOString()
        
        if (!clinicalContext || !clinicalQuestion) {
          throw new Error('Missing clinical information. Please go back and complete the form.')
        }
        
        console.log('Sending request with context:', clinicalContext.substring(0, 50) + '...')
        
        // Call the API route instead of directly calling OpenAI
        const response = await fetch('/api/assess-echo', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            clinicalContext, 
            clinicalQuestion,
            timestamp // Include timestamp to ensure uniqueness
          }),
          // Prevent browser caching of the API response
          cache: 'no-store'
        })
        
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Failed to get assessment')
        }
        
        const aiResponse = await response.json()
        console.log('Received AI response:', aiResponse.recommendation)
        
        // Store the AI response in session storage
        sessionStorage.setItem('ai_response', JSON.stringify(aiResponse))
        
        // Log to audit backend and get a case ID
        const caseId = await logToAudit({
          clinicalContext,
          clinicalQuestion,
          aiResponse,
          timestamp
        })
        
        // Store the case ID in session storage
        sessionStorage.setItem('case_id', caseId)
        
        // Navigate to the results page
        router.push('/results')
      } catch (error) {
        console.error('Error fetching AI response:', error)
        setError(error instanceof Error ? error.message : 'Unknown error occurred')
      }
    }
    
    fetchAIResponse()
  }, [router])

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      <h1 className="text-2xl font-bold mb-8 text-center">
        Assessing Echo Appropriateness...
      </h1>
      
      {error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 max-w-md">
          <h2 className="text-lg font-semibold text-red-800 mb-2">Error</h2>
          <p className="text-red-700">{error}</p>
          <button 
            onClick={() => router.push('/context')}
            className="mt-4 btn btn-primary"
          >
            Return to Form
          </button>
        </div>
      ) : (
        <>
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary"></div>
          
          <p className="mt-8 text-gray-600">
            Please wait while we analyze your request...
          </p>
        </>
      )}
    </div>
  )
} 