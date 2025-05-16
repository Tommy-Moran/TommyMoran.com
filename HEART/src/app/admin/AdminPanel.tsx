'use client'

import { useState } from 'react'
import Link from 'next/link'
import { getAuditLogs, downloadAuditCsv } from '@/lib/audit-logger'

interface AuditLog {
  id: number
  caseId: string
  clinicalContext: string
  clinicalQuestion: string
  aiResponse: {
    recommendation: string
    rationale: string
    nextSteps: string
    consultOtherTeams: string
  }
  timestamp: string
  createdAt: string
}

export default function AdminPanel() {
  const [password, setPassword] = useState('')
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!password) {
      setError('Password is required')
      return
    }
    
    setLoading(true)
    setError('')
    
    try {
      const auditLogs = await getAuditLogs(password)
      
      if (Array.isArray(auditLogs)) {
        setLogs(auditLogs)
        setAuthenticated(true)
      } else {
        setError('Failed to retrieve logs. Incorrect password?')
      }
    } catch (error) {
      setError('Error retrieving logs: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }
  
  const handleDownloadCsv = async () => {
    setLoading(true)
    try {
      await downloadAuditCsv(password)
    } catch (error) {
      setError('Error downloading CSV: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">HEART Admin Panel</h1>
      
      {!authenticated ? (
        <div className="bg-white shadow-md rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Authentication Required</h2>
          
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label htmlFor="password" className="block text-gray-700 mb-2">
                Admin Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="form-input w-full p-2 border rounded"
                placeholder="Enter admin password"
                required
              />
            </div>
            
            {error && (
              <div className="mb-4 p-2 bg-red-50 text-red-700 border border-red-200 rounded">
                {error}
              </div>
            )}
            
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={loading}
            >
              {loading ? 'Loading...' : 'Access Audit Logs'}
            </button>
          </form>
        </div>
      ) : (
        <div>
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold">Audit Logs ({logs.length})</h2>
            <div className="flex gap-4">
              <button
                onClick={handleDownloadCsv}
                className="btn btn-secondary"
                disabled={loading}
              >
                {loading ? 'Processing...' : 'Download CSV'}
              </button>
              <Link href="/" className="btn btn-primary">
                Back to Home
              </Link>
            </div>
          </div>
          
          {error && (
            <div className="mb-4 p-2 bg-red-50 text-red-700 border border-red-200 rounded">
              {error}
            </div>
          )}
          
          <div className="bg-white shadow-md rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Case ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date/Time
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Recommendation
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-6 py-4 whitespace-nowrap font-medium">
                      {log.caseId}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {new Date(log.createdAt).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      {log.aiResponse.recommendation}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => {
                          alert(`Clinical Context: ${log.clinicalContext}\n\nClinical Question: ${log.clinicalQuestion}`)
                        }}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
                
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-4 text-center text-gray-500">
                      No audit logs found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
} 