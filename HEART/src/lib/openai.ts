import OpenAI from 'openai';

// Initialize the OpenAI client
// In production, you would load this from an environment variable
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || 'your-api-key-here',
});

// Assistant ID for the HEART application
const ASSISTANT_ID = 'asst_qCeKG8yoFLKfbwQANHV28xNX';

interface EchoAssessmentResponse {
  recommendation: string;
  rationale: string;
  nextSteps: string;
  consultOtherTeams: string;
}

/**
 * Processes a clinical context and question through the OpenAI Assistant
 * @param clinicalContext The clinical context provided by the user
 * @param clinicalQuestion The specific question about the echo
 * @returns Structured assessment response
 */
export async function assessEchoAppropriateness(
  clinicalContext: string,
  clinicalQuestion: string
): Promise<EchoAssessmentResponse> {
  try {
    // For demonstration purposes, returning a mock response
    // In production, this would be replaced with actual OpenAI API calls
    
    // Create a thread
    // const thread = await openai.beta.threads.create();
    
    // Add a message to the thread
    // await openai.beta.threads.messages.create(thread.id, {
    //   role: "user",
    //   content: `Clinical Context: ${clinicalContext}\n\nClinical Question: ${clinicalQuestion}`
    // });
    
    // Run the assistant
    // const run = await openai.beta.threads.runs.create(thread.id, {
    //   assistant_id: ASSISTANT_ID
    // });
    
    // Wait for the run to complete
    // const completedRun = await waitForRunCompletion(thread.id, run.id);
    
    // Get the messages
    // const messages = await openai.beta.threads.messages.list(thread.id);
    // const lastMessage = messages.data[0];
    
    // Parse the response and return structured data
    // const response = parseAssistantResponse(lastMessage.content);
    
    // For demonstration, return mock data
    return {
      recommendation: "Inpatient echocardiogram is appropriate",
      rationale: "Given the clinical context of acute heart failure and hypotension, an urgent inpatient echocardiogram is indicated to assess left ventricular function and potential valvular abnormalities.",
      nextSteps: "Complete inpatient echo request via iCVIS. Include relevant clinical information and specific questions to be answered.",
      consultOtherTeams: "Consider cardiology consult if hemodynamic instability continues."
    };
  } catch (error) {
    console.error('Error calling OpenAI:', error);
    throw new Error('Failed to assess echo appropriateness');
  }
}

// Helper function to wait for a run to complete
async function waitForRunCompletion(threadId: string, runId: string) {
  let runStatus = await openai.beta.threads.runs.retrieve(threadId, runId);
  
  // Poll until the run is completed
  while (runStatus.status !== 'completed') {
    // If the run failed, throw an error
    if (runStatus.status === 'failed') {
      throw new Error(`Run failed: ${runStatus.last_error}`);
    }
    
    // Wait for a moment before checking again
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Check the status again
    runStatus = await openai.beta.threads.runs.retrieve(threadId, runId);
  }
  
  return runStatus;
}

// Helper function to parse the assistant's response into structured data
function parseAssistantResponse(content: any): EchoAssessmentResponse {
  // In a real implementation, parse the content from the assistant
  // This is just a placeholder
  return {
    recommendation: "Default recommendation",
    rationale: "Default rationale",
    nextSteps: "Default next steps",
    consultOtherTeams: "Default consult other teams"
  };
} 