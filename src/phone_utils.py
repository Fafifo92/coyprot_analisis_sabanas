import phonenumbers
import re
import pandas as pd

def normalizar_numero_colombia(numero):
    """
    Limpia y estandariza números telefónicos al formato de 10 dígitos de Colombia.
    Elimina prefijos de país (57), prefijos de operador (132, 005, 009) y basura.
    
    Objetivo: Que '573001234567', '+57 300 123 4567' y '3001234567' 
    sean tratados como el mismo número único.
    """
    # 1. Manejo de valores vacíos o nulos
    if pd.isna(numero) or str(numero).strip() in ["", "nan", "None", "Desconocido"]:
        return "Desconocido"
    
    # 2. Convertir a string y eliminar todo lo que no sea dígito
    # Esto elimina +, -, espacios, paréntesis
    s = re.sub(r'\D', '', str(numero))
    
    longitud = len(s)
    
    # 3. Lógica de normalización
    
    # Caso ideal: Ya tiene 10 dígitos (Ej: 3001234567)
    if longitud == 10:
        return s
    
    # Caso mayor a 10 dígitos (Posible prefijo país o carrier)
    if longitud > 10:
        ultimos_10 = s[-10:]
        
        # Validamos si esos últimos 10 dígitos parecen un número colombiano válido
        # - Móvil: Empieza por 3 (Ej: 310...)
        # - Fijo Nuevo: Empieza por 60 (Ej: 601...)
        if ultimos_10.startswith('3') or ultimos_10.startswith('60'):
            return ultimos_10
            
        # Caso específico: Prefijo país 57 + 10 dígitos = 12 dígitos
        if s.startswith('57') and longitud == 12:
            return s[2:]
            
        # Caso específico: Prefijos de larga distancia (005, 009, 007) + 57 + Número
        # Ej: 009573001234567 -> 15 dígitos
        if s.startswith('00') and '57' in s:
            # Intentar buscar donde empieza el 57 y tomar lo que sigue
            partes = s.split('57', 1)
            if len(partes) > 1 and len(partes[1]) == 10:
                return partes[1]

    # Si tiene menos de 10 dígitos (Ej: #123, 112, 911) o no coincide con reglas, se retorna limpio
    return s

def validar_numero(numero, region="CO"):
    """
    Valida si un número es técnicamente posible y válido para una región específica.
    """
    try:
        # Asegurar que se pasa como string para el parser
        parsed_num = phonenumbers.parse(str(numero), region)
        return phonenumbers.is_valid_number(parsed_num)
    except phonenumbers.NumberParseException:
        return False

def formatear_numero(numero, region="CO", formato=phonenumbers.PhoneNumberFormat.INTERNATIONAL):
    """
    Da formato visual estético (Ej: +57 300 1234567).
    Útil para la visualización en el reporte PDF/HTML si se desea.
    """
    try:
        parsed_num = phonenumbers.parse(str(numero), region)
        if phonenumbers.is_valid_number(parsed_num):
            return phonenumbers.format_number(parsed_num, formato)
        return str(numero)
    except phonenumbers.NumberParseException:
        return str(numero)

def detectar_region(numero):
    """
    Intenta detectar el código de país (ISO) de un número.
    """
    try:
        # Parseamos sin región por defecto para ver si el número trae el prefijo (+)
        parsed_num = phonenumbers.parse(str(numero), None)
        return phonenumbers.region_code_for_number(parsed_num)
    except phonenumbers.NumberParseException:
        return None

def verificar_whatsapp(numero):
    """
    Placeholder para futura funcionalidad de verificación de WhatsApp.
    Actualmente solo retorna False.
    """
    # Aquí se podría integrar una API externa en el futuro
    return False

if __name__ == "__main__":
    # Pruebas rápidas
    pruebas = [
        "3001234567",           # Normal
        "573001234567",         # Con 57
        "+57 300 123 4567",     # Con formato
        "009573001234567",      # Salida internacional
        "310 555 5555",         # Espacios
        "123",                  # Corto
        "NaN"                   # Nulo
    ]
    print("--- Test de Normalización ---")
    for p in pruebas:
        print(f"Entrada: {p} -> Salida: {normalizar_numero_colombia(p)}")