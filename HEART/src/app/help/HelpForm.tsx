'use client'

import { useState } from 'react'
import Link from 'next/link'

export default function HelpForm() {
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    
    try {
      // In a real implementation, we would send an email here
      // For now, we'll just simulate a delay
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      // This would send an email to TommyMoran@gmail.com
      console.log('Sending help request email:', {
        to: 'TommyMoran@gmail.com',
        subject: 'HEART App Support Request',
        body: message,
        timestamp: new Date().toISOString()
      })
      
      setIsSubmitted(true)
      setMessage('')
    } catch (error) {
      console.error('Error sending help request:', error)
    } finally {
      setIsSubmitting(false)
    }
  }
  
  return (
    <div className="w-full max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-center">Help & Support</h1>
      
      {isSubmitted ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-green-800 mb-2">Request Sent</h2>
          <p className="text-green-700">
            Your request has been sent. We will reply as soon as possible.
          </p>
        </div>
      ) : (
        <div className="bg-white shadow-md rounded-lg p-6 mb-6">
          <p className="mb-4">
            If you need assistance with the HEART application, please describe your issue below and we'll respond as soon as possible.
          </p>
          
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label 
                htmlFor="message" 
                className="block text-gray-700 text-sm font-bold mb-2"
              >
                Describe your issue or question
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                className="form-input"
                placeholder="Please provide details about what you need help with..."
                required
              />
            </div>
            
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={isSubmitting || !message}
            >
              {isSubmitting ? 'Sending...' : 'Submit Request'}
            </button>
          </form>
        </div>
      )}
      
      <div className="flex justify-center">
        <Link 
          href="/"
          className="btn btn-secondary"
        >
          Back to Home
        </Link>
      </div>
    </div>
  )
} 