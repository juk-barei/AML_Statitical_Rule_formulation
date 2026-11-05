import sys
from pathlib import Path
package_dir = Path(__file__).resolve().parent
project_root = package_dir.parent

if project_root not in sys.path:
    sys.path.insert(0,str(project_root))

