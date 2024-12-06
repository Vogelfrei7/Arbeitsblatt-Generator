from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import time

# Logging-Konfiguration
logging.basicConfig(
    filename='arbeitsblatt_generator.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Laden der Umgebungsvariablen
load_dotenv(verbose=False)

class APIKeyManager:
    def __init__(self):
        """Initialisiert den API Key Manager mit Gesundheitsüberwachung"""
        self.api_keys = [
            os.getenv('OPENAI_API_KEY_1'),
            os.getenv('OPENAI_API_KEY_2'),
            os.getenv('OPENAI_API_KEY_3')
        ]
        self.key_health = {}
        self.initialize_key_health()
        
    def initialize_key_health(self):
        """Initialisiert den Gesundheitsstatus für alle Keys"""
        for key in self.api_keys:
            if key:
                self.key_health[key] = {
                    'is_healthy': True,
                    'last_error': None,
                    'error_count': 0,
                    'last_used': 0,
                    'cooldown_until': 0
                }

    def get_healthy_key(self):
        """Gibt den nächsten gesunden API-Key zurück"""
        current_time = time.time()
        
        for key in self.api_keys:
            if not key:
                continue
                
            health = self.key_health[key]
            
            if current_time > health['cooldown_until'] and health['is_healthy']:
                health['last_used'] = current_time
                return key
                
        return None

    def mark_key_error(self, key, error):
        """Markiert einen Key als fehlerhaft"""
        if key in self.key_health:
            health = self.key_health[key]
            health['error_count'] += 1
            health['last_error'] = error
            
            if "quota" in str(error).lower():
                health['cooldown_until'] = time.time() + 300
                health['is_healthy'] = False
            else:
                health['cooldown_until'] = time.time() + 60
                
            if health['error_count'] >= 3:
                health['is_healthy'] = False
                logger.warning(f"API Key deaktiviert nach zu vielen Fehlern: {error}")

    def reset_key_health(self):
        """Setzt den Gesundheitsstatus aller Keys zurück"""
        self.initialize_key_health()

class ArbeitsblattGenerator:
    def __init__(self):
        """Initialisiert den Arbeitsblatt Generator"""
        self.key_manager = APIKeyManager()
        
        # Modell-Konfiguration
        self.model_config = {
            'Leicht': {
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_tokens': 1500
            },
            'Mittel': {
                'model': 'gpt-4o-mini',
                'temperature': 0.5,
                'max_tokens': 2000
            },
            'Schwer': {
                'model': 'gpt-4o-mini',
                'temperature': 0.7,
                'max_tokens': 2500
            }
        }

        # Stufenvorgaben
        self.stufen_vorgaben = {
            "5-6": {
                "sprache": """
                    - Sehr kurze, klare Sätze (max. 8-10 Wörter)
                    - Alltags- und Bildungssprache gemischt
                    - Neue Fachbegriffe werden immer direkt erklärt
                    - Häufige Visualisierungen, Beispiele und Analogien""",
                "methoden": """
                    - Kleinschrittige Anleitungen
                    - Viele Zwischenschritte
                    - Viel Scaffolding
                    - Starke visuelle Unterstützung
                    - Partnermethoden und spielerische Elemente""",
                "kognitiv": """
                    - Konkrete Beispiele aus der Lebenswelt
                    - Einfache Wenn-Dann-Beziehungen
                    - Beschreibungen und Benennungen
                    - Erste einfache Vergleiche"""
            },
            "7-8": {
                "sprache": """
                    - Mittellange Sätze (10-12 Wörter)
                    - Zunehmender Fachbegriff-Einsatz
                    - Erklärungen bei komplexeren Begriffen
                    - Kombination aus Text und Visualisierung""",
                "methoden": """
                    - Geleitete Arbeitsschritte mit mehr Eigenständigkeit
                    - Einführung verschiedener Arbeitstechniken
                    - Methodenwechsel innerhalb einer Aufgabe
                    - Erste Recherche-Aufgaben""",
                "kognitiv": """
                    - Transfer auf ähnliche Kontexte
                    - Einfache Analysen und Interpretationen
                    - Herstellung von Zusammenhängen
                    - Begründungen auf Basis gelernter Konzepte"""
            },
            "9-11": {
                "sprache": """
                    - Komplexere Satzstrukturen (12-15 Wörter)
                    - Regelmäßiger Einsatz von Fachsprache
                    - Fachbegriffe werden vernetzt
                    - Auch abstrakte Beschreibungen""",
                "methoden": """
                    - Selbstständiges Arbeiten mit Leitfragen
                    - Systematische Analyse-Tools
                    - Komplexere Arbeitstechniken
                    - Einführung wissenschaftlicher Methoden""",
                "kognitiv": """
                    - Abstrakteres Denken
                    - Systematische Analysen
                    - Vergleich verschiedener Perspektiven
                    - Entwicklung eigener Argumentationen"""
            },
            "12-13": {
                "sprache": """
                    - Komplexe Satzstrukturen
                    - Durchgehende Fachsprache
                    - Wissenschaftliche Formulierungen
                    - Präzise Argumentationsketten""",
                "methoden": """
                    - Wissenschaftspropädeutisches Arbeiten
                    - Eigenständige Methodenwahl
                    - Komplexe Analysemodelle
                    - Forschendes Lernen""",
                "kognitiv": """
                    - Theoriegestützte Analyse
                    - Entwicklung eigener Modelle
                    - Kritische Reflexion
                    - Transfer auf neue Kontexte"""
            }
        }

        self.format_anweisungen = {
            "Multiple Choice": {
                "struktur": "4-5 Antwortmöglichkeiten pro Frage, eine korrekte Antwort",
                "qualitaet": "plausible Distraktoren, keine offensichtlich falschen Optionen",
                "progression": "von Faktenwissen zu Transferleistungen"
            },
            "Lückentext": {
                "struktur": "sinnvolle Lücken im Kontext, angemessene Anzahl",
                "qualitaet": "eindeutige Lösungen, sprachlich korrekte Integration",
                "progression": "von einzelnen Begriffen zu komplexeren Konzepten"
            },
            "Wahr/Falsch": {
                "struktur": "präzise formulierte Aussagen, ausgewogene Verteilung",
                "qualitaet": "keine Mehrdeutigkeiten, klare Begründbarkeit",
                "progression": "zunehmende Komplexität und Transferleistung"
            }
        }
        
        logger.info("ArbeitsblattGenerator erfolgreich initialisiert")

    def get_stufe_group(self, klassenstufe):
        """Bestimmt die Stufengruppe basierend auf der Klassenstufe"""
        stufe = int(klassenstufe)
        if stufe <= 6:
            return "5-6"
        elif stufe <= 8:
            return "7-8"
        elif stufe <= 11:
            return "9-11"
        else:
            return "12-13"

    def create_prompt(self, data):
        """Erstellt einen optimierten Prompt"""
        stufe_group = self.get_stufe_group(data['klassenstufe'])
        stufe_info = self.stufen_vorgaben[stufe_group]
        format_info = self.format_anweisungen[data['aufgabenformat']]
        
        prompt = f"""Erstelle ein differenziertes {data['fach']}-Arbeitsblatt für die Klassenstufe {data['klassenstufe']} zum Thema "{data['thema']}" mit {data['aufgabenformat']}-Aufgaben.

# Rahmenbedingungen
- Fach: {data['fach']}
- Klassenstufe: {data['klassenstufe']}
- Schwierigkeitsgrad: {data['differenzierungsstufe']}
- Aufgabenformat: {data['aufgabenformat']}

# Didaktische Anforderungen
1. Sprachliches Niveau:
   - {stufe_info['sprache']}
2. Methodische Gestaltung:
   - {stufe_info['methoden']}
3. Kognitive Anforderungen:
   - {stufe_info['kognitiv']}

# Aufgabenstruktur
- Format: {format_info['struktur']}
- Qualitätsmerkmale: {format_info['qualitaet']}
- Progression: {format_info['progression']}

# Analyseschritte
1. Lies und analysiere das folgende Material
2. Identifiziere die Hauptkonzepte und Schlüsselbegriffe
3. Entwickle passende Aufgabenstellungen gemäß dem gewählten Format
4. Formuliere klare Arbeitsanweisungen
5. Erstelle einen Erwartungshorizont

# Ausgabeformat
- Titel des Arbeitsblatts
- Nummerierte Aufgaben im {data['aufgabenformat']}-Format
- Lehrerhandreichung immer anschließend mit
    - Einleitender Materialtext oder Kontext (2-3 Sätze)
    - Bei Bedarf: Differenzierte Hilfestellungen in Klammern
    - Erwartungshorizont/Musterlösung

FORMATIERUNGSHINWEISE:
- Verwende keine Markdown-Formatierung
- Nutze normale Nummerierung (1., 2., 3., etc.)
- Strukturiere den Text durch Absätze und Leerzeilen
- Verwende für Aufzählungen normale Buchstaben (a), b), c)) oder Zahlen

# Material
{data['eingabetext']}"""

        if data.get('lernziele'):
            prompt += f"""
# Lernziele
{data['lernziele']}"""

        if data.get('custom_prompt'):
            prompt += f"""
# Zusätzliche Anweisungen
{data['custom_prompt']}"""

        return prompt

    def generate_worksheet(self, data):
        """Optimierte Arbeitsblatt-Generierung mit verbessertem API-Handling"""
        prompt = self.create_prompt(data)
        config = self.model_config[data['differenzierungsstufe']]
        
        for _ in range(3):  # Maximale Anzahl von Versuchen
            api_key = self.key_manager.get_healthy_key()
            
            if not api_key:
                logger.error("Keine gesunden API Keys verfügbar")
                raise Exception("Momentan keine API-Verbindung möglich. Bitte später erneut versuchen.")
            
            try:
                client = OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model=config['model'],
                    messages=[
                        {"role": "system", "content": "Du bist ein erfahrener {data['fach']}-Lehrer mit langjähriger Unterrichtserfahrung und Experte in der Erstellung differenzierter Arbeitsblätter"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=config['temperature'],
                    max_tokens=config['max_tokens'],
                    presence_penalty=0.2,
                    frequency_penalty=0.3,
                    timeout=30
                )
                
                return self.format_response(response.choices[0].message.content, data)
                
            except Exception as e:
                self.key_manager.mark_key_error(api_key, e)
                logger.warning(f"Fehler bei API-Anfrage: {str(e)}")
                continue
        
        raise Exception("Alle Versuche fehlgeschlagen. Bitte später erneut versuchen.")

    def format_response(self, content, data):
        """Formatiert die API-Antwort"""
        return f"""
        <div class='arbeitsblatt-output'>
            <div class='arbeitsblatt-header'>
                <h2>Generiertes Arbeitsblatt</h2>
                <div class='meta-info'>
                    <span>Fach: {data['fach']}</span>
                    <span>Klasse: {data['klassenstufe']}</span>
                    <span>Niveau: {data['differenzierungsstufe']}</span>
                    <span>Format: {data['aufgabenformat']}</span>
                    <span>Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}</span>
                </div>
            </div>
            <div class='arbeitsblatt-content'>
                <pre id="arbeitsblatt-text">{content}</pre>
            </div>
            <div class='arbeitsblatt-actions'>
                <button onclick="copyToClipboard()" class='copy-btn'>
                    In Zwischenablage kopieren
                </button>
            </div>
        </div>
        """

# Flask App mit optimiertem Setup
app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins for development
        "methods": ["POST", "OPTIONS"],  # Explicitly allow required methods
        "allow_headers": ["Content-Type"],  # Allow required headers
        "expose_headers": ["Access-Control-Allow-Origin"],  # Expose CORS headers
        "supports_credentials": False  # No credentials needed for this API
    }
})

# Generator initialisieren
generator = ArbeitsblattGenerator()

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        
        required_fields = ['fach', 'klassenstufe', 'differenzierungsstufe', 'aufgabenformat', 'thema', 'eingabetext']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Unvollständige Eingabedaten"}), 400
        
        result = generator.generate_worksheet(data)
        return jsonify({"result": result})

    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )