import { NextResponse } from 'next/server';
import OpenAI from 'openai';

// Initialize the OpenAI client with environment variable
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Assistant ID for the HEART application
const ASSISTANT_ID = process.env.OPENAI_ASSISTANT_ID || 'asst_qCeKG8yoFLKfbwQANHV28xNX';

// Function to clean reference markers from text
function cleanReferenceMarkers(text: string): string {
  // Remove patterns like 【4:0†Echo Inappropriateness Criteria.txt】
  return text.replace(/【[^】]*】/g, '');
}

// Function to extract recommendation from text
function extractRecommendation(text: string): string {
  // First check if the text explicitly says "not indicated" anywhere in the opening part
  if (text.toLowerCase().includes("not indicated")) {
    return "Echocardiogram is not indicated.";
  }
  
  // Look for a pattern like "Recommendation: An inpatient echocardiogram is indicated within 24 hours"
  const recommendationMatch = text.match(/Recommendation:\s*(.*?)(?:\s*Rationale:|$)/i);
  
  if (recommendationMatch && recommendationMatch[1]) {
    const fullRec = recommendationMatch[1].trim();
    
    // Double-check if this recommendation says "not indicated" despite being extracted
    if (fullRec.toLowerCase().includes("not indicated")) {
      return "Echocardiogram is not indicated.";
    }
    
    // Check if it's indicated or not
    let type = '';
    if (fullRec.toLowerCase().includes('inpatient')) {
      type = 'Inpatient';
    } else if (fullRec.toLowerCase().includes('outpatient')) {
      type = 'Outpatient';
    }
    
    // Check for timeframe with expanded patterns
    let timeframe = '';
    // Look for specific patterns like "within X hours/days/weeks"
    const timeframeMatch = fullRec.match(/within\s+(\d+)\s+(hours?|days?|weeks?)/i);
    if (timeframeMatch) {
      timeframe = `within ${timeframeMatch[1]} ${timeframeMatch[2]}`;
    } 
    // Check for common timing keywords
    else if (fullRec.toLowerCase().includes('urgent')) {
      timeframe = 'urgent';
    } else if (fullRec.toLowerCase().includes('emergency')) {
      timeframe = 'urgent';
    } else if (fullRec.toLowerCase().includes('immediate')) {
      timeframe = 'immediate';
    } else if (fullRec.toLowerCase().includes('routine')) {
      timeframe = 'routine';
    } else if (fullRec.toLowerCase().includes('elective')) {
      timeframe = 'elective';
    } else if (fullRec.toLowerCase().includes('as soon as possible')) {
      timeframe = 'as soon as possible';
    }
    // If no specific timeframe in recommendation, check the entire text for timing clues
    else {
      // Look in the entire text (including rationale) for timing indications
      if (text.toLowerCase().includes('urgent') && !text.toLowerCase().includes('not urgent')) {
        timeframe = 'urgent';
      } else if (text.toLowerCase().includes('emergency')) {
        timeframe = 'urgent';
      } else if (text.toLowerCase().includes('immediate')) {
        timeframe = 'immediate';
      } else if ((text.toLowerCase().includes('as soon as possible') || text.toLowerCase().includes('asap'))) {
        timeframe = 'as soon as possible';
      }
      // Default timeframe based on study type
      else if (type === 'Inpatient' && !timeframe) {
        timeframe = 'during this admission';
      }
    }
    
    if (type && timeframe) {
      return `${type} echocardiogram is indicated ${timeframe}.`;
    } else if (type) {
      return `${type} echocardiogram is indicated.`;
    }
  }
  
  // Look for potential conflicts between recommendation and rationale
  // This handles cases where the recommendation and rationale might disagree
  if (text.toLowerCase().includes("not appropriate") || 
      text.toLowerCase().includes("inappropriateness criterion") || 
      text.toLowerCase().includes("does not warrant")) {
    return "Echocardiogram is not indicated.";
  }
  
  // If no explicit recommendation format or if we can't determine, return a default
  return "Assessment completed - please review rationale.";
}

// Function to extract just the rationale from the text
function extractRationale(text: string): string {
  // Look for a pattern like "Rationale: The clinical context involves..."
  const rationaleMatch = text.match(/Rationale:\s*(.*?)(?:\s*Next Steps:|$)/i);
  
  if (rationaleMatch && rationaleMatch[1]) {
    return rationaleMatch[1].trim();
  }
  
  // If no explicit rationale format is found, return a default
  return "Please review the details in the assessment.";
}

// Function to extract next steps from the text
function extractNextSteps(text: string): string {
  // Look for a pattern like "Next Steps: Complete and submit..."
  const nextStepsMatch = text.match(/Next Steps:\s*(.*?)(?:\s*Consult Other Teams:|$)/i);
  
  if (nextStepsMatch && nextStepsMatch[1]) {
    return nextStepsMatch[1].trim();
  }
  
  return "Please review the assessment and follow appropriate clinical guidelines.";
}

// Function to extract consult recommendations from the text
function extractConsultRecommendations(text: string): string {
  // Look for a pattern like "Consult Other Teams: Cardiology"
  const consultMatch = text.match(/Consult Other Teams:\s*(.*?)(?:\s*$)/i);
  
  if (consultMatch && consultMatch[1]) {
    return consultMatch[1].trim();
  }
  
  return "Consider consultation with specialists as needed based on the assessment.";
}

export async function POST(request: Request) {
  try {
    if (!process.env.OPENAI_API_KEY) {
      return NextResponse.json(
        { error: 'OpenAI API key is not configured' },
        { status: 500 }
      );
    }

    // Parse the request body
    const { clinicalContext, clinicalQuestion } = await request.json();

    if (!clinicalContext || !clinicalQuestion) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Create a thread
    const thread = await openai.beta.threads.create();
    
    // Add a message to the thread
    await openai.beta.threads.messages.create(thread.id, {
      role: "user",
      content: `Clinical Context: ${clinicalContext}\n\nClinical Question: ${clinicalQuestion}`
    });
    
    // Run the assistant
    const run = await openai.beta.threads.runs.create(thread.id, {
      assistant_id: ASSISTANT_ID
    });
    
    // Wait for the run to complete
    const completedRun = await waitForRunCompletion(thread.id, run.id);
    
    // Get the messages
    const messages = await openai.beta.threads.messages.list(thread.id);
    const assistantMessages = messages.data.filter(msg => msg.role === 'assistant');
    
    if (assistantMessages.length === 0) {
      throw new Error('No response received from assistant');
    }
    
    const lastMessage = assistantMessages[0];
    
    // Process the assistant's response
    let responseContent = '';
    
    if (lastMessage.content && lastMessage.content.length > 0) {
      const contentItem = lastMessage.content[0];
      if (contentItem.type === 'text') {
        responseContent = cleanReferenceMarkers(contentItem.text.value);
      }
    }
    
    // Try to parse the response as JSON, or use a simple format if not possible
    let response;
    try {
      response = JSON.parse(responseContent);
    } catch (e) {
      // If not in JSON format, create a structured response by parsing the text
      const cleanedContent = cleanReferenceMarkers(responseContent);
      
      response = {
        recommendation: extractRecommendation(cleanedContent),
        rationale: extractRationale(cleanedContent),
        nextSteps: extractNextSteps(cleanedContent),
        consultOtherTeams: extractConsultRecommendations(cleanedContent)
      };
    }

    // Create response with cache control headers
    const nextResponse = NextResponse.json(response);
    
    // Set cache control headers to prevent caching
    nextResponse.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    nextResponse.headers.set('Pragma', 'no-cache');
    nextResponse.headers.set('Expires', '0');
    
    return nextResponse;
  } catch (error) {
    console.error('Error calling OpenAI:', error);
    return NextResponse.json(
      { error: 'Failed to assess echo appropriateness' },
      { status: 500 }
    );
  }
}

// Helper function for waiting for run completion
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