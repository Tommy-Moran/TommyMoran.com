'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { logAssessmentToExcel } from '@/lib/excel-logger'

interface AIResponse {
  recommendation: string
  rationale: string
  nextSteps: string
  consultOtherTeams: string
}

export default function ResultsDisplay() {
  const [aiResponse, setAiResponse] = useState<AIResponse | null>(null)
  const [echoType, setEchoType] = useState<'inpatient' | 'outpatient' | 'not-indicated'>('not-indicated')
  const [caseId, setCaseId] = useState<string>('')
  
  useEffect(() => {
    // Get the AI response from session storage
    if (typeof window !== 'undefined') {
      const responseStr = sessionStorage.getItem('ai_response')
      const storedCaseId = sessionStorage.getItem('case_id') || ''
      
      if (responseStr) {
        const response = JSON.parse(responseStr) as AIResponse
        setAiResponse(response)
        setCaseId(storedCaseId)
        
        // Determine the echo type based on the recommendation
        if (response.recommendation.toLowerCase().includes('inpatient')) {
          setEchoType('inpatient')
        } else if (response.recommendation.toLowerCase().includes('outpatient')) {
          setEchoType('outpatient')
        } else {
          setEchoType('not-indicated')
        }
        
        // Log the assessment to Excel Online
        logAssessment(response)
      }
    }
  }, [])
  
  const logAssessment = async (response: AIResponse) => {
    try {
      // Get clinical data from session storage
      const clinicalContext = sessionStorage.getItem('clinical_context') || ''
      const clinicalQuestion = sessionStorage.getItem('clinical_question') || ''
      // Log to Excel Online
      await logAssessmentToExcel({
        timestamp: new Date().toISOString(),
        clinicalContext,
        clinicalQuestion,
        recommendation: response.recommendation,
        rationale: response.rationale,
        nextSteps: response.nextSteps,
        consultOtherTeams: response.consultOtherTeams,
        outcome: echoType
      })
    } catch (error) {
      console.error('Error logging assessment:', error)
    }
  }
  
  const copyToClipboard = () => {
    const clinicalContext = sessionStorage.getItem('clinical_context') || ''
    const clinicalQuestion = sessionStorage.getItem('clinical_question') || ''
    const recommendation = aiResponse ? aiResponse.recommendation : ''
    
    const textToCopy = `Clinical Context:\n${clinicalContext}\n\nClinical Question:\n${clinicalQuestion}\n\nRecommendation:\n${recommendation}\n\nCase ID: ${caseId}`
    
    navigator.clipboard.writeText(textToCopy)
      .then(() => {
        alert('Clinical information copied to clipboard')
      })
      .catch(err => {
        console.error('Failed to copy text: ', err)
      })
  }
  
  return (
    <div className="w-full max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-center">Echo Appropriateness Assessment</h1>
      
      {aiResponse ? (
        <>
          <div className="bg-white shadow-md rounded-lg overflow-hidden mb-6">
            <div className="bg-primary text-white p-4">
              <h2 className="text-xl font-semibold">Recommendation</h2>
            </div>
            <div className="p-4">
              <p>{aiResponse.recommendation}</p>
            </div>
          </div>
          
          <div className="bg-white shadow-md rounded-lg overflow-hidden mb-6">
            <div className="bg-secondary text-white p-4">
              <h2 className="text-xl font-semibold">Rationale</h2>
            </div>
            <div className="p-4">
              <p>{aiResponse.rationale}</p>
            </div>
          </div>
          
          <div className="bg-white shadow-md rounded-lg overflow-hidden mb-6">
            <div className="bg-secondary text-white p-4">
              <h2 className="text-xl font-semibold">Next Steps</h2>
            </div>
            <div className="p-4">
              <p>{aiResponse.nextSteps}</p>
              
              {echoType === 'inpatient' && (
                <div className="mt-4 flex flex-col sm:flex-row gap-4">
                  <button 
                    onClick={copyToClipboard}
                    className="btn btn-primary"
                  >
                    Copy Clinical Context
                  </button>
                  <a 
                    href="https://intranet.ths.tas.gov.au/healthforms?formNameOrNumber=echo&siteLimit=1_RHH" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="btn btn-secondary"
                  >
                    RHH Echo Request Form
                  </a>
                </div>
              )}
              
              {echoType === 'outpatient' && (
                <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p>Complete the paper echo request form and submit it to Cardiology Reception, Level 2.</p>
                </div>
              )}
              
              {echoType === 'not-indicated' && (
                <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p>Based on validated inpatient echo appropriateness criteria, an echocardiogram is not indicated. If you still feel it is required, please discuss with the Cardiology team directly via the hospital switchboard 03 6166 8308.</p>
                </div>
              )}
            </div>
          </div>
          
          {aiResponse.consultOtherTeams && (
            <div className="bg-white shadow-md rounded-lg overflow-hidden mb-6">
              <div className="bg-secondary text-white p-4">
                <h2 className="text-xl font-semibold">Consider Consulting</h2>
              </div>
              <div className="p-4">
                <p>{aiResponse.consultOtherTeams}</p>
              </div>
            </div>
          )}
          
          <div className="flex flex-col sm:flex-row justify-center gap-4 mt-8">
            <Link 
              href="/" 
              className="btn btn-primary"
            >
              Start New Assessment
            </Link>
            <Link 
              href="/context" 
              className="btn btn-secondary"
            >
              Edit Submission
            </Link>
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center p-8">
          <p>Loading results...</p>
        </div>
      )}
    </div>
  )
} 