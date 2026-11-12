"""Textos en español de las filas de la ventana de Ajustes (ver settings.registry)."""

from __future__ import annotations

SETTINGS_STRINGS: dict[str, str] = {
    # Secciones de la barra lateral
    "category.general": "General",
    "category.appearance": "Apariencia",
    "category.audio": "Audio y notificaciones",
    "category.storage": "Almacenamiento",
    "category.shortcuts": "Atajos",
    "category.advanced": "Avanzado",
    # Nombres de las opciones
    "option.language.en": "English",
    "option.language.es": "Español",
    "option.appearance_mode.system": "Sistema",
    "option.appearance_mode.light": "Claro",
    "option.appearance_mode.dark": "Oscuro",
    "option.density.comfortable": "Cómodo",
    "option.density.compact": "Compacto",
    "option.whisper_device.auto": "Automático",
    "option.whisper_device.cuda": "GPU (CUDA)",
    "option.whisper_device.cpu": "CPU",
    # General
    "setting.language.label": "Idioma de la interfaz",
    "setting.language.help": "Idioma de los menús y mensajes, y formato de fecha y hora. "
    "El tutor siempre habla en inglés.",
    "setting.autostart.label": "Iniciar con Windows",
    "setting.autostart.help": "Abre la aplicación automáticamente al iniciar sesión.",
    # Apariencia
    "setting.appearance_mode.label": "Tema",
    "setting.appearance_mode.help": "Claro, oscuro o el mismo que el sistema operativo.",
    "setting.ui_scale.label": "Escala de la interfaz",
    "setting.ui_scale.help": "Agranda o reduce todos los elementos. Se aplica de inmediato.",
    "setting.chat_font_size.label": "Tamaño de fuente del chat",
    "setting.chat_font_size.help": "Tamaño del texto de la conversación, de 10 a 22 puntos.",
    "setting.density.label": "Densidad del diseño",
    "setting.density.help": "El modo compacto usa menos espacio entre los elementos.",
    # Audio y notificaciones
    "setting.tts_enabled.label": "Salida de voz",
    "setting.tts_enabled.help": "Lee en voz alta las respuestas del tutor con Piper.",
    "setting.cue_record_start.label": "Sonido al iniciar la grabación",
    "setting.cue_record_start.help": "Reproduce un pitido breve cuando el micrófono empieza "
    "a escuchar.",
    "setting.cue_record_stop.label": "Sonido al detener la grabación",
    "setting.cue_record_stop.help": "Reproduce un pitido breve cuando termina la grabación.",
    "setting.cue_error.label": "Sonido en caso de error",
    "setting.cue_error.help": "Reproduce un doble pitido grave cuando algo falla.",
    "setting.notify_report.label": "Notificación de escritorio del informe",
    "setting.notify_report.help": "Muestra una notificación cuando el informe de fin de sesión "
    "está listo y la ventana no tiene el foco.",
    # Almacenamiento
    "setting.data_dir.label": "Carpeta de datos",
    "setting.data_dir.help": "Dónde se guardan las conversaciones, los errores y los registros. "
    "Los datos existentes no se mueven.",
    "setting.export_dir.label": "Carpeta de exportación",
    "setting.export_dir.help": "Dónde se guardan por defecto los informes y las listas de "
    "errores exportados. Si está vacía se usa Documentos.",
    "setting.open_data_folder.label": "Abrir carpeta de datos",
    "setting.open_data_folder.help": "Muestra en el Explorador de archivos la carpeta con tus "
    "conversaciones y errores.",
    "setting.export_report.label": "Exportar el último informe",
    "setting.export_report.help": "Guarda el informe de la última sesión como archivo Markdown.",
    "setting.export_mistakes.label": "Exportar errores",
    "setting.export_mistakes.help": "Guarda la lista de errores como archivo CSV.",
    "setting.clear_logs.label": "Eliminar registros de conversación",
    "setting.clear_logs.help": "Elimina de forma permanente todos los archivos de conversación "
    "guardados. Tu historial de errores se conserva.",
    "setting.clear_mistakes.label": "Eliminar historial de errores",
    "setting.clear_mistakes.help": "Elimina de forma permanente todos los errores registrados "
    "y sus estadísticas de práctica.",
    # Atajos
    "setting.ptt_key.label": "Tecla para hablar",
    "setting.ptt_key.help": "Mantén pulsada esta tecla para hablar. Las demás aplicaciones "
    "también la reciben.",
    "setting.shortcut_end_session.label": "Finalizar sesión",
    "setting.shortcut_end_session.help": "Termina la conversación y genera el informe.",
    "setting.shortcut_settings.label": "Abrir ajustes",
    "setting.shortcut_settings.help": "Abre esta ventana.",
    "setting.shortcut_chat_tab.label": "Ir a la pestaña Chat",
    "setting.shortcut_chat_tab.help": "Muestra la conversación.",
    "setting.shortcut_mistakes_tab.label": "Ir a la pestaña Errores",
    "setting.shortcut_mistakes_tab.help": "Muestra tus errores recurrentes.",
    # Avanzado
    "setting.whisper_device.label": "Dispositivo de reconocimiento de voz",
    "setting.whisper_device.help": "Automático usa la GPU cuando está disponible. "
    "La CPU es más lenta, pero siempre funciona.",
    "setting.whisper_model.label": "Modelo de reconocimiento de voz",
    "setting.whisper_model.help": "Los modelos más grandes son más precisos, pero más lentos "
    "y necesitan más memoria.",
    "setting.ollama_url.label": "URL del servidor Ollama",
    "setting.ollama_url.help": "Dirección del servidor Ollama.",
    "setting.ollama_model.label": "Modelo de Ollama",
    "setting.ollama_model.help": "Modelo usado para las respuestas y los comentarios. "
    "Debe estar descargado previamente.",
    "setting.test_connection.label": "Probar la conexión con Ollama",
    "setting.test_connection.help": "Comprueba que el servidor responde y que el modelo "
    "está instalado.",
    "setting.log_level.label": "Nivel de detalle del registro",
    "setting.log_level.help": "Cuánta información se escribe en el archivo de registro.",
    "setting.open_logs_folder.label": "Abrir carpeta de registros",
    "setting.open_logs_folder.help": "Muestra los archivos de registro de la aplicación, "
    "útiles para el soporte técnico.",
    "setting.restore_defaults.label": "Restaurar valores predeterminados",
    "setting.restore_defaults.help": "Devuelve todos los ajustes a su valor predeterminado. "
    "No se guarda nada hasta que pulses Guardar.",
    # Ventana de ajustes
    "settings.title": "Ajustes",
    "settings.search_placeholder": "Buscar ajustes (Ctrl+F)",
    "settings.search_empty": "Ningún ajuste coincide con '{query}'",
    "settings.dirty": "● Cambios sin guardar ({count})",
    "settings.clean": "Sin cambios",
    "settings.pill_restart": "Requiere reinicio",
    "settings.locked": "Definido por {var}",
    "settings.confirm_discard_title": "¿Descartar los cambios?",
    "settings.confirm_discard": "Hay cambios sin guardar. ¿Cerrar sin guardar?",
    "settings.confirm_restore_title": "¿Restaurar los valores predeterminados?",
    "settings.confirm_restore": "Todos los ajustes volverán a su valor predeterminado. "
    "No se guarda nada hasta que pulses Guardar.",
    "settings.save_failed": "No se pudieron guardar los ajustes: {error}",
    "settings.action_failed": "{error}",
    "button.save": "Guardar",
    "button.cancel": "Cancelar",
    "button.restore_defaults": "Restaurar valores",
    "button.browse": "Examinar...",
    "button.open": "Abrir",
    "unit.points": "{value} pt",
    # Aviso de reinicio
    "banner.restart": "Reinicia la aplicación para aplicar: {names}",
    "banner.restart_now": "Reiniciar ahora",
    "banner.later": "Más tarde",
    "restart.confirm_title": "¿Reiniciar ahora?",
    "restart.confirm_message": "La conversación actual terminará. ¿Reiniciar de todos modos?",
    # Captura de teclas y pausa de la tecla para hablar
    "settings.ptt_paused": "La tecla para hablar está en pausa mientras Ajustes está abierto.",
    "button.change": "Cambiar...",
    "capture.title_ptt": "Tecla para hablar",
    "capture.title_shortcut": "Nuevo atajo",
    "capture.prompt_ptt": "Pulsa la tecla que mantendrás pulsada para hablar.",
    "capture.prompt_shortcut": "Pulsa el nuevo atajo, por ejemplo Ctrl+K.",
    "capture.hint": "Esc cancela.",
    "capture.unsupported": "Esa tecla no se puede usar aquí.",
}
