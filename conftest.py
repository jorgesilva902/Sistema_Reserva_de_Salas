import sys
from pathlib import Path

# Agregar raíz del proyecto al sys.path para resolución de imports del paquete 'app'
root_path = Path(__file__).resolve().parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))
