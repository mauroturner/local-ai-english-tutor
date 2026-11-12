"""Spanish interface texts (neutral, professional register)."""

from __future__ import annotations

from .es_settings import SETTINGS_STRINGS

STRINGS: dict[str, str] = {
    # Window chrome
    "app.title": "Tutor de inglés con IA - Asistente virtual",
    "app.heading": "Tutor virtual de inglés",
    "tab.chat": "Chat",
    "tab.mistakes": "Errores",
    "hint.hold": "Mantén pulsada '{key}' para hablar y suéltala para enviar",
    # Microphone, level, status, buttons
    "mic.label": "Seleccionar micrófono:",
    "mic.none": "Ninguno",
    "level.label": "Nivel de audio:",
    "button.end_session": "Finalizar sesión",
    "button.stop_practice": "Detener práctica",
    "button.practice": "Practicar",
    "tooltip.settings": "Ajustes ({shortcut})",
    "tooltip.end_session_disabled": "Disponible cuando Alex no esté ocupado",
    # Status chip (one per session state)
    "chip.loading": "Cargando",
    "chip.idle": "Listo",
    "chip.recording": "Grabando",
    "chip.transcribing": "Transcribiendo",
    "chip.thinking": "Pensando",
    "chip.speaking": "Hablando",
    "chip.reporting": "Redactando",
    # Status messages (see i18n.translate_status)
    "status.initializing": "Iniciando...",
    "status.ready": "Listo",
    "status.ready_hold": "Listo: mantén {key}",
    "status.practice_hold": "Práctica: mantén {key} para responder",
    "status.loading": "Cargando el modelo de voz...",
    "status.listening": "Escuchando...",
    "status.transcribing": "Transcribiendo...",
    "status.thinking": "Pensando...",
    "status.speaking": "Hablando...",
    "status.preparing_practice": "Preparando la práctica...",
    "status.checking_answer": "Revisando tu respuesta...",
    "status.writing_feedback": "Redactando comentarios...",
    "status.too_short": "Muy corto o con poco volumen, inténtalo de nuevo",
    "status.not_caught": "No te he entendido, inténtalo de nuevo",
    # Chat bubbles
    "chat.empty": "Mantén pulsada {key} y habla para empezar la conversación.",
    "chat.you": "Tú: {text}",
    "chat.alex": "Alex: {text}",
    "chat.tip": 'Consejo: "{original}"  ->  "{corrected}"',
    "practice.correct": "¡Correcto!",
    "practice.retry": "Inténtalo de nuevo:",
    "practice.banner": 'Practicando: "{original}" -> "{corrected}"',
    # Mistakes tab
    "mistakes.empty": "Todavía no hay errores. Conversa con Alex y aparecerán aquí.",
    "mistakes.truncated": "Se muestran los {shown} errores más frecuentes de {total}.",
    "mistakes.stats": "x{count}   última vez {date}   práctica {successes}/{attempts}",
    "severity.major": "GRAVE",
    "severity.minor": "LEVE",
    "notify.report_title": "El informe de tu sesión está listo",
    "notify.report_body": "Abre la aplicación para revisar tus comentarios.",
    "restart.failed": (
        "No se pudo reiniciar la aplicación automáticamente. La configuración se guardó; "
        "vuelve a iniciarla con: python main.py"
    ),
}

STRINGS.update(SETTINGS_STRINGS)
