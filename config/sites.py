#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Definiciones y configuraciones para los diferentes sitios web soportados.
"""

# Definición de los sitios soportados
SUPPORTED_SITES = {
    # M440.in
    'M440': {
        'name': 'M440.in',
        'domain': 'm440.in',
        'url_patterns': ['https://m440.in/manga/', 'https://m440.in/capitulo/'],
        'scraper_module': 'scrapers.m440_scraper',
        'get_chapters_func': 'get_m440_chapters',
        'scrape_func': 'scrape_m440'
    },
    
    # Olympusscanlation
    'OLYMPUS': {
        'name': 'Olympusscanlation',
        'domain': 'olympusscanlation.com',
        'url_patterns': ['https://olympusscanlation.com/'],
        'scraper_module': 'scrapers.olympus_scraper',
        'get_chapters_func': 'get_olympus_chapters',
        'scrape_func': 'scrape_olympus'
    },
    
    # Inquisitorscans
    'INQUISITOR': {
        'name': 'Inquisitorscans',
        'domain': 'inquisitorscans.com',
        'url_patterns': ['https://inquisitorscans.com/'],
        'scraper_module': 'scrapers.olympus_scraper',  # Usa el mismo scraper que Olympus
        'get_chapters_func': 'get_olympus_chapters',
        'scrape_func': 'scrape_olympus'
    },
    
    # Otros sitios pueden ser añadidos aquí siguiendo el mismo formato
}

def identify_site(url):
    """
    Identifica el sitio al que pertenece una URL.
    
    Args:
        url: URL a identificar
        
    Returns:
        dict: Configuración del sitio o None si no es soportado
    """
    for site_id, site_config in SUPPORTED_SITES.items():
        # Verificar si la URL contiene el dominio del sitio
        if site_config['domain'] in url:
            return site_config
            
        # También verificar patrones de URL específicos
        for pattern in site_config['url_patterns']:
            if url.startswith(pattern):
                return site_config
                
    return None

def get_site_id_by_number(site_number):
    """
    Obtiene el ID de un sitio por su número en el menú.
    
    Args:
        site_number: Número del sitio (1-based)
        
    Returns:
        str: ID del sitio o None si el número es inválido
    """
    sites = list(SUPPORTED_SITES.keys())
    if 1 <= site_number <= len(sites):
        return sites[site_number - 1]
    return None

def print_supported_sites():
    """Imprime una lista de los sitios soportados."""
    print("\nSitios soportados:")
    for i, (site_id, site_config) in enumerate(SUPPORTED_SITES.items(), 1):
        print(f"{i}. {site_config['name']} ({site_config['domain']})")
