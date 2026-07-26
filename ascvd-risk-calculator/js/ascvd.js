(function () {
    'use strict';

    // ── Element refs ───────────────────────────────────────
    const uploadZone = document.getElementById('upload-zone');
    const pdfInput = document.getElementById('pdf-input');
    const fileNameEl = document.getElementById('file-name');
    const uploadStatus = document.getElementById('upload-status');

    const form = document.getElementById('risk-form');
    const ageInput = document.getElementById('age');
    const sbpInput = document.getElementById('sbp');
    const tcInput = document.getElementById('tc');
    const hdlInput = document.getElementById('hdl');
    const ldlInput = document.getElementById('ldl');
    const formError = document.getElementById('form-error');

    const resultsCard = document.getElementById('results-card');
    const riskNumberEl = document.getElementById('risk-number');
    const riskCategoryPill = document.getElementById('risk-category-pill');
    const riskInterpretationText = document.getElementById('risk-interpretation-text');
    const riskMarker = document.getElementById('risk-marker');
    const rangeWarning = document.getElementById('range-warning');
    const thresholdRows = document.querySelectorAll('#threshold-tbody tr');

    // ── Segmented toggle state ─────────────────────────────
    const toggles = {
        sex: { el: document.getElementById('sex-toggle'), value: null },
        race: { el: document.getElementById('race-toggle'), value: 'white' },
        treated: { el: document.getElementById('treated-toggle'), value: 'no' },
        smoker: { el: document.getElementById('smoker-toggle'), value: 'no' },
        diabetes: { el: document.getElementById('diabetes-toggle'), value: 'no' },
    };

    Object.keys(toggles).forEach(function (key) {
        const group = toggles[key];
        group.el.querySelectorAll('button').forEach(function (btn) {
            btn.addEventListener('click', function () {
                group.el.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                group.value = btn.dataset.value;
                group.el.classList.remove('auto-filled', 'needs-review');
            });
        });
    });

    function setToggle(key, value, autoFilled) {
        const group = toggles[key];
        if (value === null || value === undefined) return;
        group.el.querySelectorAll('button').forEach(function (b) {
            b.classList.toggle('active', b.dataset.value === value);
        });
        group.value = value;
        group.el.classList.remove('auto-filled', 'needs-review');
        if (autoFilled) group.el.classList.add('auto-filled');
    }

    function flagToggleReview(key) {
        toggles[key].el.classList.add('needs-review');
    }

    // ── Upload / drag-drop ──────────────────────────────────
    uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });
    uploadZone.addEventListener('dragleave', function () { uploadZone.classList.remove('drag-over'); });
    uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') handleFile(file);
        else showUploadStatus('error', 'Please drop a PDF file.');
    });
    pdfInput.addEventListener('change', function () {
        if (pdfInput.files[0]) handleFile(pdfInput.files[0]);
    });

    function handleFile(file) {
        fileNameEl.textContent = file.name;
        fileNameEl.style.display = 'block';
        extractFromPdf(file);
    }

    function showUploadStatus(kind, message) {
        uploadStatus.className = 'upload-status visible ' + kind;
        uploadStatus.textContent = message;
    }

    async function extractFromPdf(file) {
        showUploadStatus('loading', 'Reading referral PDF…');

        const formData = new FormData();
        formData.append('pdf', file);

        try {
            const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            const apiUrl = isLocal
                ? '/ascvd-risk-calculator/extract'
                : 'https://tommymoran-com-chatbot.onrender.com/ascvd-risk-calculator/extract';

            const resp = await fetch(apiUrl, { method: 'POST', body: formData });
            const data = await resp.json();

            if (!resp.ok || data.error) {
                showUploadStatus('error', data.error || 'Could not process this PDF.');
                return;
            }

            applyExtractedFields(data.fields, data.found_count);
        } catch (err) {
            showUploadStatus('error', 'Network error — please check the server is running, or enter values manually below.');
        }
    }

    function setNumericField(input, fieldData) {
        input.classList.remove('auto-filled', 'needs-review');
        if (fieldData && fieldData.found && fieldData.value !== null && fieldData.value !== undefined) {
            input.value = fieldData.value;
            input.classList.add('auto-filled');
        }
    }

    function applyExtractedFields(fields, foundCount) {
        setNumericField(ageInput, fields.age);
        setNumericField(sbpInput, fields.systolic_bp);
        setNumericField(tcInput, fields.total_chol_mmol);
        setNumericField(hdlInput, fields.hdl_chol_mmol);
        setNumericField(ldlInput, fields.ldl_chol_mmol);

        if (fields.sex && fields.sex.found) {
            setToggle('sex', fields.sex.value, true);
        }
        if (fields.smoker && fields.smoker.found) {
            setToggle('smoker', fields.smoker.value ? 'yes' : 'no', true);
        }
        if (fields.diabetes && fields.diabetes.found) {
            setToggle('diabetes', fields.diabetes.value ? 'yes' : 'no', true);
        }
        if (fields.on_bp_treatment && fields.on_bp_treatment.found) {
            setToggle('treated', fields.on_bp_treatment.value ? 'yes' : 'no', true);
        }

        // Fields the calculation needs that could not be found are flagged for manual entry.
        const missing = [];
        if (!fields.age || !fields.age.found) missing.push('age');
        if (!fields.sex || !fields.sex.found) { missing.push('sex'); flagToggleReview('sex'); }
        if (!fields.systolic_bp || !fields.systolic_bp.found) missing.push('systolic BP');
        if (!fields.total_chol_mmol || !fields.total_chol_mmol.found) missing.push('total cholesterol');
        if (!fields.hdl_chol_mmol || !fields.hdl_chol_mmol.found) missing.push('HDL cholesterol');

        if (missing.length === 0) {
            showUploadStatus('success', 'Extracted ' + foundCount + ' field(s) from the referral. Review the highlighted values below, then calculate.');
        } else {
            showUploadStatus('warn', 'Extracted what we could (' + foundCount + ' field(s)). Please fill in: ' + missing.join(', ') + '.');
        }
    }

    // ── Risk calculation (2013 ACC/AHA Pooled Cohort Equations) ──
    // Coefficients per Goff DC et al., Circulation 2014;129(25 Suppl 2):S49-S73, Table A.
    const COEFF = {
        female_white: {
            lnAge: -29.799, lnAgeSq: 4.884, lnTC: 13.540, lnAgeLnTC: -3.114,
            lnHDL: -13.578, lnAgeLnHDL: 3.149,
            lnSBPTreated: 2.019, lnSBPUntreated: 1.957,
            smoker: 7.574, lnAgeSmoker: -1.665, diabetes: 0.661,
            mean: -29.1817, s0: 0.96652,
        },
        female_black: {
            lnAge: 17.114, lnTC: 0.940,
            lnHDL: -18.920, lnAgeLnHDL: 4.475,
            lnSBPTreated: 29.291, lnAgeLnSBPTreated: -6.432,
            lnSBPUntreated: 27.820, lnAgeLnSBPUntreated: -6.087,
            smoker: 0.691, diabetes: 0.874,
            mean: 86.6081, s0: 0.95334,
        },
        male_white: {
            lnAge: 12.344, lnTC: 11.853, lnAgeLnTC: -2.664,
            lnHDL: -7.990, lnAgeLnHDL: 1.769,
            lnSBPTreated: 1.797, lnSBPUntreated: 1.764,
            smoker: 7.837, lnAgeSmoker: -1.795, diabetes: 0.658,
            mean: 61.1816, s0: 0.91436,
        },
        male_black: {
            lnAge: 2.469, lnTC: 0.302, lnHDL: -0.307,
            lnSBPTreated: 1.916, lnSBPUntreated: 1.809,
            smoker: 0.549, diabetes: 0.645,
            mean: 19.5425, s0: 0.89536,
        },
    };

    const MMOL_TO_MGDL = 38.67;

    function calculateRisk(input) {
        const key = input.sex + '_' + input.race;
        const c = COEFF[key];

        const tcMgdl = input.tcMmol * MMOL_TO_MGDL;
        const hdlMgdl = input.hdlMmol * MMOL_TO_MGDL;

        const lnAge = Math.log(input.age);
        const lnTC = Math.log(tcMgdl);
        const lnHDL = Math.log(hdlMgdl);
        const lnSBP = Math.log(input.sbp);
        const smoker = input.smoker ? 1 : 0;
        const diabetes = input.diabetes ? 1 : 0;

        let sum = 0;
        sum += (c.lnAge || 0) * lnAge;
        sum += (c.lnAgeSq || 0) * lnAge * lnAge;
        sum += (c.lnTC || 0) * lnTC;
        sum += (c.lnAgeLnTC || 0) * lnAge * lnTC;
        sum += (c.lnHDL || 0) * lnHDL;
        sum += (c.lnAgeLnHDL || 0) * lnAge * lnHDL;

        if (input.treated) {
            sum += (c.lnSBPTreated || 0) * lnSBP;
            sum += (c.lnAgeLnSBPTreated || 0) * lnAge * lnSBP;
        } else {
            sum += (c.lnSBPUntreated || 0) * lnSBP;
            sum += (c.lnAgeLnSBPUntreated || 0) * lnAge * lnSBP;
        }

        sum += (c.smoker || 0) * smoker;
        sum += (c.lnAgeSmoker || 0) * lnAge * smoker;
        sum += (c.diabetes || 0) * diabetes;

        const risk = 1 - Math.pow(c.s0, Math.exp(sum - c.mean));
        return risk * 100;
    }

    function categorize(riskPct) {
        if (riskPct < 5) return { key: 'low', label: 'Low risk', color: '#16a34a', tint: '#eafaf0' };
        if (riskPct < 7.5) return { key: 'borderline', label: 'Borderline risk', color: '#ca8a04', tint: '#fdf6e3' };
        if (riskPct < 20) return { key: 'intermediate', label: 'Intermediate risk', color: '#ea580c', tint: '#fdefe6' };
        return { key: 'high', label: 'High risk', color: '#dc2626', tint: '#fdecec' };
    }

    // Piecewise mapping of an actual risk% onto the marker's position (0-100)
    // along the meter, whose four coloured segments are drawn at fixed widths
    // (20% / 15% / 35% / 30%) rather than proportional to the risk scale.
    function markerPosition(riskPct) {
        const r = Math.max(0, riskPct);
        if (r <= 5) return (r / 5) * 20;
        if (r <= 7.5) return 20 + ((r - 5) / 2.5) * 15;
        if (r <= 20) return 35 + ((r - 7.5) / 12.5) * 35;
        const capped = Math.min(r, 50);
        return 70 + ((capped - 20) / 30) * 30;
    }

    function interpretationText(riskPct, cat) {
        const pctStr = riskPct.toFixed(1) + '%';
        const base = 'Estimated 10-year risk of a first ASCVD event (myocardial infarction, stroke, or coronary death) is ' + pctStr + '.';
        const guidance = {
            low: ' Guideline emphasis is on lifestyle measures; a statin is not routinely indicated on risk grounds alone.',
            borderline: ' Consider risk-enhancing factors (e.g. family history, CRP, coronary calcium score) to guide a statin discussion.',
            intermediate: ' A moderate-intensity statin is reasonable per ACC/AHA guidance; risk-enhancing factors or a coronary calcium score can help refine the decision.',
            high: ' A high-intensity statin is reasonable per ACC/AHA guidance, alongside aggressive risk-factor modification.',
        };
        return base + (guidance[cat.key] || '');
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        formError.classList.remove('visible');
        rangeWarning.classList.remove('visible');

        const age = parseFloat(ageInput.value);
        const sbp = parseFloat(sbpInput.value);
        const tcMmol = parseFloat(tcInput.value);
        const hdlMmol = parseFloat(hdlInput.value);
        const sex = toggles.sex.value;
        const race = toggles.race.value;
        const treated = toggles.treated.value === 'yes';
        const smoker = toggles.smoker.value === 'yes';
        const diabetes = toggles.diabetes.value === 'yes';

        const missing = [];
        if (!Number.isFinite(age)) missing.push('age');
        if (!sex) missing.push('sex');
        if (!Number.isFinite(sbp)) missing.push('systolic BP');
        if (!Number.isFinite(tcMmol)) missing.push('total cholesterol');
        if (!Number.isFinite(hdlMmol)) missing.push('HDL cholesterol');

        if (missing.length > 0) {
            formError.textContent = 'Please provide: ' + missing.join(', ') + '.';
            formError.classList.add('visible');
            resultsCard.classList.remove('visible');
            return;
        }

        if (age < 40 || age > 79) {
            formError.textContent = 'The Pooled Cohort Equations are validated for ages 40–79 only. This patient is outside that range — a numeric estimate would not be reliable and has not been calculated.';
            formError.classList.add('visible');
            resultsCard.classList.remove('visible');
            return;
        }

        const riskPct = calculateRisk({ age: age, sex: sex, race: race, sbp: sbp, treated: treated, tcMmol: tcMmol, hdlMmol: hdlMmol, smoker: smoker, diabetes: diabetes });
        const cat = categorize(riskPct);

        riskNumberEl.textContent = riskPct.toFixed(1) + '%';
        riskNumberEl.style.color = cat.color;
        riskCategoryPill.textContent = cat.label;
        riskCategoryPill.style.color = cat.color;
        riskCategoryPill.style.background = cat.tint;
        riskInterpretationText.textContent = interpretationText(riskPct, cat);
        riskMarker.style.left = markerPosition(riskPct) + '%';

        thresholdRows.forEach(function (row) {
            row.classList.toggle('current-row', row.dataset.cat === cat.key);
        });

        const outOfRangeMsgs = [];
        if (tcMmol < 3.3 || tcMmol > 8.3) outOfRangeMsgs.push('total cholesterol');
        if (sbp < 90 || sbp > 200) outOfRangeMsgs.push('systolic BP');
        if (outOfRangeMsgs.length > 0) {
            rangeWarning.textContent = 'Note: ' + outOfRangeMsgs.join(' and ') + ' fall outside the range used to derive the Pooled Cohort Equations — interpret this estimate with additional caution.';
            rangeWarning.classList.add('visible');
        }

        resultsCard.classList.add('visible');
        resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
})();
