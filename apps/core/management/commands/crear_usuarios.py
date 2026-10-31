"""
Management command para crear y configurar usuarios y grupos base del sistema.

Población inicial de seguridad (Ticket 0 / Ticket 3.9.4):
- Grupos: Admin_Institucional, Bedelia_Operadoras, Consulta_Directiva
- Usuarios: admin, director, zaquino, mudarte, msosa
- Contraseña predeterminada: admin123
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = (
        "Crea los grupos y usuarios base para el funcionamiento y testing "
        "del sistema Zunin (Ticket 0 / Ticket 3.9.4)."
    )

    MANAGED_USERS = {
        "admin": {
            "is_superuser": True,
            "is_staff": True,
            "group": None,
        },
        "director": {
            "is_superuser": False,
            "is_staff": True,
            "group": "Admin_Institucional",
        },
        "zaquino": {
            "is_superuser": False,
            "is_staff": True,
            "group": "Bedelia_Operadoras",
        },
        "mudarte": {
            "is_superuser": False,
            "is_staff": True,
            "group": "Bedelia_Operadoras",
            "first_name": "María Eva",
            "last_name": "Duarte",
            "email": "mudarte@iesetyfp.edu.ar",
        },
        "msosa": {
            "is_superuser": False,
            "is_staff": True,
            "group": "Consulta_Directiva",
        },
    }

    MANAGED_GROUPS = [
        "Admin_Institucional",
        "Bedelia_Operadoras",
        "Consulta_Directiva",
    ]

    DEFAULT_PASSWORD = "admin123"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Elimina únicamente los usuarios y grupos gestionados por este "
                "comando antes de crearlos."
            ),
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)
        User = get_user_model()

        with transaction.atomic():
            if reset:
                users_to_delete = User.objects.filter(
                    username__in=self.MANAGED_USERS.keys()
                )
                groups_to_delete = Group.objects.filter(
                    name__in=self.MANAGED_GROUPS
                )
                count_users = users_to_delete.count()
                count_groups = groups_to_delete.count()
                users_to_delete.delete()
                groups_to_delete.delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Reset aplicado: eliminados {count_users} usuario(s) y "
                        f"{count_groups} grupo(s) gestionados."
                    )
                )

            # 1. Configuración de Grupos y Permisos
            # Admin_Institucional: Permisos totales CRUD (add, change, delete, view)
            admin_group, _ = Group.objects.get_or_create(
                name="Admin_Institucional"
            )
            admin_perms = Permission.objects.filter(
                Q(codename__startswith="add_")
                | Q(codename__startswith="change_")
                | Q(codename__startswith="delete_")
                | Q(codename__startswith="view_")
            )
            admin_group.permissions.set(admin_perms)

            # Bedelia_Operadoras: Agregar, cambiar y ver (PROHIBIDO delete)
            bedelia_group, _ = Group.objects.get_or_create(
                name="Bedelia_Operadoras"
            )
            bedelia_perms = Permission.objects.filter(
                Q(codename__startswith="add_")
                | Q(codename__startswith="change_")
                | Q(codename__startswith="view_")
            ).exclude(codename__startswith="delete_")
            bedelia_group.permissions.set(bedelia_perms)

            # Consulta_Directiva: Solo lectura (view)
            consulta_group, _ = Group.objects.get_or_create(
                name="Consulta_Directiva"
            )
            consulta_perms = Permission.objects.filter(
                codename__startswith="view_"
            )
            consulta_group.permissions.set(consulta_perms)

            groups_map = {
                "Admin_Institucional": admin_group,
                "Bedelia_Operadoras": bedelia_group,
                "Consulta_Directiva": consulta_group,
            }

            self.stdout.write(
                self.style.SUCCESS(
                    "Grupos configurados:\n"
                    f"  - Admin_Institucional: {admin_group.permissions.count()} "
                    "permisos (CRUD)\n"
                    f"  - Bedelia_Operadoras: {bedelia_group.permissions.count()} "
                    "permisos (Add/Change/View - Sin Delete)\n"
                    f"  - Consulta_Directiva: {consulta_group.permissions.count()} "
                    "permisos (View únicamente)"
                )
            )

            # 2. Creación / Actualización de Usuarios
            self.stdout.write("Configurando usuarios:")
            for username, config in self.MANAGED_USERS.items():
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "is_superuser": config["is_superuser"],
                        "is_staff": config["is_staff"],
                    },
                )
                user.is_superuser = config["is_superuser"]
                user.is_staff = config["is_staff"]
                if "first_name" in config:
                    user.first_name = config["first_name"]
                if "last_name" in config:
                    user.last_name = config["last_name"]
                if "email" in config:
                    user.email = config["email"]
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()

                group_name = config["group"]
                if group_name:
                    group_obj = groups_map[group_name]
                    user.groups.set([group_obj])
                    group_info = f"grupo: {group_name}"
                else:
                    user.groups.clear()
                    group_info = "sin grupo (superusuario)"

                action = "Creado" if created else "Actualizado"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{action}] {username} (staff={user.is_staff}, "
                        f"superuser={user.is_superuser}, {group_info})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Operación completada con éxito. "
                "Todos los usuarios y grupos fueron configurados."
            )
        )
