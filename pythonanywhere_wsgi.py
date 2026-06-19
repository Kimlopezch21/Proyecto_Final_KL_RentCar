import os
import sys


PROJECT_DIR = "/home/tu_usuario/Proyecto_Final_KL_RentCar"

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault("RENTCAR_DB", os.path.join(PROJECT_DIR, "rentcar.sqlite"))
os.environ.setdefault("RENTCAR_DEMO_AUTH", "0")

from app import application  # noqa: E402
