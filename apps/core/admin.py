"""
Configuración del panel de administración para el módulo Core.
Establece títulos institucionales y cabeceras del admin de Django.
"""

from django.contrib import admin

# Personalización del Panel de Administración IESETyFP
admin.site.site_header = "IESETyFP - Bedelía y Gestión Docente"
admin.site.site_title = "IESETyFP Bedelía"
admin.site.index_title = "Panel de Administración"
