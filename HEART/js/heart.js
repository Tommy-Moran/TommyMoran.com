/*
 * HEART - Hobart Echo Appropriateness Review Tool
 * Frontend JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const clinicalForm = document.getElementById('clinical-form');
    const loadingScreen = document.getElementById('loading-screen');
    const resultsContainer = document.getElementById('results-container');
    const caseIdValue = document.getElementById('case-id-value');
    const recommendationContent = document.getElementById('recommendation-content');
    const rationaleContent = document.getElementById('rationale-content');
    const nextStepsContent = document.getElementById('next-steps-content');
    const consultContent = document.getElementById('consult-content');
    const inpatientActions = document.getElementById('inpatient-actions');
    const copyContextButton = document.getElementById('copy-context-button');
    const editContextButton = document.getElementById('new-assessment-button');
    
    // Clinical context and question textarea elements
    const clinicalContextTextarea = document.getElementById('clinical-context');
    const clinicalQuestionTextarea = document.getElementById('clinical-question');
    
    // Store clinical context for potential copying later
    let savedClinicalContext = '';
    let savedClinicalQuestion = '';
    let savedCaseId = '';
    
    // Add event listener to the form submission
    if (clinicalForm) {
        clinicalForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get values from the form
            savedClinicalContext = clinicalContextTextarea.value;
            savedClinicalQuestion = clinicalQuestionTextarea.value;
            
            // Validate that both fields have content
            if (!savedClinicalContext.trim() || !savedClinicalQuestion.trim()) {
                alert('Please provide both clinical context and a specific question.');
                return;
            }
            
            // Hide the form and show loading screen
            clinicalForm.style.display = 'none';
            loadingScreen.style.display = 'flex';
            
            // Send request to the backend
            fetch('https://tommymoran-com-chatbot.onrender.com/HEART/assess', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    clinical_context: savedClinicalContext,
                    clinical_question: savedClinicalQuestion
                }),
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Process the response
                if (data.error) {
                    throw new Error(data.error);
                }
                
                // Save the case ID
                savedCaseId = data.case_id;
                
                // Hide loading screen and show results
                loadingScreen.style.display = 'none';
                resultsContainer.style.display = 'block';
                
                // Populate the results
                caseIdValue.textContent = data.case_id;
                
                // Handle sections based on parsed data
                if (data.sections) {
                    // Recommendation
                    if (data.sections.Recommendation) {
                        recommendationContent.textContent = data.sections.Recommendation;
                    } else {
                        recommendationContent.textContent = 'No recommendation provided.';
                    }
                    
                    // Rationale
                    if (data.sections.Rationale) {
                        rationaleContent.textContent = data.sections.Rationale;
                    } else {
                        rationaleContent.textContent = 'No rationale provided.';
                    }
                    
                    // Next Steps
                    if (data.sections['Next Steps']) {
                        nextStepsContent.textContent = data.sections['Next Steps'];
                        
                        // Check if inpatient is mentioned in the recommendation or next steps
                        const isInpatient = 
                            (data.sections.Recommendation && data.sections.Recommendation.toLowerCase().includes('inpatient')) ||
                            (data.sections['Next Steps'] && data.sections['Next Steps'].toLowerCase().includes('inpatient'));
                        
                        // Show/hide inpatient actions accordingly
                        inpatientActions.style.display = isInpatient ? 'flex' : 'none';
                    } else {
                        nextStepsContent.textContent = 'No next steps provided.';
                        inpatientActions.style.display = 'none';
                    }
                    
                    // Consult Other Teams
                    if (data.sections['Consult Other Teams']) {
                        consultContent.textContent = data.sections['Consult Other Teams'];
                    } else {
                        consultContent.textContent = 'None.';
                    }
                } else {
                    // Fallback if sections are not provided
                    recommendationContent.textContent = 'Please see the complete assessment below:';
                    rationaleContent.textContent = data.response || 'No response received.';
                    nextStepsContent.textContent = '';
                    consultContent.textContent = 'None.';
                    inpatientActions.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                loadingScreen.style.display = 'none';
                alert('There was an error processing your request: ' + error.message);
                // Reset form to be visible again
                clinicalForm.style.display = 'block';
            });
        });
    }
    
    // Handle copy context button
    if (copyContextButton) {
        copyContextButton.addEventListener('click', function() {
            const textToCopy = `Case ID: ${savedCaseId}\n\nClinical Context:\n${savedClinicalContext}\n\nClinical Question:\n${savedClinicalQuestion}`;
            
            // Create a temporary textarea element to copy the text
            const textarea = document.createElement('textarea');
            textarea.value = textToCopy;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            
            // Change button text temporarily to indicate success
            const originalText = copyContextButton.textContent;
            copyContextButton.textContent = 'Copied!';
            setTimeout(() => {
                copyContextButton.textContent = originalText;
            }, 2000);
        });
    }
    
    // Handle edit context button
    if (editContextButton) {
        editContextButton.textContent = 'Edit Context';
        editContextButton.addEventListener('click', function() {
            // Save the last context/question to localStorage
            if (savedClinicalContext && savedClinicalQuestion) {
                localStorage.setItem('editContext', savedClinicalContext);
                localStorage.setItem('editQuestion', savedClinicalQuestion);
            }
            window.location.href = 'context.html';
        });
    }
    
    // On context.html, pre-fill fields from localStorage if present
    if (window.location.pathname.endsWith('context.html')) {
        const context = localStorage.getItem('editContext');
        const question = localStorage.getItem('editQuestion');
        if (context && clinicalContextTextarea) clinicalContextTextarea.value = context;
        if (question && clinicalQuestionTextarea) clinicalQuestionTextarea.value = question;
        // Clear after loading
        localStorage.removeItem('editContext');
        localStorage.removeItem('editQuestion');
    }
}); 