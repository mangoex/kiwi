from __future__ import annotations

# ruff: noqa: E501
"""sync 156 insumos, base units, presentations, and initial cost states from catalog

Revision ID: 0048_sync_insumos_and_presentations
Revises: 0047_canonical_roles_and_permissions
Create Date: 2026-08-24 17:15:00.000000

"""
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0048_sync_insumos_and_presentations"
down_revision: str | None = "0047_canonical_roles_and_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"

INSUMOS_DATA = [
    {
        "sku": "1001",
        "name": "ACEITUNA NEGRA",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 202.3333,
        "avg_cost": 132.1234,
        "tax": 16.0
    },
    {
        "sku": "1002",
        "name": "ATUN",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 217.3333,
        "avg_cost": 106.9974,
        "tax": 16.0
    },
    {
        "sku": "1003",
        "name": "AVENA",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 59.52,
        "avg_cost": 25.7036,
        "tax": 0.0
    },
    {
        "sku": "1004",
        "name": "AZUCAR",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 21.99,
        "avg_cost": 24.1668,
        "tax": 16.0
    },
    {
        "sku": "1005",
        "name": "AZUCAR LIGTH",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 31.12,
        "avg_cost": 117.2618,
        "tax": 16.0
    },
    {
        "sku": "1006",
        "name": "BOLSA DE HIELO",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 7.0,
        "avg_cost": 38.8689,
        "tax": 0.0
    },
    {
        "sku": "1007",
        "name": "CACAO",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 650.0,
        "avg_cost": 74.2577,
        "tax": 0.0
    },
    {
        "sku": "1008",
        "name": "CHILE",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 51.15,
        "avg_cost": 4.3404,
        "tax": 16.0
    },
    {
        "sku": "1009",
        "name": "CHOCOMILK",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 129.73,
        "avg_cost": 0.0473,
        "tax": 16.0
    },
    {
        "sku": "1010",
        "name": "DATIL",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 184.97,
        "avg_cost": 30.1228,
        "tax": 16.0
    },
    {
        "sku": "1011",
        "name": "DURAZNO",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 116.15,
        "avg_cost": 2.4704,
        "tax": 16.0
    },
    {
        "sku": "1012",
        "name": "GRANOS DE ELOTE",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 103.3333,
        "avg_cost": 50.9536,
        "tax": 16.0
    },
    {
        "sku": "1013",
        "name": "HUEVO",
        "group": "ABARROTE",
        "unit": "PZA",
        "last_cost": 3.1,
        "avg_cost": 16.5592,
        "tax": 0.0
    },
    {
        "sku": "1014",
        "name": "LECHERA",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 67.36,
        "avg_cost": 38.7855,
        "tax": 16.0
    },
    {
        "sku": "1015",
        "name": "MANTEQUILLA",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 92.6,
        "avg_cost": 11.0013,
        "tax": 16.0
    },
    {
        "sku": "1017",
        "name": "MERMELADA DE FRESA",
        "group": "ABARROTE",
        "unit": "PZA",
        "last_cost": 2.34,
        "avg_cost": 1.0799,
        "tax": 16.0
    },
    {
        "sku": "1018",
        "name": "MIEL BOTE",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 103.62,
        "avg_cost": 20.1235,
        "tax": 16.0
    },
    {
        "sku": "1019",
        "name": "PAPELITO GRANDE",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 15.76,
        "avg_cost": 15.7613,
        "tax": 0.0
    },
    {
        "sku": "1020",
        "name": "PLATOS BIODEGRADABLES",
        "group": "ABARROTE",
        "unit": "PZA",
        "last_cost": 0.2414,
        "avg_cost": 0.2414,
        "tax": 16.0
    },
    {
        "sku": "1022",
        "name": "SAZONADOR",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 280.45,
        "avg_cost": 280.4492,
        "tax": 16.0
    },
    {
        "sku": "1023",
        "name": "TAJIN",
        "group": "ABARROTE",
        "unit": "KILO",
        "last_cost": 152.069,
        "avg_cost": 151.2069,
        "tax": 0.0
    },
    {
        "sku": "1025",
        "name": "SABRITAS VEGGIE",
        "group": "ABARROTE",
        "unit": "PZA",
        "last_cost": 25.0,
        "avg_cost": 0.2799,
        "tax": 16.0
    },
    {
        "sku": "2001",
        "name": "ADEREZO ARANDANO",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 49.6042,
        "avg_cost": 26.0408,
        "tax": 0.0
    },
    {
        "sku": "2002",
        "name": "ADEREZO BALSAMICO",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 200.0,
        "avg_cost": 89.7438,
        "tax": 0.0
    },
    {
        "sku": "2003",
        "name": "ADEREZO CHIPOTLE",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 46.1741,
        "avg_cost": 24.5584,
        "tax": 0.0
    },
    {
        "sku": "2004",
        "name": "ADEREZO CILANTRO",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 38.2586,
        "avg_cost": 16.9241,
        "tax": 0.0
    },
    {
        "sku": "2005",
        "name": "ADEREZO RANCH",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 49.6042,
        "avg_cost": 57.0489,
        "tax": 0.0
    },
    {
        "sku": "2006",
        "name": "ADEREZO VINAGRETA",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 42.7599,
        "avg_cost": 118.4857,
        "tax": 0.0
    },
    {
        "sku": "2007",
        "name": "ADEREZO KYOTO",
        "group": "ADEREZOS",
        "unit": "LITRO",
        "last_cost": 150.0,
        "avg_cost": 21.8408,
        "tax": 0.0
    },
    {
        "sku": "3001",
        "name": "BACTERICIDA",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "LITRO",
        "last_cost": 101.28,
        "avg_cost": 1.6721,
        "tax": 16.0
    },
    {
        "sku": "3002",
        "name": "CLORO",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "LITRO",
        "last_cost": 25.0,
        "avg_cost": 1.7314,
        "tax": 16.0
    },
    {
        "sku": "3003",
        "name": "CUBREBOCAS",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "PZA",
        "last_cost": 1.3362,
        "avg_cost": 1.3362,
        "tax": 0.0
    },
    {
        "sku": "3004",
        "name": "GUANTES VINYL",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "PZA",
        "last_cost": 5.1034,
        "avg_cost": 5.1034,
        "tax": 0.0
    },
    {
        "sku": "3005",
        "name": "JABON DE MANOS",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "LTS",
        "last_cost": 64.6552,
        "avg_cost": 64.6552,
        "tax": 16.0
    },
    {
        "sku": "3006",
        "name": "JABON POLVO",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "KILO",
        "last_cost": 64.6552,
        "avg_cost": 64.6552,
        "tax": 0.0
    },
    {
        "sku": "3007",
        "name": "JABON AXION",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "LTS",
        "last_cost": 42.8571,
        "avg_cost": 10.8748,
        "tax": 16.0
    },
    {
        "sku": "3008",
        "name": "LIMPIADOR MULTIUSOS",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "KILO",
        "last_cost": 22.097,
        "avg_cost": 22.097,
        "tax": 16.0
    },
    {
        "sku": "3009",
        "name": "PAPEL HIGIENICO",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "PZA",
        "last_cost": 23.85,
        "avg_cost": 10.3813,
        "tax": 16.0
    },
    {
        "sku": "3010",
        "name": "TOALLA ROLLO CAFE",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "PZA",
        "last_cost": 57.2633,
        "avg_cost": 57.2633,
        "tax": 0.0
    },
    {
        "sku": "3011",
        "name": "TOALLAS INTERDOBLADAS",
        "group": "ARTICULOS DE LIMPIEZA",
        "unit": "PZA",
        "last_cost": 0.1684,
        "avg_cost": 4.6332,
        "tax": 0.0
    },
    {
        "sku": "4001",
        "name": "AGUA JAMAICA",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 17.0,
        "avg_cost": 2.9248,
        "tax": 0.0
    },
    {
        "sku": "4002",
        "name": "AGUA MIRENAL",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 19.52,
        "avg_cost": 2.7284,
        "tax": 0.0
    },
    {
        "sku": "4003",
        "name": "AGUA SIN SED",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 12.91,
        "avg_cost": 4.0041,
        "tax": 0.0
    },
    {
        "sku": "4004",
        "name": "COCA COLA",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 18.58,
        "avg_cost": 4.0531,
        "tax": 0.0
    },
    {
        "sku": "4005",
        "name": "COCA COLA LIGTH",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 19.0,
        "avg_cost": 24.0943,
        "tax": 0.0
    },
    {
        "sku": "4006",
        "name": "GARRAFON SIN SED",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 2.2632,
        "avg_cost": 10.9637,
        "tax": 0.0
    },
    {
        "sku": "4007",
        "name": "JAZTEA",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 15.0,
        "avg_cost": 5.4501,
        "tax": 0.0
    },
    {
        "sku": "4008",
        "name": "JAZTEA LITGH",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 16.0,
        "avg_cost": 31.262,
        "tax": 0.0
    },
    {
        "sku": "4009",
        "name": "JAZTEA STEVIA",
        "group": "BEBIDAS",
        "unit": "PZA",
        "last_cost": 16.0,
        "avg_cost": 33.2004,
        "tax": 0.0
    },
    {
        "sku": "5002",
        "name": "APIO",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 33.5,
        "avg_cost": 42.7036,
        "tax": 0.0
    },
    {
        "sku": "5003",
        "name": "BETABEL",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 20.0,
        "avg_cost": 9.955,
        "tax": 0.0
    },
    {
        "sku": "5004",
        "name": "CEBOLLA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 13.0,
        "avg_cost": 11.929,
        "tax": 0.0
    },
    {
        "sku": "5005",
        "name": "CHAMPIÑON",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 148.8889,
        "avg_cost": 21.6353,
        "tax": 0.0
    },
    {
        "sku": "5006",
        "name": "ESPINACA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 186.2676,
        "avg_cost": 1.1725,
        "tax": 0.0
    },
    {
        "sku": "5010",
        "name": "JENGIBRE",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 92.0,
        "avg_cost": 2.5884,
        "tax": 0.0
    },
    {
        "sku": "5012",
        "name": "KIWI",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 121.0,
        "avg_cost": 8.5369,
        "tax": 0.0
    },
    {
        "sku": "5014",
        "name": "LIMON",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 32.0,
        "avg_cost": 25.2542,
        "tax": 0.0
    },
    {
        "sku": "5015",
        "name": "MANZANA ROJA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 55.0,
        "avg_cost": 50.0814,
        "tax": 0.0
    },
    {
        "sku": "5016",
        "name": "MANZANA VERDE",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 59.0,
        "avg_cost": 58.2373,
        "tax": 0.0
    },
    {
        "sku": "5017",
        "name": "MELON CHINO",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 22.0,
        "avg_cost": 23.9997,
        "tax": 0.0
    },
    {
        "sku": "5018",
        "name": "NARANJA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 17.5,
        "avg_cost": 15.1734,
        "tax": 0.0
    },
    {
        "sku": "5019",
        "name": "NOPAL",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 25.51,
        "avg_cost": 26.0793,
        "tax": 0.0
    },
    {
        "sku": "5020",
        "name": "PAPAYA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 38.9,
        "avg_cost": 26.3026,
        "tax": 0.0
    },
    {
        "sku": "5021",
        "name": "PEPINO",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 13.01,
        "avg_cost": 13.01,
        "tax": 0.0
    },
    {
        "sku": "5022",
        "name": "PIÑA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 18.5,
        "avg_cost": 17.9098,
        "tax": 0.0
    },
    {
        "sku": "5023",
        "name": "PLATANO",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 24.0,
        "avg_cost": 23.8063,
        "tax": 0.0
    },
    {
        "sku": "5026",
        "name": "TORONJA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 25.0,
        "avg_cost": 24.6493,
        "tax": 0.0
    },
    {
        "sku": "5028",
        "name": "JICAMA",
        "group": "FRUTAS Y VERDURA",
        "unit": "KILO",
        "last_cost": 0.0,
        "avg_cost": 0.0,
        "tax": 0.0
    },
    {
        "sku": "6001",
        "name": "JAMON",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "KILO",
        "last_cost": 89.0,
        "avg_cost": 79.4537,
        "tax": 0.0
    },
    {
        "sku": "6002",
        "name": "LECHE DE ALMENDRA",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "LITRO",
        "last_cost": 28.81,
        "avg_cost": 16.4174,
        "tax": 16.0
    },
    {
        "sku": "6003",
        "name": "LECHE DE COCO",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "LITRO",
        "last_cost": 21.34,
        "avg_cost": 10.569,
        "tax": 16.0
    },
    {
        "sku": "6004",
        "name": "LECHE DESLACTOSADA",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "LITRO",
        "last_cost": 26.0,
        "avg_cost": 14.9537,
        "tax": 16.0
    },
    {
        "sku": "6005",
        "name": "LECHE ENTERA",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "LITRO",
        "last_cost": 25.0,
        "avg_cost": 90.0628,
        "tax": 16.0
    },
    {
        "sku": "6006",
        "name": "PASTA FUSILI",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "KILO",
        "last_cost": 4.0,
        "avg_cost": 18.4206,
        "tax": 0.0
    },
    {
        "sku": "6011",
        "name": "QUESO MOZZARELLA",
        "group": "LACTEOS Y PROTEINAS",
        "unit": "KILO",
        "last_cost": 125.431,
        "avg_cost": 125.431,
        "tax": 0.0
    },
    {
        "sku": "1016",
        "name": "MAYONESA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 40.3,
        "avg_cost": 0.2112,
        "tax": 0.0
    },
    {
        "sku": "1021",
        "name": "SALSA BBQ",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 61.62,
        "avg_cost": 33.002,
        "tax": 16.0
    },
    {
        "sku": "5001",
        "name": "AGUACATE",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 84.0,
        "avg_cost": 55.8145,
        "tax": 0.0
    },
    {
        "sku": "5007",
        "name": "FRESA CONGELADA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 53.3333,
        "avg_cost": 54.7954,
        "tax": 0.0
    },
    {
        "sku": "5008",
        "name": "FRESA NATURAL",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 178.41,
        "avg_cost": 0.822,
        "tax": 0.0
    },
    {
        "sku": "5009",
        "name": "GERMINADO",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 104.0,
        "avg_cost": 19.0752,
        "tax": 0.0
    },
    {
        "sku": "5011",
        "name": "JUGO DE NARANJA",
        "group": "PANES Y TORTILLAS",
        "unit": "LITRO",
        "last_cost": 43.75,
        "avg_cost": 3.494,
        "tax": 0.0
    },
    {
        "sku": "5013",
        "name": "LECHUGA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 60.0,
        "avg_cost": 193.5622,
        "tax": 0.0
    },
    {
        "sku": "5024",
        "name": "TOMATE",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 24.0,
        "avg_cost": 25.6978,
        "tax": 0.0
    },
    {
        "sku": "5025",
        "name": "TOMATE CHERRI",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 36.0,
        "avg_cost": 37.5725,
        "tax": 0.0
    },
    {
        "sku": "5027",
        "name": "ZANAHORIA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 9.09,
        "avg_cost": 9.09,
        "tax": 0.0
    },
    {
        "sku": "6007",
        "name": "POLLO",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 200.0,
        "avg_cost": 62.7116,
        "tax": 0.0
    },
    {
        "sku": "6008",
        "name": "QUESO CABRA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 242.5,
        "avg_cost": 134.7025,
        "tax": 0.0
    },
    {
        "sku": "6009",
        "name": "QUESO MANCHEGO",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 150.0,
        "avg_cost": 15.5768,
        "tax": 0.0
    },
    {
        "sku": "6010",
        "name": "QUESO MANCHEGO REBANADA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 2.78,
        "avg_cost": 0.0,
        "tax": 0.0
    },
    {
        "sku": "6012",
        "name": "QUESO PANELA",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 105.0,
        "avg_cost": 47.4062,
        "tax": 0.0
    },
    {
        "sku": "6013",
        "name": "YOGURTH",
        "group": "PANES Y TORTILLAS",
        "unit": "LITRO",
        "last_cost": 48.9,
        "avg_cost": 23.1387,
        "tax": 0.0
    },
    {
        "sku": "7001",
        "name": "BAGUETTE AJO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 12.0,
        "avg_cost": 73.7388,
        "tax": 0.0
    },
    {
        "sku": "7002",
        "name": "BAGUETTE OREGANO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 12.0,
        "avg_cost": 3.3988,
        "tax": 0.0
    },
    {
        "sku": "7003",
        "name": "BAGUETTE INTEGRAL",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 12.0,
        "avg_cost": 67.2022,
        "tax": 0.0
    },
    {
        "sku": "7004",
        "name": "BARRA MINI",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 1.5086,
        "avg_cost": 1.5086,
        "tax": 0.0
    },
    {
        "sku": "7005",
        "name": "BARRA PAN",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 1.875,
        "avg_cost": 29.283,
        "tax": 0.0
    },
    {
        "sku": "7006",
        "name": "BISQUET",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 17.5,
        "avg_cost": 38.6066,
        "tax": 0.0
    },
    {
        "sku": "7007",
        "name": "BOLLITO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 20.0,
        "avg_cost": 24.9342,
        "tax": 0.0
    },
    {
        "sku": "7008",
        "name": "CROTONES",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 67.24,
        "avg_cost": 26.6266,
        "tax": 0.0
    },
    {
        "sku": "7009",
        "name": "CUERNITO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 20.0,
        "avg_cost": 105.5913,
        "tax": 0.0
    },
    {
        "sku": "7010",
        "name": "EMPANADA DE GUAYABA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 17.5,
        "avg_cost": 172.0781,
        "tax": 0.0
    },
    {
        "sku": "7011",
        "name": "FOCACCIA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 20.0,
        "avg_cost": 18.0038,
        "tax": 0.0
    },
    {
        "sku": "7012",
        "name": "FRITUTAS",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 76.0,
        "avg_cost": 40.2389,
        "tax": 0.0
    },
    {
        "sku": "7013",
        "name": "GALLETA CHISPA COMBO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 7.5,
        "avg_cost": 22.0947,
        "tax": 0.0
    },
    {
        "sku": "7014",
        "name": "GALLETA AVENA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 20.0,
        "avg_cost": 11.2867,
        "tax": 0.0
    },
    {
        "sku": "7015",
        "name": "PANQUE CAFE",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 126.1433,
        "tax": 0.0
    },
    {
        "sku": "7016",
        "name": "ROL CANELA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 42.3134,
        "tax": 0.0
    },
    {
        "sku": "7017",
        "name": "TORTILLAS INTEGRAL",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 3.25,
        "avg_cost": 1.4778,
        "tax": 0.0
    },
    {
        "sku": "7018",
        "name": "GALLETAS DE COCO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 20.0,
        "avg_cost": 22.8017,
        "tax": 0.0
    },
    {
        "sku": "7019",
        "name": "CORBATA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 17.5,
        "avg_cost": 14.5204,
        "tax": 16.0
    },
    {
        "sku": "7020",
        "name": "ROL CHOCOLATE",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 25.8986,
        "tax": 16.0
    },
    {
        "sku": "7021",
        "name": "PAN DE NARANJA",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 22.5,
        "tax": 16.0
    },
    {
        "sku": "7022",
        "name": "GALLETAS NUEZ",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 13.8791,
        "tax": 16.0
    },
    {
        "sku": "7023",
        "name": "GALLETA CHOCOLATE",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 22.5,
        "avg_cost": 21.0622,
        "tax": 16.0
    },
    {
        "sku": "8010",
        "name": "CHAROLA COMBO",
        "group": "PANES Y TORTILLAS",
        "unit": "PZA",
        "last_cost": 4.3,
        "avg_cost": 17.605,
        "tax": 16.0
    },
    {
        "sku": "9003",
        "name": "ARANDANO",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 123.0,
        "avg_cost": 1.8913,
        "tax": 0.0
    },
    {
        "sku": "9004",
        "name": "CACAHUATE GARAPIÑADO",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 120.0,
        "avg_cost": 3.4776,
        "tax": 0.0
    },
    {
        "sku": "9007",
        "name": "NUEZ",
        "group": "PANES Y TORTILLAS",
        "unit": "KILO",
        "last_cost": 176.72,
        "avg_cost": 0.8303,
        "tax": 0.0
    },
    {
        "sku": "1024",
        "name": "POPOTES",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.12,
        "avg_cost": 7.9476,
        "tax": 0.0
    },
    {
        "sku": "8001",
        "name": "BOLSA BASURA 70X90",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 41.0,
        "avg_cost": 41.2632,
        "tax": 0.0
    },
    {
        "sku": "8002",
        "name": "BOLSA BASURA 90X120",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 41.0,
        "avg_cost": 19.3341,
        "tax": 0.0
    },
    {
        "sku": "8003",
        "name": "BOLSA CHICA",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 79.0,
        "avg_cost": 19.1383,
        "tax": 0.0
    },
    {
        "sku": "8004",
        "name": "BOLSA GRANDE",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 61.0,
        "avg_cost": 16.6449,
        "tax": 0.0
    },
    {
        "sku": "8005",
        "name": "BOLSA KIWI BAG",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 22.53,
        "avg_cost": 2.0962,
        "tax": 0.0
    },
    {
        "sku": "8006",
        "name": "BOLSA MEDIANA",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 48.0,
        "avg_cost": 13.3065,
        "tax": 0.0
    },
    {
        "sku": "8007",
        "name": "BOLSITA HELADO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "KILO",
        "last_cost": 184.0,
        "avg_cost": 9.2535,
        "tax": 0.0
    },
    {
        "sku": "8008",
        "name": "BOTELLA PLASTICO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 1.71,
        "avg_cost": 1.7381,
        "tax": 0.0
    },
    {
        "sku": "8009",
        "name": "CAJA KIWI BOX",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 35.77,
        "avg_cost": 71.4661,
        "tax": 0.0
    },
    {
        "sku": "8011",
        "name": "CUCHARA",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.25,
        "avg_cost": 0.25,
        "tax": 0.0
    },
    {
        "sku": "8012",
        "name": "CHAROLA ENSALADA CHICA",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 2.59,
        "avg_cost": 33.3621,
        "tax": 16.0
    },
    {
        "sku": "8014",
        "name": "PORTA VASOS",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 4.31,
        "avg_cost": 4.31,
        "tax": 16.0
    },
    {
        "sku": "8015",
        "name": "SERVILLETAS",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.0819,
        "avg_cost": 0.0912,
        "tax": 0.0
    },
    {
        "sku": "8016",
        "name": "TAPA 1 LT",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 1.0,
        "avg_cost": 17.6598,
        "tax": 0.0
    },
    {
        "sku": "8017",
        "name": "TAPA 12 OZ",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 1.4,
        "avg_cost": 12.1496,
        "tax": 0.0
    },
    {
        "sku": "8018",
        "name": "TAPAS 600 ML",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.7,
        "avg_cost": 10.6043,
        "tax": 0.0
    },
    {
        "sku": "8019",
        "name": "TAPA 2 OZ",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.32,
        "avg_cost": 2.4656,
        "tax": 0.0
    },
    {
        "sku": "8020",
        "name": "TAPA ADEREZO CHICO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.25,
        "avg_cost": 40.7798,
        "tax": 0.0
    },
    {
        "sku": "8021",
        "name": "TAPA ADEREZO GDE",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.57,
        "avg_cost": 1.1393,
        "tax": 0.0
    },
    {
        "sku": "8022",
        "name": "TAPA ENSALADERA JADE",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 2.14,
        "avg_cost": 2.0598,
        "tax": 0.0
    },
    {
        "sku": "8023",
        "name": "TENEDOR",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.412,
        "avg_cost": 3.2938,
        "tax": 0.0
    },
    {
        "sku": "8024",
        "name": "VASO 1 LITRO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 2.0,
        "avg_cost": 14.5622,
        "tax": 0.0
    },
    {
        "sku": "8025",
        "name": "VASO 12 OZ",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 12.17,
        "avg_cost": 4.7522,
        "tax": 0.0
    },
    {
        "sku": "8026",
        "name": "VASO 600 ML",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 1.18,
        "avg_cost": 11.8955,
        "tax": 0.0
    },
    {
        "sku": "8027",
        "name": "VASO ADEREZO CHICO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.32,
        "avg_cost": 0.3756,
        "tax": 0.0
    },
    {
        "sku": "8028",
        "name": "VASO ADEREZO GDE",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.8,
        "avg_cost": 0.8656,
        "tax": 0.0
    },
    {
        "sku": "8029",
        "name": "VASO PARA HIELO",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 1.8534,
        "avg_cost": 1.8534,
        "tax": 0.0
    },
    {
        "sku": "8030",
        "name": "VASO 2 OZ",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.36,
        "avg_cost": 7.6025,
        "tax": 0.0
    },
    {
        "sku": "8031",
        "name": "CHAROLA INIX14X14",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 0.0,
        "avg_cost": 0.0,
        "tax": 0.0
    },
    {
        "sku": "8032",
        "name": "CHAROLA YOGURT (INIX 16OZ POR PZA)",
        "group": "PLASTICOS Y DESECHABLES",
        "unit": "PZA",
        "last_cost": 5.0,
        "avg_cost": 15.102,
        "tax": 0.0
    },
    {
        "sku": "9001",
        "name": "AJONJOLI",
        "group": "SEMILLA Y CEREALES",
        "unit": "KILO",
        "last_cost": 92.0,
        "avg_cost": 2.5754,
        "tax": 0.0
    },
    {
        "sku": "9002",
        "name": "ALMENDRA",
        "group": "SEMILLA Y CEREALES",
        "unit": "KILO",
        "last_cost": 136.2069,
        "avg_cost": 136.2069,
        "tax": 0.0
    },
    {
        "sku": "9005",
        "name": "CEREAL YOGURTH",
        "group": "SEMILLA Y CEREALES",
        "unit": "PZA",
        "last_cost": 11.0,
        "avg_cost": 5.6663,
        "tax": 0.0
    },
    {
        "sku": "9006",
        "name": "CHIA",
        "group": "SEMILLA Y CEREALES",
        "unit": "KILO",
        "last_cost": 49.46,
        "avg_cost": 0.8952,
        "tax": 0.0
    },
    {
        "sku": "9008",
        "name": "SEMILLA DE GIRASOL",
        "group": "SEMILLA Y CEREALES",
        "unit": "KILO",
        "last_cost": 65.0,
        "avg_cost": 7.6369,
        "tax": 0.0
    },
    {
        "sku": "9009",
        "name": "CEREAL DE AVENA",
        "group": "SEMILLA Y CEREALES",
        "unit": "PZA",
        "last_cost": 0.0,
        "avg_cost": 0.0,
        "tax": 0.0
    }
]

def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    unit_defs = [
        ("KILO", "Kilogramo", 3, "mass"),
        ("KILOGRAMO", "Kilogramo", 3, "mass"),
        ("KG", "Kilogramo", 3, "mass"),
        ("LITRO", "Litro", 3, "volume"),
        ("LTS", "Litro", 3, "volume"),
        ("L", "Litro", 3, "volume"),
        ("PZA", "Pieza", 0, "count"),
        ("PIEZA", "Pieza", 0, "count"),
    ]

    unit_map = {}
    for code, name, precision, dim in unit_defs:
        row = conn.execute(
            sa.text("SELECT id FROM inventory_units WHERE organization_id = :org_id AND UPPER(code) = :code LIMIT 1"),
            {"org_id": ORGANIZATION_ID, "code": code.upper()},
        ).fetchone()
        if row:
            unit_map[code.upper()] = row[0]
        else:
            uid = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO inventory_units (id, organization_id, code, name, precision_scale, dimension, created_at) "
                    "VALUES (:id, :org_id, :code, :name, :prec, :dim, :created_at)"
                ),
                {
                    "id": uid,
                    "org_id": ORGANIZATION_ID,
                    "code": code.upper(),
                    "name": name,
                    "prec": precision,
                    "dim": dim,
                    "created_at": now,
                },
            )
            unit_map[code.upper()] = uid

    default_unit_id = unit_map.get("PZA") or list(unit_map.values())[0]

    supplier_row = conn.execute(
        sa.text("SELECT id FROM suppliers WHERE organization_id = :org_id LIMIT 1"),
        {"org_id": ORGANIZATION_ID},
    ).fetchone()
    if supplier_row:
        default_supplier_id = supplier_row[0]
    else:
        default_supplier_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO suppliers (id, organization_id, code, commercial_name, legal_name, country, supplier_type, credit_days, currency, delivery_days, payment_methods, status, created_at, updated_at) "
                "VALUES (:id, :org_id, 'SUP-001', 'PROVEEDOR GENERAL', 'PROVEEDOR GENERAL', 'MX', 'insumos', 0, 'MXN', '[]', '[]', 'active', :now, :now)"
            ),
            {"id": default_supplier_id, "org_id": ORGANIZATION_ID, "now": now},
        )

    branches = conn.execute(
        sa.text("SELECT id FROM branches WHERE organization_id = :org_id AND status = 'active'"),
        {"org_id": ORGANIZATION_ID},
    ).fetchall()

    branch_warehouses = []
    for b in branches:
        b_id = b[0]
        wh_row = conn.execute(
            sa.text("SELECT id FROM warehouses WHERE branch_id = :b_id LIMIT 1"),
            {"b_id": b_id},
        ).fetchone()
        if wh_row:
            branch_warehouses.append((b_id, wh_row[0]))
        else:
            wh_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO warehouses (id, organization_id, branch_id, code, name, is_active, status, created_at, updated_at) "
                    "VALUES (:id, :org_id, :b_id, 'WH-PRINCIPAL', 'Almacén Principal', 1, 'active', :now, :now)"
                ),
                {"id": wh_id, "org_id": ORGANIZATION_ID, "b_id": b_id, "now": now},
            )
            branch_warehouses.append((b_id, wh_id))

    for item in INSUMOS_DATA:
        sku = item["sku"]
        name = item["name"]
        group = item.get("group") or "ABARROTE"
        raw_unit = str(item.get("unit") or "PZA").upper()
        base_unit_id = unit_map.get(raw_unit, default_unit_id)
        last_cost = float(round(float(item.get("last_cost") or 0), 4))
        avg_cost = float(round(float(item.get("avg_cost") or last_cost), 4))
        tax_rate = float(round(float(item.get("tax") or 0) / 100.0, 4))

        item_type = "packaging" if any(k in group.upper() for k in ["DESECHABLE", "PAPELERIA", "EMPAQUE"]) else "ingredient"

        existing_item = conn.execute(
            sa.text("SELECT id FROM inventory_items WHERE organization_id = :org_id AND sku = :sku LIMIT 1"),
            {"org_id": ORGANIZATION_ID, "sku": sku},
        ).fetchone()

        if existing_item:
            item_id = existing_item[0]
            conn.execute(
                sa.text(
                    "UPDATE inventory_items SET name = :name, base_unit_id = :unit_id, item_type = :itype, category_name = :cat, updated_at = :now WHERE id = :id"
                ),
                {"name": name, "unit_id": base_unit_id, "itype": item_type, "cat": group, "now": now, "id": item_id},
            )
        else:
            item_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO inventory_items (id, organization_id, name, sku, base_unit_id, item_type, category_name, catalog_scope, status, created_at, updated_at) "
                    "VALUES (:id, :org_id, :name, :sku, :unit_id, :itype, :cat, 'organization', 'active', :now, :now)"
                ),
                {
                    "id": item_id,
                    "org_id": ORGANIZATION_ID,
                    "name": name,
                    "sku": sku,
                    "unit_id": base_unit_id,
                    "itype": item_type,
                    "cat": group,
                    "now": now,
                },
            )

        pres_code = f"PRES-{sku}"
        pres_name = f"{name} · 1 {raw_unit}"
        existing_pres = conn.execute(
            sa.text("SELECT id FROM purchase_presentations WHERE organization_id = :org_id AND code = :code LIMIT 1"),
            {"org_id": ORGANIZATION_ID, "code": pres_code},
        ).fetchone()

        if existing_pres:
            conn.execute(
                sa.text(
                    "UPDATE purchase_presentations SET name = :name, last_net_price = :price, cost_per_base_unit = :cost, tax_rate = :tax, updated_at = :now WHERE id = :id"
                ),
                {
                    "name": pres_name,
                    "price": last_cost,
                    "cost": last_cost,
                    "tax": tax_rate,
                    "now": now,
                    "id": existing_pres[0],
                },
            )
        else:
            pres_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO purchase_presentations (id, organization_id, supplier_id, item_id, code, name, package_type, commercial_quantity, commercial_unit_id, base_unit_id, base_unit_yield, usable_content, yield_percent, tax_rate, last_net_price, cost_per_base_unit, is_preferred, status, created_at, updated_at) "
                    "VALUES (:id, :org_id, :supplier_id, :item_id, :code, :name, 'direct', 1.0, :unit_id, :unit_id, 1.0, 1.0, 1.0, :tax, :price, :cost, 1, 'active', :now, :now)"
                ),
                {
                    "id": pres_id,
                    "org_id": ORGANIZATION_ID,
                    "supplier_id": default_supplier_id,
                    "item_id": item_id,
                    "code": pres_code,
                    "name": pres_name,
                    "unit_id": base_unit_id,
                    "tax": tax_rate,
                    "price": last_cost,
                    "cost": last_cost,
                    "now": now,
                },
            )

        for b_id, wh_id in branch_warehouses:
            cost_row = conn.execute(
                sa.text(
                    "SELECT 1 FROM inventory_cost_states WHERE branch_id = :b_id AND warehouse_id = :wh_id AND item_id = :item_id"
                ),
                {"b_id": b_id, "wh_id": wh_id, "item_id": item_id},
            ).fetchone()

            if cost_row:
                conn.execute(
                    sa.text(
                        "UPDATE inventory_cost_states SET last_unit_cost = :lcost, average_unit_cost = :acost, updated_at = :now WHERE branch_id = :b_id AND warehouse_id = :wh_id AND item_id = :item_id"
                    ),
                    {"lcost": last_cost, "acost": avg_cost, "now": now, "b_id": b_id, "wh_id": wh_id, "item_id": item_id},
                )
            else:
                conn.execute(
                    sa.text(
                        "INSERT INTO inventory_cost_states (branch_id, warehouse_id, item_id, quantity_on_hand, average_unit_cost, last_unit_cost, updated_at) "
                        "VALUES (:b_id, :wh_id, :item_id, 0.0, :acost, :lcost, :now)"
                ),
                {
                    "b_id": b_id,
                    "wh_id": wh_id,
                    "item_id": item_id,
                    "acost": avg_cost,
                    "lcost": last_cost,
                    "now": now,
                },
            )

def downgrade() -> None:
    pass
