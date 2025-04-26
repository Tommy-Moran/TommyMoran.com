export const ECHO_TYPES = {
    INITIAL: 'initial',
    VALVULAR: 'valvular',
    PROSTHETIC: 'prosthetic',
    INTERVENTION: 'intervention',
    HEART_FAILURE: 'heartfailure',
    CONGENITAL: 'congenital',
    PERICARDIAL: 'pericardial',
    CHEMO: 'chemo',
    PREOP: 'preop',
    OTHER: 'other'
};

export const ECHO_CATEGORIES = [
    {
        echoType: ECHO_TYPES.INITIAL,
        options: [
            { value: 'initialEvaluation', label: 'Initial Cardiovascular Evaluation' },
            { value: 'acuteCondition', label: 'Acute Cardiac Conditions' },
            { value: 'arrhythmia', label: 'Arrhythmias' }
        ]
    },
    {
        echoType: ECHO_TYPES.VALVULAR,
        options: [
            { value: 'aorticValve', label: 'Aortic Valve Disease' },
            { value: 'mitralValve', label: 'Mitral Valve Disease' },
            { value: 'otherValve', label: 'Other Valve Disease' }
        ]
    },
    {
        echoType: ECHO_TYPES.PROSTHETIC,
        options: [
            { value: 'mechanicalValve', label: 'Mechanical Valve' },
            { value: 'bioValve', label: 'Bioprosthetic Valve' },
            { value: 'postSurgery', label: 'Post-Cardiac Surgery' }
        ]
    },
    {
        echoType: ECHO_TYPES.INTERVENTION,
        options: [
            { value: 'preProcedure', label: 'Pre-Procedure Assessment' },
            { value: 'postProcedure', label: 'Post-Procedure Assessment' }
        ]
    },
    {
        echoType: ECHO_TYPES.HEART_FAILURE,
        options: [
            { value: 'newHF', label: 'New Heart Failure' },
            { value: 'knownHF', label: 'Known Heart Failure' },
            { value: 'deviceOptimization', label: 'Device Optimization' }
        ]
    },
    {
        echoType: ECHO_TYPES.CONGENITAL,
        options: [
            { value: 'asd', label: 'Atrial Septal Defect' },
            { value: 'vsd', label: 'Ventricular Septal Defect' },
            { value: 'otherCongenital', label: 'Other Congenital Heart Disease' }
        ]
    },
    {
        echoType: ECHO_TYPES.PERICARDIAL,
        options: [
            { value: 'pericarditis', label: 'Pericarditis' },
            { value: 'pericardialEffusion', label: 'Pericardial Effusion' }
        ]
    },
    {
        echoType: ECHO_TYPES.CHEMO,
        options: [
            { value: 'baseline', label: 'Baseline Assessment' },
            { value: 'surveillance', label: 'Surveillance' }
        ]
    },
    {
        echoType: ECHO_TYPES.PREOP,
        options: [
            { value: 'cardiac', label: 'Cardiac Surgery' },
            { value: 'nonCardiac', label: 'Non-Cardiac Surgery' }
        ]
    },
    {
        echoType: ECHO_TYPES.OTHER,
        options: [
            { value: 'other', label: 'Other Indication' }
        ]
    }
];

export const REFERRING_DOCTOR_TYPES = [
    { value: 'gp', label: 'General Practitioner' },
    { value: 'gpRural', label: 'General Practitioner (Rural - MMM 3 to 7)' },
    { value: 'cardiologist', label: 'Cardiologist' },
    { value: 'nonCardioSpecialist', label: 'Non-Cardiology Specialist' },
    { value: 'consultantPhysician', label: 'Consultant Physician' }
];

export const BILLING_CODES = {
    INITIAL: '55126',
    VALVULAR_SPECIALIST: '55127',
    VALVULAR_GP_RURAL: '55128',
    HEART_FAILURE: '55129'
};

export const TIME_INTERVALS = {
    IMMEDIATE: 'immediate',
    URGENT_24: 'urgent24',
    URGENT_48: 'urgent48',
    PROMPT: 'prompt',
    ROUTINE: 'routine'
};

export const TIME_INTERVAL_LABELS = {
    [TIME_INTERVALS.IMMEDIATE]: 'Immediate (within hours)',
    [TIME_INTERVALS.URGENT_24]: 'Urgent (within 24 hours)',
    [TIME_INTERVALS.URGENT_48]: 'Urgent (within 48 hours)',
    [TIME_INTERVALS.PROMPT]: 'Prompt (within 2-4 weeks)',
    [TIME_INTERVALS.ROUTINE]: 'Routine (2-4 weeks)'
};

export const VALVE_SEVERITY = {
    MILD: 'mild',
    MODERATE: 'moderate',
    SEVERE: 'severe'
};

export const VALVE_SEVERITY_LABELS = {
    [VALVE_SEVERITY.MILD]: 'Mild',
    [VALVE_SEVERITY.MODERATE]: 'Moderate',
    [VALVE_SEVERITY.SEVERE]: 'Severe'
};

export const VALVE_TYPES = {
    AORTIC_STENOSIS: 'aorticStenosis',
    AORTIC_REGURGITATION: 'aorticRegurgitation',
    MITRAL_STENOSIS: 'mitralStenosis',
    MITRAL_REGURGITATION: 'mitralRegurgitation',
    TRICUSPID_REGURGITATION: 'tricuspidRegurgitation',
    TRICUSPID_STENOSIS: 'tricuspidStenosis',
    PULMONIC_REGURGITATION: 'pulmonicRegurgitation',
    PULMONIC_STENOSIS: 'pulmonicStenosis',
    MULTIPLE_VALVE: 'multipleValve'
};

export const VALVE_TYPE_LABELS = {
    [VALVE_TYPES.AORTIC_STENOSIS]: 'Aortic Stenosis (AS)',
    [VALVE_TYPES.AORTIC_REGURGITATION]: 'Aortic Regurgitation (AR)',
    [VALVE_TYPES.MITRAL_STENOSIS]: 'Mitral Stenosis (MS)',
    [VALVE_TYPES.MITRAL_REGURGITATION]: 'Mitral Regurgitation (MR)',
    [VALVE_TYPES.TRICUSPID_REGURGITATION]: 'Tricuspid Regurgitation (TR)',
    [VALVE_TYPES.TRICUSPID_STENOSIS]: 'Tricuspid Stenosis (TS)',
    [VALVE_TYPES.PULMONIC_REGURGITATION]: 'Pulmonic Regurgitation (PR)',
    [VALVE_TYPES.PULMONIC_STENOSIS]: 'Pulmonic Stenosis (PS)',
    [VALVE_TYPES.MULTIPLE_VALVE]: 'Multiple valve disease'
};

export const SURVEILLANCE_INTERVALS = {
    [VALVE_TYPES.AORTIC_STENOSIS]: {
        [VALVE_SEVERITY.MILD]: '3-5 yearly',
        [VALVE_SEVERITY.MODERATE]: '1-2 yearly',
        [VALVE_SEVERITY.SEVERE]: '6-12 monthly'
    },
    [VALVE_TYPES.AORTIC_REGURGITATION]: {
        [VALVE_SEVERITY.MILD]: '3-5 yearly',
        [VALVE_SEVERITY.MODERATE]: '1-2 yearly',
        [VALVE_SEVERITY.SEVERE]: '6-12 monthly'
    },
    [VALVE_TYPES.MITRAL_STENOSIS]: {
        [VALVE_SEVERITY.MILD]: '3-5 yearly',
        [VALVE_SEVERITY.MODERATE]: '1-2 yearly',
        [VALVE_SEVERITY.SEVERE]: 'Annually'
    },
    [VALVE_TYPES.MITRAL_REGURGITATION]: {
        [VALVE_SEVERITY.MILD]: '3-5 yearly',
        [VALVE_SEVERITY.MODERATE]: '1-2 yearly',
        [VALVE_SEVERITY.SEVERE]: '6-12 monthly'
    }
};

export const PATIENT_TYPES = {
    INPATIENT: 'inpatient',
    OUTPATIENT: 'outpatient'
}; 