import { TIME_INTERVAL_LABELS, VALVE_SEVERITY_LABELS, VALVE_TYPE_LABELS } from './constants.js';

export const createElement = (tag, attributes = {}, children = []) => {
    const element = document.createElement(tag);
    
    Object.entries(attributes).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else {
            element.setAttribute(key, value);
        }
    });
    
    children.forEach(child => {
        if (typeof child === 'string') {
            element.appendChild(document.createTextNode(child));
        } else {
            element.appendChild(child);
        }
    });
    
    return element;
};

export const createSelect = (options, attributes = {}) => {
    const select = createElement('select', attributes);
    
    options.forEach(option => {
        const optionElement = createElement('option', {
            value: option.value
        }, [option.label]);
        
        select.appendChild(optionElement);
    });
    
    return select;
};

export const createFormGroup = (label, element, className = '') => {
    const formGroup = createElement('div', { className: `form-group ${className}`.trim() });
    const labelElement = createElement('label', {}, [label]);
    
    formGroup.appendChild(labelElement);
    formGroup.appendChild(element);
    
    return formGroup;
};

export const createButton = (text, onClick, className = '') => {
    return createElement('button', {
        className,
        onclick: onClick
    }, [text]);
};

export const createButtonContainer = (buttons) => {
    const container = createElement('div', { className: 'button-container' });
    buttons.forEach(button => container.appendChild(button));
    return container;
};

export const createResultContainer = (isAppropriate, content) => {
    const container = createElement('div', {
        className: `result-container ${isAppropriate ? 'result-appropriate' : 'result-inappropriate'}`
    });
    
    container.innerHTML = content;
    return container;
};

export const createTag = (text, type) => {
    return createElement('span', {
        className: `tag tag-${type}`
    }, [text]);
};

export const createInfoBox = (content, type = 'info') => {
    return createElement('div', {
        className: `${type}-box`
    }, [content]);
};

export const formatTimeInterval = (interval) => {
    return TIME_INTERVAL_LABELS[interval] || interval;
};

export const formatValveSeverity = (severity) => {
    return VALVE_SEVERITY_LABELS[severity] || severity;
};

export const formatValveType = (type) => {
    return VALVE_TYPE_LABELS[type] || type;
};

export const validateForm = (formData) => {
    const errors = [];
    
    Object.entries(formData).forEach(([key, value]) => {
        if (!value) {
            errors.push(`${key} is required`);
        }
    });
    
    return errors;
};

export const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

export const scrollToTop = () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
};

export const formatDate = (date) => {
    return new Date(date).toLocaleDateString('en-AU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}; 