import re

# Diccionario simplificado de Municipios principales y sus coordenadas aproximadas
# Se puede expandir según necesidad. Formato: MUNICIPIO: (LAT, LON)
MUNICIPIOS_COORDS = {
    "MEDELLIN": (6.2442, -75.5812), "BOGOTA": (4.7110, -74.0721), "CALI": (3.4516, -76.5320),
    "BARRANQUILLA": (10.9685, -74.7813), "CARTAGENA": (10.3910, -75.4794), "CUCUTA": (7.8939, -72.5078),
    "BUCARAMANGA": (7.1193, -73.1227), "PEREIRA": (4.8133, -75.6961), "SANTA MARTA": (11.2408, -74.1990),
    "IBAGUE": (4.4389, -75.2322), "BELLO": (6.3373, -75.5579), "PASTO": (1.2136, -77.2811),
    "MANIZALES": (5.0703, -75.5138), "NEIVA": (2.9273, -75.2819), "SOACHA": (4.5794, -74.2160),
    "VILLAVICENCIO": (4.1420, -73.6266), "ARMENIA": (4.5339, -75.6811), "SOLEDAD": (10.9184, -74.7699),
    "VALLEDUPAR": (10.4631, -73.2532), "ITAGUI": (6.1846, -75.5991), "MONTERIA": (8.7480, -75.8814),
    "SINCELEJO": (9.3047, -75.3978), "POPAYAN": (2.4378, -76.6132), "FLORENCIA": (1.6175, -75.6038),
    "RIOHACHA": (11.5444, -72.9072), "TUNJA": (5.5353, -73.3678), "YOPAL": (5.3378, -72.3959),
    "QUIBDO": (5.6947, -76.6611), "BARBOSA": (6.4388, -75.3333), # Antioquia
    "AMAGA": (6.0400, -75.7032), "COVENAS": (9.4217, -75.6833), "LORICA": (9.2394, -75.8139),
    "ENVIGADO": (6.1759, -75.5917), "SABANETA": (6.1515, -75.6166), "RIONEGRO": (6.1551, -75.3737),
    "APARTADO": (7.8828, -76.6321), "TURBO": (8.0927, -76.7278), "CAUCASIA": (7.9865, -75.1932),
    "GIRARDOTA": (6.3789, -75.4455), "COPACABANA": (6.3466, -75.5088), "LA ESTRELLA": (6.1578, -75.6433),
    "CALDAS": (6.0911, -75.6357), "GUARNE": (6.2796, -75.4429), "MARINILLA": (6.1783, -75.3385),
    "SAN GIL": (6.5543, -73.1311), "BARRANCABERMEJA": (7.0653, -73.8547), "GIRON": (7.0682, -73.1698),
    "PIEDECUESTA": (6.9874, -73.0494), "FLORIDABLANCA": (7.0622, -73.0864), "DUITAMA": (5.8256, -73.0335),
    "SOGAMOSO": (5.7145, -72.9339), "ZIPAQUIRA": (5.0267, -74.0016), "FUSAGASUGA": (4.3365, -74.3638),
    "FACATATIVA": (4.8115, -74.3541), "CHIA": (4.8624, -74.0586), "MOSQUERA": (4.7059, -74.2302),
    "MADRID": (4.7323, -74.2642), "FUNZA": (4.7167, -74.2117), "CAJICA": (4.9189, -74.0272)
}

def inferir_municipio_y_coords(nombre_celda):
    """
    Analiza cadenas como 'ANT.BARBOSA-2_R1', 'SUC.COVENAS-5' o 'MED.CORDOBA'.
    Extrae 'BARBOSA', 'COVENAS', 'CORDOBA' y busca coordenadas.
    Retorna: (NombreMunicipio, Lat, Lon) o (None, None, None)
    """
    if not nombre_celda or not isinstance(nombre_celda, str):
        return None, None, None

    texto = nombre_celda.upper().strip()
    
    # Lógica 1: Buscar patrones tipo DEPTO.MUNICIPIO o MUNICIPIO-SECTOR
    # Eliminamos sufijos técnicos comunes primero (_R1, -2, etc)
    texto_limpio = re.sub(r'[-_][A-Z0-9]+$', '', texto) # Quita _R1, -5
    texto_limpio = re.sub(r'[-_][A-Z0-9]+$', '', texto_limpio) # Repite por si acaso (ANT.BARBOSA-2_R1)

    # Separar por punto (común en celdas Claro/Movistar: ANT.BARBOSA)
    partes = re.split(r'[.]', texto_limpio)
    
    candidato = ""
    
    # Si hay punto, generalmente el segundo es el municipio (ANT.BARBOSA)
    if len(partes) >= 2:
        candidato = partes[1].strip()
    else:
        # Si no hay punto, tomamos todo el texto limpio
        candidato = texto_limpio.strip()

    # Buscamos coincidencias parciales o exactas en el diccionario
    for muni, coords in MUNICIPIOS_COORDS.items():
        # Verificamos si el candidato contiene el municipio (ej: BARBOSA contiene BARBOSA)
        if muni == candidato or (len(candidato) > 4 and muni in candidato):
            return muni, coords[0], coords[1]
    
    return None, None, None