interface AuditData {
  clinicalContext: string;
  clinicalQuestion: string;
  aiResponse: any;
  timestamp: string;
}

interface AuditResponse {
  success: boolean;
  caseId: string;
}

// The URL of your Render backend
const AUDIT_API_URL = process.env.NEXT_PUBLIC_AUDIT_API_URL || 'https://heart-audit-api.onrender.com';

/**
 * Logs assessment data to the audit backend
 */
export async function logToAudit(data: AuditData): Promise<string> {
  try {
    const response = await fetch(`${AUDIT_API_URL}/api/log-assessment`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Error logging to audit: ${response.statusText}`);
    }

    const result: AuditResponse = await response.json();
    return result.caseId;
  } catch (error) {
    console.error('Failed to log to audit:', error);
    // Return a fallback case ID if something fails
    return `H${Math.floor(Math.random() * 900000) + 100000}`;
  }
}

/**
 * Retrieves all audit logs (password protected)
 */
export async function getAuditLogs(password: string): Promise<any[]> {
  try {
    const response = await fetch(`${AUDIT_API_URL}/api/audit-logs`, {
      method: 'GET',
      headers: {
        'X-Audit-Password': password,
      },
    });

    if (!response.ok) {
      throw new Error(`Error retrieving audit logs: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to retrieve audit logs:', error);
    return [];
  }
}

/**
 * Downloads audit logs as CSV (password protected)
 */
export async function downloadAuditCsv(password: string): Promise<void> {
  try {
    const response = await fetch(`${AUDIT_API_URL}/api/audit-logs/csv`, {
      method: 'GET',
      headers: {
        'X-Audit-Password': password,
      },
    });

    if (!response.ok) {
      throw new Error(`Error downloading CSV: ${response.statusText}`);
    }

    // Create a blob from the response
    const blob = await response.blob();
    
    // Create a download link
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = 'heart_audit_logs.csv';
    
    // Add to the DOM and trigger a click
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    console.error('Failed to download CSV:', error);
    alert('Failed to download CSV. Please try again later.');
  }
} 