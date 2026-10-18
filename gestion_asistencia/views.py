from django.shortcuts import render


def index_view(request):
    """
    Vista principal del panel de Bedelía - IESETyFP.
    Muestra el estado general del sistema y accesos rápidos a asistencia y licencias.
    """
    context = {
        "institucion": "IESETyFP",
        "subtitulo": "Sistema de Gestión de Asistencia y Licencias Docentes",
        "modulo_activo": "dashboard",
    }
    return render(request, "gestion_asistencia/index.html", context)
