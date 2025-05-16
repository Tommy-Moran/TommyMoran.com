'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function ContextForm() {
  const [clinicalContext, setClinicalContext] = useState('')
  const [clinicalQuestion, setClinicalQuestion] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const router = useRouter()

  // Check if there's existing data to pre-fill
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedContext = sessionStorage.getItem('clinical_context')
      const savedQuestion = sessionStorage.getItem('clinical_question')
      
      if (savedContext) setClinicalContext(savedContext)
      if (savedQuestion) setClinicalQuestion(savedQuestion)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      // Store the context and question for AI submission and later review
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('clinical_context', clinicalContext)
        sessionStorage.setItem('clinical_question', clinicalQuestion)
        
        // Add a timestamp to ensure each submission is treated as new
        sessionStorage.setItem('submission_timestamp', new Date().toISOString())
        
        // Clear any previous AI response
        sessionStorage.removeItem('ai_response')
      }
      
      // Navigate to loading page
      router.push('/loading')
    } catch (error) {
      console.error('Error submitting data:', error)
      setIsSubmitting(false)
      // Display error message to user
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      <div className="w-full max-w-2xl">
        <h1 className="text-2xl sm:text-3xl font-sans font-bold mb-4 text-primary tracking-wide max-w-2xl mx-auto">
          Clinical Context Checker
        </h1>
        <div className="mb-6 p-4 bg-gradient-to-r from-blue-100 to-orange-50 border-l-4 border-blue-400 rounded-md shadow-sm transition-all duration-300 hover:shadow-lg hover:translate-y-[-2px]">
          <p className="text-blue-800 text-center text-base">
          This tool employs a custom AI model trained on validated appropriateness criteria  to assess common clinical scenarios for inpatient echocardiogram requests. <span className="font-bold underline">Do not</span> include identifiable patient details such as URN, date of birth, name, or address.
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="bg-white shadow-md rounded-lg p-6">
          <div className="mb-6">
            <label 
              htmlFor="clinicalContext" 
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Clinical Context
            </label>
            <textarea
              id="clinicalContext"
              value={clinicalContext}
              onChange={(e) => setClinicalContext(e.target.value)}
              rows={5}
              className="form-input"
              placeholder="Describe relevant clinical history, findings, symptoms, comorbidities, prior investigations, etc."
              required
            />
          </div>
          
          <div className="mb-6">
            <label 
              htmlFor="clinicalQuestion" 
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Specific Clinical Question
            </label>
            <textarea
              id="clinicalQuestion"
              value={clinicalQuestion}
              onChange={(e) => setClinicalQuestion(e.target.value)}
              rows={3}
              className="form-input"
              placeholder="What exact clinical question do you want the echocardiogram to answer?"
              required
            />
          </div>
          
          <div className="flex items-center justify-between mt-6">
            <Link
              href="/"
              className="btn btn-secondary"
            >
              Back
            </Link>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !clinicalContext || !clinicalQuestion}
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
} 