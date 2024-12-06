/**
 * CC Buchner Arbeitsblatt Generator
 * Version: 1.0.0
 * Author: Dominik Gleißner
 */

// Konfiguration
const CONFIG = {
    API_URL: `http://${window.location.hostname}:5000/api/generate`,
    AUTOSAVE_DELAY: 1000,
    MAX_HISTORY_ITEMS: 10
};

// Generator Status
const GeneratorState = {
    IDLE: 'idle',
    GENERATING: 'generating',
    SUCCESS: 'success',
    ERROR: 'error'
};

let currentState = GeneratorState.IDLE;

// Initialisierung nach DOM-Load
document.addEventListener("DOMContentLoaded", function() {
    initializeFormHandling();
    setupValidation();
    setupAutosave();
    loadSavedDraft();
    
    // Initialen Abschnitt aktivieren
    const firstSection = document.getElementById('allgemeine-angaben');
    firstSection.classList.add('active');
    updateProgress('allgemeine-angaben');
});

// Navigation zwischen Abschnitten
function openSection(sectionId) {
    if (sectionId !== 'allgemeine-angaben') {
        const currentSection = document.querySelector('.section-content.active');
        if (currentSection && !validateSection(currentSection.id)) {
            alert('Bitte füllen Sie alle erforderlichen Felder aus.');
            return;
        }
    }

    // Sektionen aktualisieren
    const sections = document.querySelectorAll('.section-content');
    sections.forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');

    // Fortschrittsanzeige aktualisieren
    updateProgress(sectionId);
}

// Aktualisierung der Fortschrittsanzeige
function updateProgress(currentSection) {
    const steps = document.querySelectorAll('.step');
    let currentStep;
    
    switch(currentSection) {
        case 'allgemeine-angaben': currentStep = 0; break;
        case 'details': currentStep = 1; break;
        case 'output': currentStep = 2; break;
        default: currentStep = 0;
    }

    steps.forEach((step, index) => {
        if (index < currentStep) {
            step.classList.add('completed');
            step.classList.remove('active');
        } else if (index === currentStep) {
            step.classList.add('active');
            step.classList.remove('completed');
        } else {
            step.classList.remove('completed', 'active');
        }
    });
}

// Formular-Initialisierung
function initializeFormHandling() {
    const form = document.getElementById("arbeitsblatt-form");
    
    form.addEventListener("submit", function(event) {
        event.preventDefault();
        submitForm();
    });

    // Klassenstufen-Slider
    const slider = document.getElementById("klassenstufe");
    const output = document.getElementById("klassenstufe-value");
    if (slider && output) {
        slider.oninput = function() {
            output.textContent = this.value;
        };
    }
}

// Formularvalidierung
function validateSection(sectionId) {
    const section = document.getElementById(sectionId);
    const requiredFields = section.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.classList.add('invalid');
        } else {
            field.classList.remove('invalid');
        }
    });

    return isValid;
}

function validateForm() {
    const requiredFields = ['fach', 'thema', 'eingabetext', 'klassenstufe', 'differenzierungsstufe', 'aufgabenformat'];
    let isValid = true;

    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (!field || !field.value.trim()) {
            isValid = false;
            if (field) field.classList.add('invalid');
        } else {
            if (field) field.classList.remove('invalid');
        }
    });

    return isValid;
}

// Formular absenden
async function submitForm() {
    try {
        if (currentState === GeneratorState.GENERATING) {
            console.log("Generierung läuft bereits...");
            return;
        }

        if (!validateForm()) {
            alert("Bitte füllen Sie alle erforderlichen Felder aus.");
            return;
        }

        updateUIState(GeneratorState.GENERATING);
        const formData = collectFormData();

        const response = await fetch(CONFIG.API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();
        
        if (result.error) {
            throw new Error(result.error);
        }

        displayResult(result);
        updateUIState(GeneratorState.SUCCESS);
        saveToHistory(formData);
        clearFormDraft();

    } catch (error) {
        console.error('Fehler:', error);
        alert('Ein Fehler ist aufgetreten: ' + error.message);
        updateUIState(GeneratorState.ERROR);
    }
}

// UI-Status-Management
function updateUIState(state) {
    currentState = state;
    const submitButton = document.querySelector('button[type="submit"]');
    const loadingIndicator = document.getElementById('loading-indicator');

    switch(state) {
        case GeneratorState.GENERATING:
            submitButton.disabled = true;
            submitButton.textContent = 'Generiere Arbeitsblatt...';
            loadingIndicator.classList.remove('hidden');
            break;
        case GeneratorState.SUCCESS:
            submitButton.disabled = false;
            submitButton.textContent = 'Neues Arbeitsblatt generieren';
            loadingIndicator.classList.add('hidden');
            break;
        case GeneratorState.ERROR:
            submitButton.disabled = false;
            submitButton.textContent = 'Erneut versuchen';
            loadingIndicator.classList.add('hidden');
            break;
        default:
            submitButton.disabled = false;
            submitButton.textContent = 'Arbeitsblatt generieren';
            loadingIndicator.classList.add('hidden');
    }
}

// Formulardaten sammeln
function collectFormData() {
    return {
        fach: document.getElementById('fach').value,
        klassenstufe: document.getElementById('klassenstufe').value,
        differenzierungsstufe: document.getElementById('differenzierungsstufe').value,
        aufgabenformat: document.getElementById('aufgabenformat').value,
        thema: document.getElementById('thema').value,
        lernziele: document.getElementById('lernziele').value,
        eingabetext: document.getElementById('eingabetext').value,
        custom_prompt: document.getElementById('custom-prompt').value
    };
}

// Ergebnis anzeigen
function displayResult(result) {
    const resultContainer = document.getElementById('result');
    resultContainer.innerHTML = result.result;
    openSection('output');
}

// Zwischenablage-Funktionalität
async function copyToClipboard() {
    try {
        const text = document.getElementById('arbeitsblatt-text').textContent;
        await navigator.clipboard.writeText(text);
        alert('Text wurde in die Zwischenablage kopiert!');
    } catch (err) {
        console.error('Fehler beim Kopieren:', err);
        alert('Fehler beim Kopieren des Textes.');
    }
}

// Autosave-Funktionalität
function setupAutosave() {
    const formInputs = document.querySelectorAll('input, textarea, select');
    formInputs.forEach(input => {
        input.addEventListener('change', saveFormDraft);
        input.addEventListener('keyup', debounce(saveFormDraft, CONFIG.AUTOSAVE_DELAY));
    });
}

function saveFormDraft() {
    const formData = collectFormData();
    localStorage.setItem('arbeitsblattDraft', JSON.stringify(formData));
}

function loadSavedDraft() {
    const savedDraft = localStorage.getItem('arbeitsblattDraft');
    if (savedDraft) {
        const formData = JSON.parse(savedDraft);
        Object.keys(formData).forEach(key => {
            const element = document.getElementById(key);
            if (element) element.value = formData[key];
        });
    }
}

function clearFormDraft() {
    localStorage.removeItem('arbeitsblattDraft');
}

// Historie-Funktionalität
function saveToHistory(formData) {
    const history = JSON.parse(localStorage.getItem('arbeitsblattHistory') || '[]');
    history.unshift({
        ...formData,
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('arbeitsblattHistory', 
        JSON.stringify(history.slice(0, CONFIG.MAX_HISTORY_ITEMS)));
}

// Utility-Funktionen
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Validierungs-Setup
function setupValidation() {
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            validateField(this);
            saveFormDraft();
        });
    });
}

function validateField(field) {
    if (field.hasAttribute('required') && !field.value.trim()) {
        field.classList.add('invalid');
        return false;
    }
    field.classList.remove('invalid');
    return true;
}