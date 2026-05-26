"""Dictionary of Spanish abbreviations for TTS expansion."""

# Mapping of abbreviations to full forms for TTS pronunciation
# Keys are case-insensitive, matching any variation
ABBREVIATION_MAP = {
    # Países y regiones
    "E.E.U.U.": "Estados Unidos",
    "EE.UU.": "Estados Unidos",
    "EEUU": "Estados Unidos",
    "U.S.A.": "Estados Unidos de América",
    "USA": "Estados Unidos de América",
    "U.K.": "Reino Unido",
    "U.E.": "Unión Europea",
    "R.U.": "Reino Unido",

    # Títulos y tratamientos
    "Sr.": "Señor",
    "Sra.": "Señora",
    "Dr.": "Doctor",
    "Dra.": "Doctora",
    "Prof.": "Profesor",
    "Profra.": "Profesora",
    "Ing.": "Ingeniero",
    "Arq.": "Arquitecto",
    "Lic.": "Licenciado",

    # Títulos académicos
    "Ph.D.": "Doctorado",
    "M.B.A.": "Máster en Administración de Empresas",

    # Unidades y medidas
    "kg.": "kilogramos",
    "gr.": "gramos",
    "cm.": "centímetros",
    "km.": "kilómetros",
    "m.": "metros",
    "mm.": "milímetros",
    "Km.": "kilómetros",
    "m2": "metros cuadrados",
    "km2": "kilómetros cuadrados",
    "°C": "grados Celsius",
    "°F": "grados Fahrenheit",
    "% ": "por ciento ",

    # Organizaciones e instituciones
    "ONU": "Organización de las Naciones Unidas",
    "O.N.U.": "Organización de las Naciones Unidas",
    "OMS": "Organización Mundial de la Salud",
    "O.M.S.": "Organización Mundial de la Salud",
    "OTAN": "Organización del Tratado del Atlántico Norte",
    "O.T.A.N.": "Organización del Tratado del Atlántico Norte",
    "UE": "Unión Europea",
    "BCE": "Banco Central Europeo",
    "FMI": "Fondo Monetario Internacional",
    "F.M.I.": "Fondo Monetario Internacional",
    "BM": "Banco Mundial",
    "OMC": "Organización Mundial del Comercio",
    "O.M.C.": "Organización Mundial del Comercio",
    "IBEX": "Índice Bursátil Español",
    "DAX": "Índice Alemán de Valores",
    "Nasdaq": "Índice Tecnológico",
    "S&P": "Standard and Poor's",
    "NYSE": "Bolsa de Nueva York",

    # Medios y empresas
    "BBC": "Corporación Británica de Radiodifusión",
    "CNN": "Cable News Network",
    "Reuters": "Reuters",
    "AFP": "Agencia France Presse",
    "AP": "Associated Press",
    "EPA": "Agencia de Protección Ambiental",
    "NASA": "Agencia Espacial Estadounidense",

    # Tiempo y fechas
    "a.C.": "antes de Cristo",
    "d.C.": "después de Cristo",
    "aprox.": "aproximadamente",
    "ene.": "enero",
    "feb.": "febrero",
    "mar.": "marzo",
    "abr.": "abril",
    "may.": "mayo",
    "jun.": "junio",
    "jul.": "julio",
    "ago.": "agosto",
    "sep.": "septiembre",
    "sept.": "septiembre",
    "oct.": "octubre",
    "nov.": "noviembre",
    "dic.": "diciembre",

    # Direcciones y ubicaciones
    "Avenida": "Avenida",
    "Avda.": "Avenida",
    "Av.": "Avenida",
    "Calle": "Calle",
    "C.": "Calle",
    "Paseo": "Paseo",
    "Ps.": "Paseo",
    "Pza.": "Plaza",
    "nº": "número",
    "N°": "número",
    "apt.": "apartamento",
    "apto.": "apartamento",

    # Otros
    "etc.": "et cetera",
    "p.ej.": "por ejemplo",
    "ej.": "ejemplo",
    "obs.": "observación",
    "ed.": "edición",
    "eds.": "ediciones",
    "pp.": "páginas",
    "pág.": "página",
    "vol.": "volumen",
    "art.": "artículo",
    "cap.": "capítulo",
    "sec.": "sección",
    "máx.": "máximo",
    "mín.": "mínimo",
    "tel.": "teléfono",
    "tlfn.": "teléfono",
    "e-mail": "correo electrónico",
    "ref.": "referencia",
    "atc.": "atentamente",
    "saludos": "saludos",
    "Att.": "Atentamente",
}


def get_abbreviation_map() -> dict:
    """Return the abbreviation mapping dictionary."""
    return ABBREVIATION_MAP.copy()
