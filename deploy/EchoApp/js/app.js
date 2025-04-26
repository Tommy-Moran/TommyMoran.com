import { 
    ECHO_TYPES, 
    ECHO_CATEGORIES, 
    REFERRING_DOCTOR_TYPES, 
    BILLING_CODES, 
    TIME_INTERVALS,
    TIME_INTERVAL_LABELS,
    VALVE_SEVERITY,
    VALVE_TYPES,
    SURVEILLANCE_INTERVALS,
    PATIENT_TYPES
} from './constants.js';

import {
    createElement,
    createSelect,
    createFormGroup,
    createButton,
    createButtonContainer,
    createResultContainer,
    createTag,
    createInfoBox,
    formatTimeInterval,
    formatValveSeverity,
    formatValveType,
    validateForm,
    debounce,
    scrollToTop
} from './utils.js';

export class EchoApp {
    constructor() {
        this.formData = {
            patientType: '',
            echoType: '',
            category: '',
            referringDoctor: '',
            timeInterval: '',
            valveSeverity: '',
            valveType: '',
            previousEchoDate: ''
        };
        
        this.initializeApp();
    }
    
    initializeApp() {
        this.setupEventListeners();
        this.renderForm();
        
        // Verify that all required screens exist
        this.checkRequiredScreens();
        
        this.setupNavigationListeners();
        this.setupOtherEventListeners();
    }
    
    checkRequiredScreens() {
        const requiredScreens = [
            'landingScreen',
            'initialAssessmentScreen',
            'mainFormScreen', 
            'indicatedScreen'
        ];
        
        const missingScreens = requiredScreens.filter(screenId => !document.getElementById(screenId));
        
        if (missingScreens.length > 0) {
            console.error('Missing required screens:', missingScreens);
        } else {
            console.log('All required screens found in DOM');
        }
    }
    
    setupEventListeners() {
        const mainElement = document.querySelector('.app-main');
        
        mainElement.addEventListener('change', debounce((event) => {
            if (event.target.matches('select')) {
                this.handleFormChange(event);
            }
        }, 300));
        
        mainElement.addEventListener('click', (event) => {
            if (event.target.matches('button')) {
                this.handleButtonClick(event);
            }
        });
    }
    
    handleFormChange(event) {
        const { name, value } = event.target;
        this.formData[name] = value;
        
        if (name === 'echoType') {
            this.updateCategoryOptions(value);
        }
        
        // We've moved the Next button handling to setupNavigationListeners,
        // so we don't need to handle it here anymore
    }
    
    handleButtonClick(event) {
        const action = event.target.dataset.action;
        
        switch (action) {
            case 'submit':
                this.handleSubmit();
                break;
            case 'reset':
                this.handleReset();
                break;
            case 'print':
                this.handlePrint();
                break;
        }
    }
    
    updateCategoryOptions(echoType) {
        const categorySelect = document.querySelector('select[name="category"]');
        const categories = ECHO_CATEGORIES.find(cat => cat.echoType === echoType)?.options || [];
        
        categorySelect.innerHTML = '';
        categories.forEach(category => {
            const option = createElement('option', {
                value: category.value
            }, [category.label]);
            categorySelect.appendChild(option);
        });
    }
    
    renderForm() {
        const mainElement = document.querySelector('.app-main');
        mainElement.innerHTML = '';
        
        const form = createElement('form', { className: 'echo-form' });
        
        // Patient Type Selection
        const patientTypeSelect = createSelect(
            Object.entries(PATIENT_TYPES).map(([key, value]) => ({ 
                value, 
                label: value === PATIENT_TYPES.INPATIENT ? 'Inpatient' : 'Outpatient' 
            })),
            { name: 'patientType', required: true }
        );
        form.appendChild(createFormGroup('Patient Type', patientTypeSelect));
        
        // Echo Type Selection
        const echoTypeSelect = createSelect(
            Object.entries(ECHO_TYPES).map(([value, label]) => ({ value, label })),
            { name: 'echoType', required: true }
        );
        form.appendChild(createFormGroup('Type of Echocardiogram', echoTypeSelect));
        
        // Category Selection
        const categorySelect = createSelect([], { name: 'category', required: true });
        form.appendChild(createFormGroup('Category', categorySelect));
        
        // Referring Doctor Selection
        const doctorSelect = createSelect(
            REFERRING_DOCTOR_TYPES.map(type => ({ value: type, label: type })),
            { name: 'referringDoctor', required: true }
        );
        form.appendChild(createFormGroup('Referring Doctor Type', doctorSelect));
        
        // Time Interval Selection
        const timeSelect = createSelect(
            Object.entries(TIME_INTERVALS).map(([value, label]) => ({ value, label })),
            { name: 'timeInterval', required: true }
        );
        form.appendChild(createFormGroup('Time Interval', timeSelect));
        
        // Valve Severity Selection
        const severitySelect = createSelect(
            Object.entries(VALVE_SEVERITY).map(([value, label]) => ({ value, label })),
            { name: 'valveSeverity', required: true }
        );
        form.appendChild(createFormGroup('Valve Severity', severitySelect));
        
        // Valve Type Selection
        const valveTypeSelect = createSelect(
            Object.entries(VALVE_TYPES).map(([value, label]) => ({ value, label })),
            { name: 'valveType', required: true }
        );
        form.appendChild(createFormGroup('Valve Type', valveTypeSelect));
        
        // Previous Echo Date
        const dateInput = createElement('input', {
            type: 'date',
            name: 'previousEchoDate',
            required: true
        });
        form.appendChild(createFormGroup('Previous Echo Date', dateInput));
        
        // Buttons
        const buttons = [
            createButton('Submit', () => this.handleSubmit(), 'button-primary'),
            createButton('Reset', () => this.handleReset(), 'button-secondary'),
            createButton('Print', () => this.handlePrint(), 'button-tertiary')
        ];
        
        form.appendChild(createButtonContainer(buttons));
        mainElement.appendChild(form);
    }
    
    handleSubmit() {
        console.log('handleSubmit called with formData:', this.formData);
        
        // First get session data to validate required fields based on the assessment type
        const initialReasonFromSession = sessionStorage.getItem('initialReason');
        const echoTypeFromSession = sessionStorage.getItem('echoType');
        
        console.log('Session data:', { initialReasonFromSession, echoTypeFromSession });
        
        // Set form data based on session data if present
        if (echoTypeFromSession) {
            this.formData.echoType = echoTypeFromSession;
        }
        
        // For initial assessment screens, we don't need the full form validation
        // since we've already collected the necessary data in the specific screens
        if (initialReasonFromSession) {
            console.log('Processing initial assessment with reason:', initialReasonFromSession);
            
            // Skip standard form validation for initial assessments
            // since we'll do specific validation in calculateAppropriateness
            const result = this.calculateAppropriateness();
            console.log('Appropriateness result:', result);
            
            this.displayResult(result);
            scrollToTop();
            return;
        }
        
        // For non-initial assessments, validate the form normally
        const errors = validateForm(this.formData);
        
        if (errors.length > 0) {
            console.log('Form validation errors:', errors);
            this.showErrors(errors);
            return;
        }
        
        const result = this.calculateAppropriateness();
        console.log('Appropriateness result:', result);
        
        this.displayResult(result);
        scrollToTop();
    }
    
    handleReset() {
        this.formData = {
            patientType: '',
            echoType: '',
            category: '',
            referringDoctor: '',
            timeInterval: '',
            valveSeverity: '',
            valveType: '',
            previousEchoDate: ''
        };
        
        this.renderForm();
    }
    
    handlePrint() {
        window.print();
    }
    
    showErrors(errors) {
        const mainElement = document.querySelector('.app-main');
        const errorBox = createInfoBox(
            errors.map(error => `<p>${error}</p>`).join(''),
            'error'
        );
        
        mainElement.insertBefore(errorBox, mainElement.firstChild);
    }
    
    calculateAppropriateness() {
        const {
            patientType,
            echoType,
            category,
            referringDoctor,
            timeInterval,
            valveSeverity,
            valveType,
            previousEchoDate
        } = this.formData;
        
        // Basic appropriateness rules
        let isAppropriate = true;
        let reasons = [];
        
        // First, try to get the assessment data from sessionStorage
        const initialReasonFromSession = sessionStorage.getItem('initialReason');
        
        // Check if this is an arrhythmia assessment
        if (initialReasonFromSession === 'arrhythmia') {
            const arrhythmiaData = sessionStorage.getItem('arrhythmiaData');
            if (arrhythmiaData) {
                const parsedData = JSON.parse(arrhythmiaData);
                const { arrhythmiaType, arrhythmiaStability, completedTests } = parsedData;
                
                // Required tests based on arrhythmia type
                const requiredTests = [];
                
                // ECG is required for all arrhythmias
                requiredTests.push('ECG');
                
                // Additional required tests based on specific arrhythmia types
                if (arrhythmiaType === 'newAF' || arrhythmiaType === 'persistentAF' || arrhythmiaType === 'atrialFlutter') {
                    requiredTests.push('thyroid function tests');
                    requiredTests.push('electrolytes');
                }
                
                if (arrhythmiaType === 'newVT' || arrhythmiaType === 'recurrentVT') {
                    requiredTests.push('electrolytes');
                }
                
                if (arrhythmiaType === 'frequentPVCs') {
                    requiredTests.push('Holter monitoring');
                }
                
                // Check if all required tests have been completed
                const missingTests = requiredTests.filter(test => !completedTests.includes(test));
                
                if (missingTests.length > 0) {
                    isAppropriate = false;
                    reasons.push(`Missing required investigation(s): ${missingTests.join(', ')}`);
                    reasons.push('Please complete the required tests before requesting an echocardiogram.');
                } else {
                    isAppropriate = true;
                    reasons.push('All required investigations have been completed.');
                    
                    // Add specific timeframe and patient type recommendations based on arrhythmia type and stability
                    if (arrhythmiaType === 'newAF') {
                        // Set recommended timeframe based on stability
                        if (arrhythmiaStability === 'unstable') {
                            // Override the timeInterval with a more appropriate value
                            this.formData.timeInterval = TIME_INTERVALS.URGENT_24;
                            reasons.push('New atrial fibrillation with unstable symptoms requires urgent assessment.');
                            // Inpatient is recommended for unstable patients
                            this.formData.patientType = PATIENT_TYPES.INPATIENT;
                        } else if (arrhythmiaStability === 'moderateSymptoms') {
                            this.formData.timeInterval = TIME_INTERVALS.PROMPT;
                            reasons.push('New atrial fibrillation with moderate symptoms should be assessed promptly.');
                            // Can be outpatient if symptoms are controlled
                            this.formData.patientType = PATIENT_TYPES.OUTPATIENT;
                        } else {
                            this.formData.timeInterval = TIME_INTERVALS.ROUTINE;
                            reasons.push('New stable atrial fibrillation can be assessed routinely.');
                            // Stable patients should be outpatient
                            this.formData.patientType = PATIENT_TYPES.OUTPATIENT;
                        }
                    } else if (arrhythmiaType === 'persistentAF' || arrhythmiaType === 'atrialFlutter') {
                        if (arrhythmiaStability === 'unstable') {
                            this.formData.timeInterval = TIME_INTERVALS.URGENT_24;
                            reasons.push('Persistent AF/flutter with unstable symptoms requires urgent assessment.');
                            this.formData.patientType = PATIENT_TYPES.INPATIENT;
                        } else {
                            this.formData.timeInterval = TIME_INTERVALS.ROUTINE;
                            reasons.push('Stable persistent AF/flutter can be assessed routinely.');
                            this.formData.patientType = PATIENT_TYPES.OUTPATIENT;
                        }
                    } else if (arrhythmiaType === 'newVT' || arrhythmiaType === 'recurrentVT') {
                        this.formData.timeInterval = TIME_INTERVALS.URGENT_24;
                        reasons.push('Ventricular tachycardia requires urgent assessment.');
                        this.formData.patientType = PATIENT_TYPES.INPATIENT;
                    } else if (arrhythmiaType === 'avBlock') {
                        this.formData.timeInterval = TIME_INTERVALS.URGENT_48;
                        reasons.push('High-grade AV block requires urgent assessment.');
                        this.formData.patientType = PATIENT_TYPES.INPATIENT;
                    } else {
                        // Default for other arrhythmias
                        if (arrhythmiaStability === 'unstable') {
                            this.formData.timeInterval = TIME_INTERVALS.URGENT_48;
                            reasons.push('Unstable arrhythmia requires urgent assessment.');
                            this.formData.patientType = PATIENT_TYPES.INPATIENT;
                        } else {
                            this.formData.timeInterval = TIME_INTERVALS.ROUTINE;
                            reasons.push('Stable arrhythmia can be assessed routinely.');
                            this.formData.patientType = PATIENT_TYPES.OUTPATIENT;
                        }
                    }
                }
            }
        }
        
        // Check if this is an acute cardiac condition assessment
        else if (initialReasonFromSession === 'heartFailure' || 
                initialReasonFromSession === 'myocardialInfarction' || 
                initialReasonFromSession === 'myocarditis' || 
                initialReasonFromSession === 'takotsubo' || 
                initialReasonFromSession === 'endocarditis' || 
                initialReasonFromSession === 'aorticDisease' || 
                initialReasonFromSession === 'pulmonaryEmbolism' ||
                initialReasonFromSession === 'acuteCondition') {
            
            const acuteData = sessionStorage.getItem('acuteConditionData');
            if (acuteData) {
                const parsedData = JSON.parse(acuteData);
                const { acuteIndication, patientLocation, completedTests } = parsedData;
                
                // Required tests based on acute condition
                const requiredTests = [];
                
                // ECG is required for all acute conditions
                requiredTests.push('ECG');
                
                // Additional required tests based on specific acute conditions
                if (acuteIndication === 'suspectedHF' || acuteIndication === 'newHF' || acuteIndication === 'acuteHF') {
                    requiredTests.push('BNP/NT-proBNP');
                    requiredTests.push('CXR');
                }
                
                if (acuteIndication === 'suspectedAMI' || acuteIndication === 'acuteMI') {
                    requiredTests.push('troponin');
                }
                
                if (acuteIndication === 'suspectedMyocarditis' || acuteIndication === 'confirmedMyocarditis') {
                    requiredTests.push('troponin');
                }
                
                if (acuteIndication === 'suspectedEndocarditis') {
                    requiredTests.push('blood cultures');
                }
                
                // Check if all required tests have been completed
                const missingTests = requiredTests.filter(test => !completedTests.includes(test));
                
                if (missingTests.length > 0) {
                    isAppropriate = false;
                    reasons.push(`Missing required investigation(s): ${missingTests.join(', ')}`);
                    reasons.push('Please complete the required tests before requesting an echocardiogram.');
                } else {
                    isAppropriate = true;
                    reasons.push('All required investigations have been completed.');
                    
                    // Set appropriate timeframe and patient type based on acute condition
                    if (acuteIndication === 'acuteHF' || 
                        acuteIndication === 'acuteMI' || 
                        acuteIndication === 'confirmedMyocarditis' || 
                        acuteIndication === 'suspectedEndocarditis') {
                        this.formData.timeInterval = TIME_INTERVALS.URGENT_24;
                        reasons.push('Acute cardiac condition requires urgent assessment.');
                        this.formData.patientType = PATIENT_TYPES.INPATIENT;
                    } else if (acuteIndication === 'newHF') {
                        this.formData.timeInterval = TIME_INTERVALS.PROMPT;
                        reasons.push('New heart failure should be assessed promptly.');
                        // Use patient location to determine inpatient/outpatient
                        this.formData.patientType = patientLocation === 'inpatient' ? 
                            PATIENT_TYPES.INPATIENT : PATIENT_TYPES.OUTPATIENT;
                    } else {
                        // Default for other acute conditions
                        this.formData.timeInterval = TIME_INTERVALS.URGENT_48;
                        reasons.push('Acute cardiac condition requires prompt assessment.');
                        this.formData.patientType = patientLocation === 'inpatient' ? 
                            PATIENT_TYPES.INPATIENT : PATIENT_TYPES.OUTPATIENT;
                    }
                }
            }
        }
        
        // Check time interval for follow-up echos
        if (echoType !== 'initial' && timeInterval === TIME_INTERVALS.URGENT_24) {
            isAppropriate = true;
            reasons.push('Urgent echocardiogram is always appropriate');
        } else if (echoType !== 'initial') {
            // Check surveillance intervals for valve conditions
            const recommendedInterval = SURVEILLANCE_INTERVALS[valveType]?.[valveSeverity];
            if (recommendedInterval) {
                const previousDate = new Date(previousEchoDate);
                const currentDate = new Date();
                const monthsSinceLastEcho = (currentDate - previousDate) / (1000 * 60 * 60 * 24 * 30);
                
                if (monthsSinceLastEcho < recommendedInterval) {
                    isAppropriate = false;
                    reasons.push(`Previous echo was too recent. Recommended interval is ${recommendedInterval} months`);
                }
            }
        }
        
        return {
            isAppropriate,
            reasons,
            patientType: this.formData.patientType, // Use the updated patientType
            billingCode: BILLING_CODES[echoType],
            timeInterval: formatTimeInterval(this.formData.timeInterval), // Use the updated timeInterval
            valveSeverity: formatValveSeverity(valveSeverity),
            valveType: formatValveType(valveType)
        };
    }
    
    displayResult(result) {
        const { isAppropriate, reasons, patientType, billingCode, timeInterval, valveSeverity, valveType } = result;
        
        // If window.showScreen is available, navigate to a dedicated results screen
        if (typeof window.showScreen === 'function') {
            if (isAppropriate) {
                // Populate the indicated screen for appropriate requests
                const indicatedContentElement = document.getElementById('indicatedContent');
                if (indicatedContentElement) {
                    const reasonsListHTML = reasons.map(reason => `<li>${reason}</li>`).join('');
                    indicatedContentElement.innerHTML = `<ul>${reasonsListHTML}</ul>`;
                }
                
                // Set the timeframe
                const timeframeElement = document.getElementById('indicatedTimeframe');
                if (timeframeElement) {
                    timeframeElement.innerHTML = `
                        <p><strong>Recommended Timeframe:</strong> ${timeInterval || 'Based on clinical urgency'}</p>
                        <p><strong>Patient Type:</strong> This is recommended as an <strong>${patientType}</strong> test.</p>
                    `;
                    
                    // Get the raw timeInterval value before formatting by removing labels
                    const rawTimeInterval = Object.keys(TIME_INTERVAL_LABELS).find(
                        key => TIME_INTERVAL_LABELS[key] === timeInterval
                    ) || '';
                    
                    // Add guidance for timing based on clinical urgency
                    if (rawTimeInterval === TIME_INTERVALS.IMMEDIATE || 
                        rawTimeInterval === TIME_INTERVALS.URGENT_24 || 
                        rawTimeInterval === TIME_INTERVALS.URGENT_48) {
                        timeframeElement.innerHTML += `
                            <p><strong>Note:</strong> For urgent/immediate tests, inpatient assessment is typically recommended.</p>
                        `;
                    } else if (rawTimeInterval === TIME_INTERVALS.ROUTINE || 
                               rawTimeInterval === TIME_INTERVALS.PROMPT) {
                        timeframeElement.innerHTML += `
                            <p><strong>Note:</strong> For routine/prompt tests, outpatient assessment is typically appropriate.</p>
                        `;
                    }
                }
                
                // Also populate the separate results screen if it exists
                const timeframeValueElement = document.getElementById('timeframeValue');
                const patientTypeValueElement = document.getElementById('patientTypeValue');
                const timeframeNoteElement = document.getElementById('timeframeNote');
                
                if (timeframeValueElement) {
                    timeframeValueElement.textContent = timeInterval || 'Based on clinical urgency';
                }
                
                if (patientTypeValueElement) {
                    patientTypeValueElement.textContent = patientType;
                }
                
                if (timeframeNoteElement) {
                    // Get the raw timeInterval value before formatting by removing labels
                    const rawTimeInterval = Object.keys(TIME_INTERVAL_LABELS).find(
                        key => TIME_INTERVAL_LABELS[key] === timeInterval
                    ) || '';
                    
                    if (rawTimeInterval === TIME_INTERVALS.IMMEDIATE || 
                        rawTimeInterval === TIME_INTERVALS.URGENT_24 || 
                        rawTimeInterval === TIME_INTERVALS.URGENT_48) {
                        timeframeNoteElement.innerHTML = '<strong>Note:</strong> For urgent/immediate tests, inpatient assessment is typically recommended.';
                    } else if (rawTimeInterval === TIME_INTERVALS.ROUTINE || 
                               rawTimeInterval === TIME_INTERVALS.PROMPT) {
                        timeframeNoteElement.innerHTML = '<strong>Note:</strong> For routine/prompt tests, outpatient assessment is typically appropriate.';
                    } else {
                        timeframeNoteElement.innerHTML = '';
                    }
                }
                
                // Set up patient type specific information
                const nextStepsElement = document.getElementById('nextSteps');
                if (nextStepsElement) {
                    if (patientType === PATIENT_TYPES.OUTPATIENT) {
                        // For outpatients (e.g., GP referrals)
                        nextStepsElement.innerHTML = `
                            <p>For outpatient requests, please complete the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a>.</p>
                        `;
                    } else {
                        // For inpatients
                        nextStepsElement.innerHTML = `
                            <p>For inpatients, you have the following options:</p>
                            <ul>
                                <li>Complete the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a>.</li>
                            </ul>
                        `;
                        
                        // Get the raw timeInterval value before formatting by removing labels
                        const rawTimeInterval = Object.keys(TIME_INTERVAL_LABELS).find(
                            key => TIME_INTERVAL_LABELS[key] === timeInterval
                        ) || '';
                        
                        // For inpatients where an outpatient assessment would be appropriate
                        if (rawTimeInterval === TIME_INTERVALS.ROUTINE || 
                            rawTimeInterval === TIME_INTERVALS.PROMPT) {
                            nextStepsElement.innerHTML += `
                                <p>If this is a current inpatient but an outpatient test would be appropriate (based on timing and clinical status), consider:</p>
                                <ul>
                                    <li>Completing the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a> for outpatient follow-up.</li>
                                    <li>Organizing an external echo through <a href="https://cardiotas.com.au/" target="_blank">CardioTas</a> or <a href="https://hobartheart.com.au/" target="_blank">Hobart Heart Centre</a> that allow bulk billing for public patients.</li>
                                </ul>
                            `;
                        }
                    }
                }
                
                // Show the indicated screen
                window.showScreen('indicatedScreen');
            } else {
                // Populate the not indicated screen for inappropriate requests
                const notIndicatedContentElement = document.getElementById('notIndicatedContent');
                if (notIndicatedContentElement) {
                    const reasonsListHTML = reasons.map(reason => `<li>${reason}</li>`).join('');
                    notIndicatedContentElement.innerHTML = `<ul>${reasonsListHTML}</ul>`;
                }
                
                // Set alternative tests recommendation
                const alternativeTestsElement = document.getElementById('alternativeTests');
                if (alternativeTestsElement) {
                    // Get the missing tests from reasons (assuming they're in the first reason)
                    const missingTestsMatch = reasons[0]?.match(/Missing required investigation\(s\): (.+)/);
                    if (missingTestsMatch && missingTestsMatch[1]) {
                        const missingTests = missingTestsMatch[1];
                        alternativeTestsElement.innerHTML = `
                            <p>Please complete the following tests before requesting an echocardiogram:</p>
                            <ul>
                                ${missingTests.split(', ').map(test => `<li>${test}</li>`).join('')}
                            </ul>
                        `;
                    } else {
                        alternativeTestsElement.innerHTML = `
                            <p>Consider alternative diagnostic approaches or consult with a cardiologist.</p>
                        `;
                    }
                }
                
                // Set reconsider echo guidance
                const reconsiderEchoElement = document.getElementById('reconsiderEcho');
                if (reconsiderEchoElement) {
                    reconsiderEchoElement.innerHTML = `
                        <p>Reconsider requesting an echocardiogram after completing the required tests or if the patient's clinical status changes significantly.</p>
                    `;
                }
                
                // Show the not indicated screen
                window.showScreen('notIndicatedScreen');
            }
        } else {
            // Fallback to displaying results in the main form
            this._displayResultInAppMain(result);
        }
    }
    
    _displayResultInAppMain(result) {
        const { isAppropriate, reasons, patientType, billingCode, timeInterval, valveSeverity, valveType } = result;
        
        // Clear previous results
        const resultContainer = document.querySelector('.app-main');
        resultContainer.innerHTML = '';
        
        // Create the result container
        const resultDiv = document.createElement('div');
        resultDiv.classList.add('result-container');
        resultDiv.classList.add(isAppropriate ? 'result-appropriate' : 'result-inappropriate');
        
        // Add the heading
        const heading = document.createElement('h3');
        heading.textContent = isAppropriate ? 
            'Based on the information provided, an echocardiogram is indicated.' : 
            'Based on the information provided, an echocardiogram is not indicated at this time.';
        resultDiv.appendChild(heading);
        
        // Add the reasons
        const reasonsList = document.createElement('ul');
        reasons.forEach(reason => {
            const reasonItem = document.createElement('li');
            reasonItem.textContent = reason;
            reasonsList.appendChild(reasonItem);
        });
        resultDiv.appendChild(reasonsList);
        
        // Append to the container
        resultContainer.appendChild(resultDiv);
        
        // If appropriate, add the timeframe and billing information
        if (isAppropriate) {
            // Add timeframe information
            const timeframeDiv = document.createElement('div');
            timeframeDiv.classList.add('form-group');
            
            const timeframeHeading = document.createElement('h3');
            timeframeHeading.textContent = 'Recommended Timeframe';
            timeframeDiv.appendChild(timeframeHeading);
            
            const timeframeContent = document.createElement('div');
            timeframeContent.classList.add('info-box');
            timeframeContent.innerHTML = `
                <p><strong>Recommended Timeframe:</strong> ${timeInterval || 'Based on clinical urgency'}</p>
                <p><strong>Patient Type:</strong> This is recommended as an <strong>${patientType}</strong> test.</p>
            `;
            
            // Get the raw timeInterval value before formatting
            const rawTimeInterval = Object.keys(TIME_INTERVAL_LABELS).find(
                key => TIME_INTERVAL_LABELS[key] === timeInterval
            ) || '';
            
            // Add guidance for timing based on clinical urgency
            if (rawTimeInterval === TIME_INTERVALS.IMMEDIATE || 
                rawTimeInterval === TIME_INTERVALS.URGENT_24 || 
                rawTimeInterval === TIME_INTERVALS.URGENT_48) {
                timeframeContent.innerHTML += `
                    <p><strong>Note:</strong> For urgent/immediate tests, inpatient assessment is typically recommended.</p>
                `;
            } else if (rawTimeInterval === TIME_INTERVALS.ROUTINE || 
                      rawTimeInterval === TIME_INTERVALS.PROMPT) {
                timeframeContent.innerHTML += `
                    <p><strong>Note:</strong> For routine/prompt tests, outpatient assessment is typically appropriate.</p>
                `;
            }
            
            timeframeDiv.appendChild(timeframeContent);
            resultDiv.appendChild(timeframeDiv);
            
            // Add billing information
            const billingDiv = document.createElement('div');
            billingDiv.classList.add('form-group');
            
            const billingHeading = document.createElement('h3');
            billingHeading.textContent = 'Billing Information';
            billingDiv.appendChild(billingHeading);
            
            const billingContent = document.createElement('div');
            billingContent.classList.add('info-box');
            billingContent.innerHTML = `
                <p><strong>Medicare Item Number:</strong> ${billingCode || 'N/A'}</p>
            `;
            billingDiv.appendChild(billingContent);
            resultDiv.appendChild(billingDiv);
            
            // Add next steps information
            const nextStepsDiv = document.createElement('div');
            nextStepsDiv.classList.add('form-group');
            
            const nextStepsHeading = document.createElement('h3');
            nextStepsHeading.textContent = 'Next Steps';
            nextStepsDiv.appendChild(nextStepsHeading);
            
            const nextStepsContent = document.createElement('div');
            nextStepsContent.classList.add('info-box');
            
            if (patientType === PATIENT_TYPES.OUTPATIENT) {
                // For outpatients (e.g., GP referrals)
                nextStepsContent.innerHTML = `
                    <p>For outpatient requests, please complete the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a>.</p>
                `;
            } else {
                // For inpatients
                nextStepsContent.innerHTML = `
                    <p>For inpatients, you have the following options:</p>
                    <ul>
                        <li>Complete the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a>.</li>
                    </ul>
                `;
                
                // For inpatients where an outpatient assessment would be appropriate
                if (rawTimeInterval === TIME_INTERVALS.ROUTINE || 
                    rawTimeInterval === TIME_INTERVALS.PROMPT) {
                    nextStepsContent.innerHTML += `
                        <p>If this is a current inpatient but an outpatient test would be appropriate (based on timing and clinical status), consider:</p>
                        <ul>
                            <li>Completing the <a href="https://www.dhhs.tas.gov.au/hospital/royal-hobart-hospital/forms/echo-request-form" target="_blank">RHH Echo Request Form</a> for outpatient follow-up.</li>
                            <li>Organizing an external echo through <a href="https://cardiotas.com.au/" target="_blank">CardioTas</a> or <a href="https://hobartheart.com.au/" target="_blank">Hobart Heart Centre</a> that allow bulk billing for public patients.</li>
                        </ul>
                    `;
                }
            }
            
            nextStepsDiv.appendChild(nextStepsContent);
            resultDiv.appendChild(nextStepsDiv);
        } else {
            // Add alternative tests recommendation
            const alternativeTestsDiv = document.createElement('div');
            alternativeTestsDiv.classList.add('form-group');
            
            const alternativeTestsHeading = document.createElement('h3');
            alternativeTestsHeading.textContent = 'Required Tests';
            alternativeTestsDiv.appendChild(alternativeTestsHeading);
            
            const alternativeTestsContent = document.createElement('div');
            alternativeTestsContent.classList.add('info-box');
            
            // Get the missing tests from reasons (assuming they're in the first reason)
            const missingTestsMatch = reasons[0]?.match(/Missing required investigation\(s\): (.+)/);
            if (missingTestsMatch && missingTestsMatch[1]) {
                const missingTests = missingTestsMatch[1];
                alternativeTestsContent.innerHTML = `
                    <p>Please complete the following tests before requesting an echocardiogram:</p>
                    <ul>
                        ${missingTests.split(', ').map(test => `<li>${test}</li>`).join('')}
                    </ul>
                `;
            } else {
                alternativeTestsContent.innerHTML = `
                    <p>Consider alternative diagnostic approaches or consult with a cardiologist.</p>
                `;
            }
            
            alternativeTestsDiv.appendChild(alternativeTestsContent);
            resultDiv.appendChild(alternativeTestsDiv);
        }
    }

    navigateToMainForm() {
        console.log('Navigating to main form with form data:', this.formData);
        
        // Show the main form screen with the appropriate fields based on the echo type
        this.renderForm();
        
        // Ensure form fields are populated with current values
        const selects = document.querySelectorAll('.app-main select');
        selects.forEach(select => {
            const name = select.getAttribute('name');
            if (name && this.formData[name]) {
                select.value = this.formData[name];
            }
        });
        
        // Now show the screen
        this.navigateTo('mainFormScreen');
    }
    
    setupNavigationListeners() {
        console.log('Setting up navigation listeners');
        
        // Register all back button click handlers with a consistent approach
        const backButtons = document.querySelectorAll('.back-btn, [id^="backFrom"]');
        backButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetScreen = button.dataset.target;
                if (targetScreen) {
                    this.navigateTo(targetScreen);
                } else if (button.id === 'backFromInitial') {
                    this.navigateTo('landingScreen');
                } else if (button.id === 'backFromMain') {
                    this.handleBackFromMain();
                } else {
                    console.warn('Back button has no target:', button);
                    this.navigateTo('landingScreen'); // Default fallback
                }
            });
        });

        // Handle all next button clicks
        const nextButtons = document.querySelectorAll('[id^="nextFrom"], [id^="process"]');
        nextButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetScreen = button.dataset.target;
                
                if (targetScreen) {
                    this.navigateTo(targetScreen);
                } else if (button.id === 'nextFromLanding') {
                    this.handleNextFromLanding();
                } else if (button.id === 'nextFromInitial') {
                    this.handleNextFromInitial();
                } else if (button.id.startsWith('process')) {
                    // These are special process buttons that have their own handlers
                    // Don't override their existing functionality
                    console.log('Process button clicked:', button.id);
                } else {
                    console.warn('Next button has no target:', button);
                }
            });
        });

        // Handle submit button on the main form
        const submitFormBtn = document.getElementById('submitForm');
        if (submitFormBtn) {
            submitFormBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleSubmit();
            });
        }
    }

    // Add these new helper methods for navigation
    navigateTo(screenId) {
        if (!screenId) {
            console.error('No screen ID provided for navigation');
            return;
        }
        
        console.log('Navigating to screen:', screenId);
        
        // Verify the target screen exists
        const targetScreen = document.getElementById(screenId);
        if (!targetScreen) {
            console.error(`Target screen "${screenId}" not found in the DOM`);
            return;
        }
        
        // Use the showScreen function defined in the global scope
        if (typeof window.showScreen === 'function') {
            console.log('Using window.showScreen to navigate');
            window.showScreen(screenId);
        } else {
            console.error('window.showScreen function not available, using fallback');
            
            // Fallback implementation
            document.querySelectorAll('.screen').forEach(screen => {
                screen.classList.remove('active');
            });
            
            targetScreen.classList.add('active');
            window.scrollTo(0, 0);
            console.log('Screen displayed:', screenId);
        }
    }
    
    handleNextFromLanding() {
        const echoTypeElement = document.getElementById('echoType');
        const patientTypeElement = document.getElementById('patientType');
        
        console.log('Elements found?', { 
            echoTypeElement: !!echoTypeElement, 
            patientTypeElement: !!patientTypeElement 
        });
        
        const echoType = echoTypeElement?.value || '';
        const patientType = patientTypeElement?.value || '';
        
        console.log('handleNextFromLanding called with values:', { echoType, patientType });
        
        if (!echoType || !patientType) {
            console.error('Missing required values for navigation');
            alert('Please select both patient type and echo type.');
            return;
        }
        
        // Store these values in formData and sessionStorage
        this.formData.echoType = echoType;
        this.formData.patientType = patientType;
        
        sessionStorage.setItem('echoType', echoType);
        sessionStorage.setItem('patientType', patientType);
        
        console.log('Navigating based on echo type:', echoType);
        
        if (echoType === 'initial') {
            console.log('Navigating to initial assessment screen');
            this.navigateTo('initialAssessmentScreen');
        } else {
            console.log('Navigating to main form');
            // For other echo types, navigate directly to main form
            this.navigateToMainForm();
        }
    }
    
    handleNextFromInitial() {
        const initialReason = document.getElementById('initialReason')?.value;
        
        if (!initialReason) {
            console.error('No initial reason selected');
            return;
        }
        
        sessionStorage.setItem('initialReason', initialReason);
        
        // Navigate based on the initial reason
        if (initialReason === 'arrhythmia') {
            this.navigateTo('arrhythmiaScreen');
        } else if (['heartFailure', 'myocardialInfarction', 'myocarditis', 'takotsubo', 
                    'endocarditis', 'aorticDisease', 'pulmonaryEmbolism'].includes(initialReason)) {
            this.navigateTo('acuteScreen');
        } else if (initialReason === 'valvularDisease') {
            this.navigateTo('valvularScreen');
        } else {
            // For other initial reasons, navigate to the generic initial screen
            this.navigateTo('initialScreen');
        }
    }
    
    handleBackFromMain() {
        // Check if we came from a specific assessment screen
        const echoType = sessionStorage.getItem('echoType');
        const initialReason = sessionStorage.getItem('initialReason');
        
        if (echoType === 'initial') {
            if (initialReason === 'arrhythmia') {
                this.navigateTo('arrhythmiaScreen');
            } else if (['heartFailure', 'myocardialInfarction', 'myocarditis', 
                       'takotsubo', 'endocarditis', 'aorticDisease', 
                       'pulmonaryEmbolism'].includes(initialReason)) {
                this.navigateTo('acuteScreen');
            } else if (initialReason === 'valvularDisease') {
                this.navigateTo('valvularScreen');
            } else {
                this.navigateTo('initialAssessmentScreen');
            }
        } else {
            this.navigateTo('landingScreen');
        }
    }

    setupOtherEventListeners() {
        console.log('Setting up other event listeners');
        
        // Initialize the tabs on the guidelines screen
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.dataset.tab;
                
                // Make the clicked tab active
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Show the corresponding tab content
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                const tabContent = document.getElementById(tabId + 'Tab');
                if (tabContent) {
                    tabContent.classList.add('active');
                } else {
                    console.error('Tab content not found for', tabId);
                }
            });
        });
        
        // Handle BNP checkbox to show/hide the BNP result field
        const bnpCheckbox = document.getElementById('priorBNP');
        const bnpResultGroup = document.getElementById('bnpResultGroup');
        
        if (bnpCheckbox && bnpResultGroup) {
            bnpCheckbox.addEventListener('change', () => {
                bnpResultGroup.style.display = bnpCheckbox.checked ? 'block' : 'none';
                const bnpResult = document.getElementById('bnpResult');
                if (bnpResult) {
                    bnpResult.required = bnpCheckbox.checked;
                }
            });
        }
    }
}

// Initialize the application
let app; // Create a global reference to the app instance

document.addEventListener('DOMContentLoaded', () => {
    // Make sure window.showScreen is available
    if (typeof window.showScreen !== 'function') {
        window.showScreen = function(screenId) {
            // Hide all screens
            document.querySelectorAll('.screen').forEach(screen => {
                screen.classList.remove('active');
            });
            
            // Show the target screen
            const targetScreen = document.getElementById(screenId);
            if (targetScreen) {
                targetScreen.classList.add('active');
                // Scroll to top
                window.scrollTo(0, 0);
                console.log('Showing screen:', screenId); // Debug log
            } else {
                console.error('Screen not found:', screenId); // Error log
            }
        };
    }
    
    console.log('Creating app instance...');
    app = new EchoApp(); // Assign the instance to the global variable
    window.app = app; // Explicitly expose the app to the global window object
    console.log('Echo app initialized successfully, window.app =', !!window.app);
    
    // Explicitly show the landing screen to ensure we start at the right place
    app.navigateTo('landingScreen');

    // ... existing event listeners ...
}); 