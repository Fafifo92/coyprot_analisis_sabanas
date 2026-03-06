import phonenumbers
import re
import pandas as pd

def normalizar_numero_colombia(numero):
    """
    Limpia y estandariza números telefónicos al formato de 10 dígitos de Colombia.
    MEJORA: Ahora es más tolerante a errores de formato de Excel y celdas sucias.
    """
    # 1. Manejo de valores nulos o basura común en Excel
    if pd.isna(numero) or str(numero).strip() in ["", "nan", "None", "Desconocido", "?", "0"]:
        return "Desconocido"
    
    # 2. Convertir a string y extraer SOLO los dígitos
    # Esto elimina: +57, espacios, comas (,), puntos (.) y guiones (-)
    s = re.sub(r'\D', '', str(numero))
    
    longitud = len(s)
    
    # 3. Lógica de normalización inteligente
    
    # Caso A: Ya tiene los 10 dígitos correctos (ej: 3001234567)
    if longitud == 10:
        return s
    
    # Caso B: Tiene prefijo de país (ej: 573001234567 -> 12 dígitos)
    if longitud == 12 and s.startswith('57'):
        return s[2:]
    
    # Caso C: Números con prefijos internacionales largos (ej: 009573001234567)
    if longitud > 10:
        ultimos_10 = s[-10:]
        # Verificamos si los últimos 10 dígitos son un móvil (empieza por 3) 
        # o un fijo nacional (empieza por 60)
        if ultimos_10.startswith('3') or ultimos_10.startswith('60'):
            return ultimos_10
        
        # Si tiene un "57" atravesado, intentamos capturar lo que sigue
        if '57' in s:
            partes = s.split('57', 1)
            posible_num = partes[1][:10]
            if len(posible_num) == 10 and (posible_num.startswith('3') or posible_num.startswith('60')):
                return posible_num

    # 4. Si es un número corto (ej: #123, 112) o no pudimos normalizar,
    # retornamos los dígitos limpios que encontramos para no perder información.
    return s if len(s) > 0 else "Desconocido"

def validar_numero(numero, region="CO"):
    """
    Valida si un número es técnicamente posible según la librería phonenumbers.
    """
    try:
        num_str = str(numero)
        # Si no tiene el +, se lo ponemos temporalmente para validar con la región
        if not num_str.startswith('+'):
            parsed_num = phonenumbers.parse(num_str, region)
        else:
            parsed_num = phonenumbers.parse(num_str, None)
        return phonenumbers.is_valid_number(parsed_num)
    except:
        return False

def formatear_numero(numero, region="CO", formato=phonenumbers.PhoneNumberFormat.INTERNATIONAL):
    """
    Da formato visual estético para el reporte (Ej: +57 300 123 4567).
    """
    try:
        s_num = str(numero)
        if not s_num.startswith('+'):
            parsed_num = phonenumbers.parse(s_num, region)
        else:
            parsed_num = phonenumbers.parse(s_num, None)
            
        if phonenumbers.is_valid_number(parsed_num):
            return phonenumbers.format_number(parsed_num, formato)
        return s_num
    except:
        return s_num

def detectar_region(numero):
    """
    Detecta el código de país (ISO) del número.
    """
    try:
        parsed_num = phonenumbers.parse(str(numero), None)
        return phonenumbers.region_code_for_number(parsed_num)
    except:
        return None

def verificar_whatsapp(numero):
    """
    Placeholder para futura integración.
    """
    return False

if __name__ == "__main__":
    # Pruebas de fuego con casos reales de Excel
    pruebas = [
        "300.123.4567",       # Con puntos
        "57,300,123,4567",    # Con comas
        "009573105554433",    # Internacional
        "   315 123 4567  ",  # Con espacios locos
        "3001234567",         # Normal
        "?",                  # Basura
        "42452.23"            # Error de fecha pegado en columna de teléfono
    ]
    print("--- Test de Limpieza Profunda ---")
    for p in pruebas:
        print(f"Entrada: [{p}] -> Salida: [{normalizar_numero_colombia(p)}]")
